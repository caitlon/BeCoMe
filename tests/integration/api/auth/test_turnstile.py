"""Integration tests for the Turnstile bot check on the unauthenticated auth endpoints.

Every case goes through the real route, so removing the guard from a route turns one of
these red. The verifier is a stub: what is under test is the wiring, not siteverify.

The check is off by default, which is what keeps the rest of the suite posting to these
endpoints with no header. Each test here switches it on by overriding the verifier
factory, and does its setup before that override so the fixtures it needs are not
themselves refused.
"""

import pytest

from api.auth.turnstile import TURNSTILE_HEADER
from api.dependencies import get_turnstile_verifier
from api.exceptions import TurnstileVerificationError
from api.middleware.exception_handlers import TURNSTILE_REFUSED_DETAIL
from api.services.user_service import UserService
from tests.integration.api.conftest import (
    app_session,
    register_verified,
    stored_accounts,
)

PASSWORD = "SecurePass123!"
GOOD_TOKEN = "0.a-token-the-widget-minted"


class StubVerifier:
    """Verifier that accepts one known token and refuses everything else.

    Stands in for ``CloudflareTurnstileVerifier`` so no test needs a live siteverify
    call. It records what the guard passed it, which is how the action each endpoint
    declares is checked.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str | None, str]] = []

    async def verify(self, token: str | None, *, action: str, client_ip: str) -> None:
        """Record the call, then accept the known token and refuse anything else."""
        self.calls.append((token, action))
        if token != GOOD_TOKEN:
            raise TurnstileVerificationError("stub refusal")


def enable_check(client) -> StubVerifier:
    """Switch the bot check on for this app by installing the stub verifier.

    :param client: Test client whose app the override is installed on.
    :return: The stub, for reading back what the guard asked it.
    """
    verifier = StubVerifier()
    client.app.dependency_overrides[get_turnstile_verifier] = lambda: verifier
    return verifier


def header(token: str | None = GOOD_TOKEN) -> dict[str, str]:
    """Build the request headers carrying a Turnstile token.

    :param token: Token to send; no header at all when None.
    :return: Headers for the request.
    """
    return {TURNSTILE_HEADER: token} if token is not None else {}


def post_register(client, email: str, token: str | None = None):
    """Post a registration, optionally carrying a token.

    :param client: Test client instance.
    :param email: Address to register.
    :param token: Token to send, or None to send no header.
    :return: The response.
    """
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "first_name": "Test",
            "last_name": "User",
        },
        headers=header(token),
    )


def post_login(client, email: str, token: str | None = None):
    """Post a login, optionally carrying a token.

    :param client: Test client instance.
    :param email: Address to sign in as.
    :param token: Token to send, or None to send no header.
    :return: The response.
    """
    return client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
        headers=header(token),
    )


def post_forgot_password(client, email: str, token: str | None = None):
    """Post a password-reset request, optionally carrying a token.

    :param client: Test client instance.
    :param email: Address to send the reset link to.
    :param token: Token to send, or None to send no header.
    :return: The response.
    """
    return client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email},
        headers=header(token),
    )


def post_resend_verification(client, email: str, token: str | None = None):
    """Post a resend request, optionally carrying a token.

    :param client: Test client instance.
    :param email: Address to resend the activation link to.
    :param token: Token to send, or None to send no header.
    :return: The response.
    """
    return client.post(
        "/api/v1/auth/resend-verification",
        json={"email": email, "password": PASSWORD},
        headers=header(token),
    )


def create_unverified(client, email: str) -> None:
    """Create an account that still needs activating, without going through a route.

    Registering through the endpoint would spend the address's verification-email
    budget, which would then suppress the resend under test for a reason that has
    nothing to do with the bot check.

    :param client: Test client instance.
    :param email: Address to create the account for.
    """
    with app_session(client) as session:
        UserService(session).create_user(
            email=email,
            password=PASSWORD,
            first_name="Test",
            last_name="User",
        )


class TestRefusedWithoutAToken:
    """With the check on, a request carrying no token is refused before anything runs."""

    def test_register_is_refused_and_creates_nothing(self, client, fake_email):
        """
        GIVEN the bot check is on
        WHEN a registration arrives with no X-Turnstile-Token header
        THEN it is refused with 403, no account is written and no email goes out
        """
        # GIVEN
        enable_check(client)

        # WHEN
        response = post_register(client, "nobody@example.com")

        # THEN
        assert response.status_code == 403
        assert stored_accounts(client, "nobody@example.com") == []
        assert fake_email.verification_calls == []

    def test_login_is_refused(self, client, fake_email):
        """
        GIVEN a verified account and the bot check on
        WHEN a login arrives with no token
        THEN it is refused with 403 and no tokens are issued
        """
        # GIVEN
        register_verified(client, "login@example.com", PASSWORD)
        enable_check(client)

        # WHEN
        response = post_login(client, "login@example.com")

        # THEN
        assert response.status_code == 403
        assert "access_token" not in response.json()

    def test_forgot_password_is_refused_and_mails_nothing(self, client, fake_email):
        """
        GIVEN a verified account and the bot check on
        WHEN a reset request arrives with no token
        THEN it is refused with 403 and no reset email goes out
        """
        # GIVEN
        register_verified(client, "reset@example.com", PASSWORD)
        enable_check(client)

        # WHEN
        response = post_forgot_password(client, "reset@example.com")

        # THEN
        assert response.status_code == 403
        assert fake_email.calls == []

    def test_resend_verification_is_refused_and_mails_nothing(self, client, fake_email):
        """
        GIVEN an unverified account and the bot check on
        WHEN a resend request arrives with no token
        THEN it is refused with 403 and no activation link goes out
        """
        # GIVEN
        create_unverified(client, "pending@example.com")
        enable_check(client)

        # WHEN
        response = post_resend_verification(client, "pending@example.com")

        # THEN
        assert response.status_code == 403
        assert fake_email.verification_calls == []


class TestUnchangedWithAToken:
    """With a token the verifier accepts, each endpoint behaves exactly as before."""

    def test_register_still_creates_the_account(self, client, fake_email):
        """
        GIVEN the bot check is on
        WHEN a registration arrives with an accepted token
        THEN it answers 202 and the account is written as usual
        """
        # GIVEN
        enable_check(client)

        # WHEN
        response = post_register(client, "welcome@example.com", GOOD_TOKEN)

        # THEN
        assert response.status_code == 202
        assert len(stored_accounts(client, "welcome@example.com")) == 1
        assert len(fake_email.verification_calls) == 1

    def test_login_still_issues_tokens(self, client, fake_email):
        """
        GIVEN a verified account and the bot check on
        WHEN a login arrives with an accepted token
        THEN it answers 200 with an access token
        """
        # GIVEN
        register_verified(client, "member@example.com", PASSWORD)
        enable_check(client)

        # WHEN
        response = post_login(client, "member@example.com", GOOD_TOKEN)

        # THEN
        assert response.status_code == 200
        assert response.json()["access_token"]

    def test_forgot_password_still_mails_the_link(self, client, fake_email):
        """
        GIVEN a verified account and the bot check on
        WHEN a reset request arrives with an accepted token
        THEN it answers 202 and the reset email goes out
        """
        # GIVEN
        register_verified(client, "forgot@example.com", PASSWORD)
        enable_check(client)

        # WHEN
        response = post_forgot_password(client, "forgot@example.com", GOOD_TOKEN)

        # THEN
        assert response.status_code == 202
        assert len(fake_email.calls) == 1

    def test_resend_verification_still_mails_the_link(self, client, fake_email):
        """
        GIVEN an unverified account and the bot check on
        WHEN a resend request arrives with an accepted token
        THEN it answers 202 and the activation link goes out
        """
        # GIVEN
        create_unverified(client, "again@example.com")
        enable_check(client)

        # WHEN
        response = post_resend_verification(client, "again@example.com", GOOD_TOKEN)

        # THEN
        assert response.status_code == 202
        assert len(fake_email.verification_calls) == 1


class TestGuardWiring:
    """What the guard hands the verifier, and which routes it is attached to."""

    def test_each_endpoint_declares_its_own_action(self, client, fake_email):
        """
        GIVEN the bot check is on
        WHEN each guarded endpoint is called
        THEN the verifier is asked about that endpoint's own action

        A token is pinned to the action it was minted for, so a copy-pasted action
        would silently let one form's token open another.
        """
        # GIVEN
        verifier = enable_check(client)

        # WHEN
        post_register(client, "actions@example.com")
        post_login(client, "actions@example.com")
        post_forgot_password(client, "actions@example.com")
        post_resend_verification(client, "actions@example.com")

        # THEN
        assert [action for _, action in verifier.calls] == [
            "register",
            "login",
            "password_reset",
            "resend_verification",
        ]

    def test_the_token_reaches_the_verifier_from_the_header(self, client, fake_email):
        """
        GIVEN the bot check is on
        WHEN a request carries X-Turnstile-Token
        THEN that value is what the verifier is asked about
        """
        # GIVEN
        verifier = enable_check(client)

        # WHEN
        post_register(client, "carried@example.com", GOOD_TOKEN)

        # THEN
        assert verifier.calls == [(GOOD_TOKEN, "register")]

    def test_a_missing_token_answers_the_same_as_a_rejected_one(self, client, fake_email):
        """
        GIVEN the bot check is on
        WHEN one request sends no token and another sends one the verifier rejects
        THEN both answer with the same status and the same body

        Any difference would tell a caller whether the check is switched on, and which
        half of it they failed.
        """
        # GIVEN
        enable_check(client)

        # WHEN
        absent = post_register(client, "absent@example.com")
        rejected = post_register(client, "rejected@example.com", "not-a-real-token")

        # THEN
        assert absent.status_code == rejected.status_code == 403
        assert absent.json() == rejected.json() == {"detail": TURNSTILE_REFUSED_DETAIL}

    @pytest.mark.parametrize(
        ("path", "payload"),
        [
            ("/api/v1/auth/verify-email", {"token": "unknown-token", "password": PASSWORD}),
            ("/api/v1/auth/reset-password", {"token": "unknown-token", "new_password": PASSWORD}),
        ],
    )
    def test_the_token_redemption_endpoints_stay_unguarded(self, client, path, payload):
        """
        GIVEN the bot check is on and would refuse every request
        WHEN an endpoint that redeems an emailed token is called
        THEN it answers on its own terms, not with the bot check's 403

        Holding a live emailed link is already evidence of a person, and the widget is
        not rendered on those pages, so guarding them would only break the round trip.
        """
        # GIVEN
        enable_check(client)

        # WHEN
        response = client.post(path, json=payload)

        # THEN
        assert response.status_code == 400
