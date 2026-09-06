"""Check a Cloudflare Turnstile token before an unauthenticated endpoint does any work.

Four endpoints accept a request from nobody in particular: register, login,
forgot-password, and resend-verification. Each costs the service something real, a
bcrypt hash, an account row, an outbound email, and none of them can ask the caller
who they are. A Turnstile token is the evidence that a browser and a person were
involved; this module is the half that checks the evidence.

The check is fail-closed. A missing header, a token Cloudflare rejects, a token minted
for another form or another site, a siteverify call that times out, answers non-2xx, or
answers something that is not JSON: all end in the same
:class:`~api.exceptions.TurnstileVerificationError`. Failing open on the transport
faults would be worse than having no check, because the way past it would then be to
make Cloudflare unreachable.

``action`` and ``hostname`` are verified, not just ``success``. A widget's sitekey is
public, so a token can be minted anywhere the sitekey is pasted. ``hostname`` is how
siteverify reports where that was and ``action`` is which form it was for; without both,
a token farmed from a copy of the site, or from the login form, would open registration
here.
"""

import ipaddress
import logging
from typing import NoReturn, Protocol

import httpx

from api.exceptions import TurnstileVerificationError

logger = logging.getLogger("api.security")

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# Budget for one siteverify call. Cloudflare answers in tens of milliseconds; this is
# the ceiling past which the request is refused rather than left hanging on a worker.
SITEVERIFY_TIMEOUT_SECONDS = 10.0


def _refuse(reason: str, action: str, **fields: object) -> NoReturn:
    """Record a refused bot check and raise.

    The record names the reason and the action, never the token. A token is a live
    credential for one submission, and the log drain is a different trust boundary
    from the request that carried it.

    :param reason: Why the check refused, e.g. ``missing_token``.
    :param action: The action the guarded endpoint declared.
    :param fields: Extra structured context; never the token.
    :raises TurnstileVerificationError: Always.
    """
    logger.warning(
        "Turnstile check refused a request",
        extra={"event": "turnstile_refused", "reason": reason, "action": action, **fields},
    )
    raise TurnstileVerificationError(f"turnstile check refused the request: {reason}")


def _remote_ip(client_ip: str) -> str | None:
    """Return ``client_ip`` when it is a real address, and ``None`` when it is not.

    :func:`api.utils.client_ip.get_client_ip` answers with a sentinel rather than an
    address whenever the origin cannot vouch for the caller (``unverified-origin``) or
    there is no transport peer at all (``unknown``). Neither is an IP. ``remoteip`` is
    an optional field, so sending nothing is the honest answer; sending a sentinel
    risks siteverify rejecting the call itself as malformed, which would refuse every
    such request for a reason that has nothing to do with its token.

    :param client_ip: Whatever ``get_client_ip`` resolved.
    :return: The address, or ``None`` when it is a sentinel.
    """
    try:
        ipaddress.ip_address(client_ip)
    except ValueError:
        return None
    return client_ip


class TurnstileVerifier(Protocol):
    """Backend deciding whether a request carries proof that a person made it."""

    async def verify(self, token: str | None, *, action: str, client_ip: str) -> None:
        """Accept the request, or refuse it.

        :param token: Raw ``X-Turnstile-Token`` header value; ``None`` when absent.
        :param action: The action the guarded endpoint declared.
        :param client_ip: Caller address resolved by ``api.utils.client_ip``.
        :raises TurnstileVerificationError: If the request carries no usable token.
        """
        ...


class DisabledTurnstileVerifier:
    """Verifier for a process running with the bot check switched off.

    Accepts every request without contacting Cloudflare, which is what lets local
    development and the test suite work with no widget and no secret. A deployed
    service can end up here too, deliberately: ``turnstile_enabled`` is the kill switch
    for a siteverify outage, and a deploy that flips it starts rather than being
    refused. It does not do so quietly, though -
    :func:`api.main._report_disabled_bot_check` records that state at ERROR on startup.
    """

    async def verify(self, token: str | None, *, action: str, client_ip: str) -> None:
        """Accept the request, whatever it carries.

        :param token: Ignored.
        :param action: Ignored.
        :param client_ip: Ignored.
        """


