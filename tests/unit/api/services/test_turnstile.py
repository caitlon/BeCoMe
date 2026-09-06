"""Unit tests for the Cloudflare Turnstile verifier.

No test performs real network I/O: the HTTP client is always injected, and the one
case that lets the verifier build its own patches ``httpx.AsyncClient``.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from api.exceptions import TurnstileVerificationError
from api.services.turnstile_service import (
    SITEVERIFY_TIMEOUT_SECONDS,
    SITEVERIFY_URL,
    CloudflareTurnstileVerifier,
    DisabledTurnstileVerifier,
)

_TOKEN = "0.a-token-minted-by-the-widget"
_HOSTNAMES = frozenset({"www.becomify.app", "becomify.app"})


def _client(body: object = None, *, status_error: bool = False) -> MagicMock:
    """Build an HTTP client stub whose ``post`` is an AsyncMock.

    :param body: Value ``response.json()`` returns; a successful siteverify answer
        when omitted.
    :param status_error: Whether ``raise_for_status`` raises, as it does on a 5xx.
    :return: The client stub.
    """
    response = MagicMock()
    if status_error:
        error_response = MagicMock()
        error_response.status_code = 503
        response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=error_response)
        )
    else:
        response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=body if body is not None else _siteverify_body())
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    return client


def _siteverify_body(**overrides: object) -> dict[str, object]:
    """Build a siteverify response body that the verifier accepts.

    :param overrides: Fields to replace, e.g. ``success=False``.
    :return: The response body.
    """
    body: dict[str, object] = {
        "success": True,
        "action": "register",
        "hostname": "www.becomify.app",
        "challenge_ts": "2026-09-06T10:00:00.000Z",
        "error-codes": [],
    }
    body.update(overrides)
    return body


def _verifier(client: MagicMock | None = None) -> CloudflareTurnstileVerifier:
    """Build a verifier wired to the given client stub and the test hostnames.

    :param client: HTTP client stub; a fresh accepting one when omitted.
    :return: The verifier under test.
    """
    return CloudflareTurnstileVerifier(
        secret_key="a-turnstile-secret",
        allowed_hostnames=_HOSTNAMES,
        client=client if client is not None else _client(),
    )


def _verify(
    verifier: CloudflareTurnstileVerifier | DisabledTurnstileVerifier,
    token: str | None = _TOKEN,
    *,
    action: str = "register",
    client_ip: str = "203.0.113.7",
) -> None:
    """Run one verification to completion.

    :param verifier: The verifier under test.
    :param token: Header value to check.
    :param action: Action the guarded endpoint declared.
    :param client_ip: Caller address the guard resolved.
    """
    asyncio.run(verifier.verify(token, action=action, client_ip=client_ip))


class TestCloudflareTurnstileVerifierAccepts:
    """The one path that lets a request through."""

    def test_accepts_a_token_cloudflare_vouches_for(self):
        """
        GIVEN siteverify answers success for this action and an allowed hostname
        WHEN the token is verified
        THEN nothing is raised
        """
        # GIVEN
        verifier = _verifier()

        # WHEN/THEN
        _verify(verifier)

    def test_posts_the_secret_token_and_client_ip_form_encoded(self):
        """
        GIVEN a verifier with an injected client
        WHEN a token is verified
        THEN siteverify is POSTed the secret, the token, and the caller's address
        """
        # GIVEN
        client = _client()
        verifier = _verifier(client)

        # WHEN
        _verify(verifier, client_ip="203.0.113.7")

        # THEN
        client.post.assert_awaited_once()
        call = client.post.call_args
        assert call.args[0] == SITEVERIFY_URL
        # data=, not json=: siteverify takes an application/x-www-form-urlencoded body.
        assert call.kwargs["data"] == {
            "secret": "a-turnstile-secret",
            "response": _TOKEN,
            "remoteip": "203.0.113.7",
        }

    def test_omits_remoteip_when_the_client_ip_is_a_sentinel(self):
        """
        GIVEN get_client_ip resolved a sentinel rather than an address
        WHEN a token is verified
        THEN remoteip is left out instead of being sent as a non-address

        The sentinels ("unverified-origin", "unknown") are not IPs. Sending one risks
        siteverify rejecting the whole call as malformed, which would refuse every
        such request for a reason that has nothing to do with its token.
        """
        # GIVEN
        client = _client()
        verifier = _verifier(client)

        # WHEN
        _verify(verifier, client_ip="unverified-origin")

        # THEN
        assert "remoteip" not in client.post.call_args.kwargs["data"]

    def test_accepts_an_ipv6_client_address(self):
        """
        GIVEN a caller reaching the service over IPv6
        WHEN a token is verified
        THEN the address is sent as remoteip like any other
        """
        # GIVEN
        client = _client()
        verifier = _verifier(client)

        # WHEN
        _verify(verifier, client_ip="2001:db8::1")

        # THEN
        assert client.post.call_args.kwargs["data"]["remoteip"] == "2001:db8::1"

    def test_builds_its_own_client_when_none_is_injected(self):
        """
        GIVEN a verifier constructed without a client
        WHEN a token is verified
        THEN it opens its own AsyncClient on the configured timeout
        """
        # GIVEN
        verifier = CloudflareTurnstileVerifier(
            secret_key="a-turnstile-secret",
            allowed_hostnames=_HOSTNAMES,
        )
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = MagicMock(return_value=_siteverify_body())
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=False)

        # WHEN
        with patch(
            "api.services.turnstile_service.httpx.AsyncClient", return_value=context
        ) as mock_client:
            _verify(verifier)

        # THEN
        assert mock_client.call_args.kwargs["timeout"] == SITEVERIFY_TIMEOUT_SECONDS
        client.post.assert_awaited_once()


class TestCloudflareTurnstileVerifierRefuses:
    """Every other path. All of them end in a refusal, never in a leaked exception."""

    def test_refuses_a_missing_token(self):
        """
        GIVEN a request that carried no X-Turnstile-Token header
        WHEN the check runs
        THEN it is refused
        """
        # GIVEN
        verifier = _verifier()

        # WHEN/THEN
        with pytest.raises(TurnstileVerificationError):
            _verify(verifier, None)

    def test_refuses_an_empty_token(self):
        """
        GIVEN a request whose header is present but empty
        WHEN the check runs
        THEN it is refused
        """
        # GIVEN
        verifier = _verifier()

        # WHEN/THEN
        with pytest.raises(TurnstileVerificationError):
            _verify(verifier, "")

    def test_a_missing_token_never_reaches_cloudflare(self):
        """
        GIVEN a request with no token
        WHEN the check runs
        THEN siteverify is not called at all, since there is nothing to ask about
        """
        # GIVEN
        client = _client()
        verifier = _verifier(client)

        # WHEN
        with pytest.raises(TurnstileVerificationError):
            _verify(verifier, None)

        # THEN
        client.post.assert_not_awaited()

    def test_refuses_when_siteverify_reports_failure(self):
        """
        GIVEN siteverify answers success: false
        WHEN the check runs
        THEN it is refused
        """
        # GIVEN
        verifier = _verifier(
            _client(_siteverify_body(success=False, **{"error-codes": ["invalid-input-response"]}))
        )

        # WHEN/THEN
        with pytest.raises(TurnstileVerificationError):
            _verify(verifier)

    def test_refuses_a_token_minted_for_another_action(self):
        """
        GIVEN a token whose action is the login widget's, presented to register
        WHEN the check runs
        THEN it is refused, so a token cannot be replayed across forms
        """
        # GIVEN
        verifier = _verifier(_client(_siteverify_body(action="login")))

        # WHEN/THEN
        with pytest.raises(TurnstileVerificationError):
            _verify(verifier, action="register")

    def test_refuses_a_token_minted_on_another_hostname(self):
        """
        GIVEN a token minted on a host outside the configured list
        WHEN the check runs
        THEN it is refused, so a copy of the site cannot mint tokens for this one

        A sitekey is public, so anybody can paste the widget onto their own page. The
        hostname in the answer is how siteverify says where the token was minted.
        """
        # GIVEN
        verifier = _verifier(_client(_siteverify_body(hostname="phish.example.com")))

        # WHEN/THEN
        with pytest.raises(TurnstileVerificationError):
            _verify(verifier)

    def test_refuses_when_siteverify_times_out(self):
        """
        GIVEN siteverify never answers within the timeout
        WHEN the check runs
        THEN it is refused rather than waved through

        Failing open here would make the way past the check "make Cloudflare slow".
        """
        # GIVEN
        client = MagicMock()
        client.post = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        verifier = _verifier(client)

        # WHEN/THEN
        with pytest.raises(TurnstileVerificationError):
            _verify(verifier)

    def test_refuses_when_siteverify_cannot_be_reached(self):
        """
        GIVEN the siteverify host refuses the connection
        WHEN the check runs
        THEN it is refused
        """
        # GIVEN
        client = MagicMock()
        client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        verifier = _verifier(client)

        # WHEN/THEN
        with pytest.raises(TurnstileVerificationError):
            _verify(verifier)

    def test_refuses_on_a_non_2xx_answer(self):
        """
        GIVEN siteverify answers 503
        WHEN the check runs
        THEN it is refused
        """
        # GIVEN
        verifier = _verifier(_client(status_error=True))

        # WHEN/THEN
        with pytest.raises(TurnstileVerificationError):
            _verify(verifier)

    def test_refuses_a_body_that_is_not_json(self):
        """
        GIVEN a 200 whose body does not parse as JSON, as an error page would not
        WHEN the check runs
        THEN it is refused instead of raising a decode error at the caller
        """
        # GIVEN
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = MagicMock(side_effect=json.JSONDecodeError("no", "<html>", 0))
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        verifier = _verifier(client)

        # WHEN/THEN
        with pytest.raises(TurnstileVerificationError):
            _verify(verifier)

    def test_refuses_a_json_body_that_is_not_an_object(self):
        """
        GIVEN a body that parses as JSON but is a list, not the expected object
        WHEN the check runs
        THEN it is refused rather than crashing on the first field lookup
        """
        # GIVEN
        verifier = _verifier(_client([1, 2, 3]))

        # WHEN/THEN
        with pytest.raises(TurnstileVerificationError):
            _verify(verifier)

    def test_refusal_record_never_carries_the_token(self):
        """
        GIVEN a token siteverify rejects
        WHEN the check refuses the request
        THEN no log record carries the raw token

        Records travel to the rotating file handler and to the log drain. A token is a
        live credential for one submission, so it must not ride along.
        """
        # GIVEN
        verifier = _verifier(_client(_siteverify_body(success=False)))

        # WHEN
        with (
            patch("api.services.turnstile_service.logger") as mock_logger,
            pytest.raises(TurnstileVerificationError),
        ):
            _verify(verifier)

        # THEN
        assert _TOKEN not in str(mock_logger.method_calls)


class TestDisabledTurnstileVerifier:
    """The verifier a process gets when the check is switched off."""

    def test_accepts_a_request_with_no_token(self):
        """
        GIVEN the check is disabled
        WHEN a request with no token is verified
        THEN nothing is raised, so local development needs no widget
        """
        # GIVEN
        verifier = DisabledTurnstileVerifier()

        # WHEN/THEN
        _verify(verifier, None)

    def test_accepts_a_token_no_widget_ever_minted(self):
        """
        GIVEN the check is disabled
        WHEN a request with a junk token is verified
        THEN nothing is raised and nothing is asked of Cloudflare
        """
        # GIVEN
        verifier = DisabledTurnstileVerifier()

        # WHEN/THEN
        _verify(verifier, "not-a-real-token")