class CloudflareTurnstileVerifier:
    """Check a token against Cloudflare's siteverify endpoint, fail-closed.

    :param secret_key: The widget's secret, paired with the sitekey the frontend renders.
    :param allowed_hostnames: Hostnames a token may have been minted on. A response
        naming anything else is refused, and so is every response while the set is
        empty, since nothing can be in it.
    :param client: Preconfigured async HTTP client; a fresh one is opened per call when
        omitted (injected directly in tests).
    :param timeout_seconds: Budget for one siteverify call, used only for a client this
        verifier opens itself.
    """

    def __init__(
        self,
        *,
        secret_key: str,
        allowed_hostnames: frozenset[str],
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = SITEVERIFY_TIMEOUT_SECONDS,
    ) -> None:
        """Store the widget credentials and an optional injected HTTP client."""
        self._secret_key = secret_key
        self._allowed_hostnames = allowed_hostnames
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def verify(self, token: str | None, *, action: str, client_ip: str) -> None:
        """Refuse the request unless Cloudflare vouches for this exact submission.

        :param token: Raw ``X-Turnstile-Token`` header value; ``None`` when absent.
        :param action: The action the guarded endpoint declared.
        :param client_ip: Caller address resolved by ``api.utils.client_ip``.
        :raises TurnstileVerificationError: On any outcome short of a token Cloudflare
            accepts, for this action, minted on an allowed hostname.
        """
        if not token:
            # Nothing to ask about, so no call is made. The refusal is the same one a
            # rejected token gets, so the answer cannot be read back for whether the
            # check is even switched on.
            _refuse("missing_token", action)
        body = await self._siteverify(token, action=action, client_ip=client_ip)
        if body.get("success") is not True:
            _refuse("rejected", action, error_codes=body.get("error-codes"))
        if body.get("action") != action:
            _refuse("action_mismatch", action, token_action=body.get("action"))
        if body.get("hostname") not in self._allowed_hostnames:
            _refuse("hostname_mismatch", action, token_hostname=body.get("hostname"))

    async def _siteverify(self, token: str, *, action: str, client_ip: str) -> dict[str, object]:
        """Ask Cloudflare about one token and return the answer it parsed to.

        :param token: The raw token to check.
        :param action: The action the guarded endpoint declared, for the refusal record.
        :param client_ip: Caller address, sent as ``remoteip`` when it is an address.
        :return: The decoded response object.
        :raises TurnstileVerificationError: If the call fails, answers non-2xx, or
            answers with something other than a JSON object.
        """
        payload = {"secret": self._secret_key, "response": token}
        remote_ip = _remote_ip(client_ip)
        if remote_ip is not None:
            payload["remoteip"] = remote_ip
        body: object
        try:
            response = await self._post(payload)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            _refuse("siteverify_status", action, status_code=exc.response.status_code)
        except httpx.HTTPError:
            # A timeout, a refused connection, or any other transport fault. Cloudflare
            # being unreachable is when a bot check is most worth having, so this
            # refuses rather than waving the request through.
            _refuse("siteverify_unreachable", action)
        except ValueError:
            # httpx raises json.JSONDecodeError, a ValueError, when the body is not
            # JSON at all: an error page or a captive portal in front of the API.
            _refuse("malformed_response", action)
        if not isinstance(body, dict):
            _refuse("malformed_response", action)
        return body

    async def _post(self, payload: dict[str, str]) -> httpx.Response:
        """POST the form-encoded payload using the injected client or a fresh one.

        :param payload: The siteverify form fields.
        :return: The HTTP response.
        """
        if self._client is not None:
            return await self._client.post(SITEVERIFY_URL, data=payload)
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            return await client.post(SITEVERIFY_URL, data=payload)
