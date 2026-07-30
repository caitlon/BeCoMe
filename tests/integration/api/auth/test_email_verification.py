"""Integration tests for the deferred-activation registration flow.

Covers the three registration branches, the login gate, and the two endpoints that
finish the round trip. The recording ``fake_email`` sender from the auth conftest holds
the only copy of each raw token, exactly as a real mailbox would.
"""

import hashlib
from datetime import timedelta

import dns.resolver
import pytest
from sqlmodel import select

from api.auth.email_throttle import InMemoryEmailSendThrottle, get_verification_email_throttle
from api.auth.login_throttle import InMemoryLoginThrottle, get_login_throttle
from api.db.models import EmailVerificationToken, User
from api.db.utils import utc_now
from api.dependencies import get_email_address_policy, get_email_service
from api.middleware.exception_handlers import EMAIL_NOT_VERIFIED_DETAIL
from api.services.email.base import EmailSender
from api.services.email.exceptions import EmailSendError
from api.services.email_policy import EmailAddressPolicy, InMemoryDomainVerdictCache
from api.services.user_cache import CachedUserData, get_user_cache
from tests.integration.api.conftest import (
    app_session,
    mark_email_verified,
    register,
    register_verified,
    stored_accounts,
)
from tests.shared.helpers import DEFAULT_TEST_PASSWORD

OTHER_PASSWORD = "SomeOtherPass99!"

# From the vendored blocklist in api/data/disposable_email_domains.txt.
DISPOSABLE_ADDRESS = "throwaway@mailinator.com"


def _login(client, email: str, password: str = DEFAULT_TEST_PASSWORD):
    """Attempt a login and return the raw response."""
    return client.post("/api/v1/auth/login", data={"username": email, "password": password})


def _verify_token(sender) -> str:
    """Extract the raw activation token from the last captured verification URL."""
    return sender.verification_calls[-1]["verify_url"].split("token=")[1]


@pytest.fixture
def unthrottled_email(client):
    """Lift the per-address email cooldown for tests that need two sends in a row.

    The cooldown is one minute, so back-to-back sends to one address are suppressed by
    design. Tests about which branch mails what override it; the throttle's own
    behaviour is asserted in TestEmailThrottling.
    """
    client.app.dependency_overrides[get_verification_email_throttle] = lambda: (
        InMemoryEmailSendThrottle(cooldown_seconds=0)
    )


class TestRegistrationBranches:
    """The three states an address can be in all answer the same way."""

    def test_free_address_creates_an_unverified_user_and_mails_a_link(self, client, fake_email):
        """A free address gets an account that cannot log in yet, plus an activation link."""
        # WHEN
        response = register(client, "fresh@example.com")

        # THEN
        assert response.status_code == 202
        accounts = stored_accounts(client, "fresh@example.com")
        assert len(accounts) == 1
        assert accounts[0]["email_verified_at"] is None

        # AND - exactly one activation link went to that address, and no notice
        assert len(fake_email.verification_calls) == 1
        assert fake_email.verification_calls[0]["to_email"] == "fresh@example.com"
        assert "/verify-email?token=" in fake_email.verification_calls[0]["verify_url"]
        assert fake_email.notice_calls == []

    def test_taken_unverified_address_is_overwritten_and_relinked(
        self, client, fake_email, unthrottled_email
    ):
        """A repeat signup on an unverified address replaces the credentials it holds.

        Nobody has proven control of the mailbox yet, so letting the first submission
        stand would let an attacker pre-register a victim's address and know the
        password of the account the victim later activates.
        """
        # GIVEN - an unverified account someone else registered first
        register(client, "contested@example.com", password=DEFAULT_TEST_PASSWORD)
        first_link = _verify_token(fake_email)

        # WHEN - the address is registered again with different credentials and name
        response = register(
            client, "contested@example.com", password=OTHER_PASSWORD, first_name="Rightful"
        )

        # THEN - still one account, now carrying the newer submission
        assert response.status_code == 202
        accounts = stored_accounts(client, "contested@example.com")
        assert len(accounts) == 1
        assert accounts[0]["first_name"] == "Rightful"

        # AND - a fresh link was mailed and the first one is dead
        assert len(fake_email.verification_calls) == 2
        second_link = _verify_token(fake_email)
        assert second_link != first_link
        assert client.post("/api/v1/auth/verify-email", json={"token": first_link}).status_code == (
            400
        )

        # AND - activating with the newer link opens the account with the newer password
        assert (
            client.post("/api/v1/auth/verify-email", json={"token": second_link}).status_code == 200
        )
        assert _login(client, "contested@example.com", DEFAULT_TEST_PASSWORD).status_code == 401
        assert _login(client, "contested@example.com", OTHER_PASSWORD).status_code == 200

    def test_taken_verified_address_changes_nothing_and_mails_a_notice(
        self, client, fake_email, unthrottled_email
    ):
        """A signup on a live account leaves it alone and tells its owner."""
        # GIVEN - an activated account
        register_verified(client, "owner@example.com", password=DEFAULT_TEST_PASSWORD)
        created_id = stored_accounts(client, "owner@example.com")[0]["id"]
        sends_so_far = len(fake_email.verification_calls)

        # WHEN - someone registers the same address with their own password
        response = register(client, "owner@example.com", password=OTHER_PASSWORD, first_name="Imp")

        # THEN - the account is untouched
        assert response.status_code == 202
        accounts = stored_accounts(client, "owner@example.com")
        assert len(accounts) == 1
        assert accounts[0]["id"] == created_id
        assert accounts[0]["first_name"] == "Test"
        assert _login(client, "owner@example.com", OTHER_PASSWORD).status_code == 401
        assert _login(client, "owner@example.com", DEFAULT_TEST_PASSWORD).status_code == 200

        # AND - the owner got a notice, never an activation link an attacker could use
        assert len(fake_email.verification_calls) == sends_so_far
        assert len(fake_email.notice_calls) == 1
        assert fake_email.notice_calls[0]["to_email"] == "owner@example.com"

    def test_notice_carries_a_static_reset_link_with_no_token(
        self, client, fake_email, unthrottled_email
    ):
        """The notice points at the reset page, it never mints a live reset token.

        An unauthenticated registration attempt that could mail a working reset link
        would let anyone flood a victim with usable password resets.
        """
        # GIVEN
        register_verified(client, "static@example.com")

        # WHEN
        register(client, "static@example.com")

        # THEN
        notice = fake_email.notice_calls[0]
        assert notice["reset_url"].endswith("/forgot-password")
        assert notice["login_url"].endswith("/login")
        assert "token" not in notice["reset_url"]

    def test_all_three_branches_answer_byte_for_byte_the_same(self, client, fake_email):
        """Status and body are identical for a free, an unverified, and a live address."""
        # GIVEN - one address in each state
        register(client, "pending@example.com")
        register_verified(client, "active@example.com")

        # WHEN
        free = register(client, "brandnew@example.com")
        unverified = register(client, "pending@example.com")
        verified = register(client, "active@example.com")

        # THEN
        assert free.status_code == unverified.status_code == verified.status_code == 202
        assert free.content == unverified.content == verified.content

    def test_send_failure_does_not_change_the_response(self, client):
        """A provider outage still answers 202: an error would betray which branch ran."""

        # GIVEN - a sender that fails on every send
        class FailingEmailSender(EmailSender):
            """Simulate a provider that fails on every send."""

            async def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
                """Raise to simulate a provider failure."""
                raise EmailSendError("send failed")

            async def send_email_verification(self, *, to_email: str, verify_url: str) -> None:
                """Raise to simulate a provider failure."""
                raise EmailSendError("send failed")

            async def send_registration_attempt_notice(
                self, *, to_email: str, login_url: str, reset_url: str
            ) -> None:
                """Raise to simulate a provider failure."""
                raise EmailSendError("send failed")

        client.app.dependency_overrides[get_email_service] = lambda: FailingEmailSender()

        # WHEN
        response = register(client, "unreachable@example.com")

        # THEN - the account still exists, waiting for a resend
        assert response.status_code == 202
        assert stored_accounts(client, "unreachable@example.com")


class TestRegistrationAddressPolicy:
    """The address policy rejects before anything reaches the database."""

    def test_disposable_domain_is_rejected_without_creating_an_account(self, client, fake_email):
        """A known throwaway provider is refused with 400 and leaves no row behind."""
        # WHEN
        response = register(client, DISPOSABLE_ADDRESS)

        # THEN
        assert response.status_code == 400
        assert stored_accounts(client, DISPOSABLE_ADDRESS) == []
        assert fake_email.verification_calls == []

    def test_unresolvable_domain_is_rejected_without_creating_an_account(self, client, fake_email):
        """A domain the resolver reports as nonexistent is refused with 400."""

        # GIVEN - a resolver that reports every domain as missing
        class NxdomainResolver:
            """Resolver stub that answers NXDOMAIN for every query."""

            async def resolve(self, *_args, **_kwargs):
                """Raise NXDOMAIN, the resolver's definitive "no such domain"."""
                raise dns.resolver.NXDOMAIN

        client.app.dependency_overrides[get_email_address_policy] = lambda: EmailAddressPolicy(
            resolver=NxdomainResolver(),
            cache=InMemoryDomainVerdictCache(),
            disposable_check_enabled=False,
        )

        # WHEN
        response = register(client, "someone@no-such-domain.example")

        # THEN
        assert response.status_code == 400
        assert stored_accounts(client, "someone@no-such-domain.example") == []
        assert fake_email.verification_calls == []


class TestLoginGate:
    """An unverified account cannot log in at all."""

    def test_login_before_verification_is_refused_with_403(self, client, fake_email):
        """The right password on an unverified account is refused, distinguishably."""
        # GIVEN
        register(client, "waiting@example.com")

        # WHEN
        response = _login(client, "waiting@example.com")

        # THEN - a 403 the SPA can tell apart from every other 403
        assert response.status_code == 403
        assert response.json()["detail"] == EMAIL_NOT_VERIFIED_DETAIL

    def test_login_after_verification_succeeds(self, client, fake_email):
        """Redeeming the activation link opens the same account for login."""
        # GIVEN
        register(client, "waiting@example.com")
        token = _verify_token(fake_email)

        # WHEN
        verified = client.post("/api/v1/auth/verify-email", json={"token": token})

        # THEN
        assert verified.status_code == 200
        assert _login(client, "waiting@example.com").status_code == 200

    def test_wrong_password_on_an_unverified_account_still_returns_401(self, client, fake_email):
        """The gate never runs before the password check, so it cannot become an oracle.

        A 403 for a wrong password would tell an unauthenticated caller that the
        address has an account -- exactly what the 401 hides.
        """
        # GIVEN
        register(client, "waiting@example.com")

        # WHEN
        response = _login(client, "waiting@example.com", "TotallyWrong123!")

        # THEN
        assert response.status_code == 401

    def test_correct_password_on_an_unverified_account_is_not_a_failed_attempt(
        self, client, fake_email
    ):
        """Being unverified must not burn the account's login-lockout budget."""
        # GIVEN - a lockout that trips after two failures
        throttle = InMemoryLoginThrottle(max_failures=2, window_seconds=3600)
        client.app.dependency_overrides[get_login_throttle] = lambda: throttle
        try:
            register(client, "patient@example.com")

            # WHEN - more correct-password attempts than the lockout threshold
            for _ in range(3):
                assert _login(client, "patient@example.com").status_code == 403

            # THEN - activating still lets the owner in; nothing was counted as a failure
            mark_email_verified(client, "patient@example.com")
            assert _login(client, "patient@example.com").status_code == 200
        finally:
            client.app.dependency_overrides.pop(get_login_throttle, None)


class TestVerifyEmailEndpoint:
    """POST /api/v1/auth/verify-email."""

    def test_full_round_trip(self, client, fake_email):
        """Register, follow the emailed link, then log in."""
        # GIVEN
        register(client, "roundtrip@example.com")
        token = _verify_token(fake_email)

        # WHEN
        response = client.post("/api/v1/auth/verify-email", json={"token": token})

        # THEN
        assert response.status_code == 200
        assert stored_accounts(client, "roundtrip@example.com")[0]["email_verified_at"] is not None
        assert _login(client, "roundtrip@example.com").status_code == 200

    def test_unknown_reused_and_expired_tokens_give_the_same_answer(self, client, fake_email):
        """No response tells a caller which kind of bad token they hold."""
        # GIVEN - a spent token, and an expired one written straight into the table
        register(client, "tokens@example.com")
        spent = _verify_token(fake_email)
        assert client.post("/api/v1/auth/verify-email", json={"token": spent}).status_code == 200

        expired_raw = "expired-integration-token"
        user_id = stored_accounts(client, "tokens@example.com")[0]["id"]
        with app_session(client) as session:
            session.add(
                EmailVerificationToken(
                    user_id=user_id,
                    token_hash=hashlib.sha256(expired_raw.encode()).hexdigest(),
                    expires_at=utc_now() - timedelta(minutes=1),
                )
            )
            session.commit()

        # WHEN
        unknown = client.post("/api/v1/auth/verify-email", json={"token": "garbage-token"})
        reused = client.post("/api/v1/auth/verify-email", json={"token": spent})
        expired = client.post("/api/v1/auth/verify-email", json={"token": expired_raw})

        # THEN
        assert unknown.status_code == reused.status_code == expired.status_code == 400
        assert unknown.content == reused.content == expired.content

    def test_verification_drops_the_cached_profile(self, client, fake_email):
        """Activation invalidates the cached snapshot instead of leaving it stale.

        The user cache holds a profile for a minute, so a snapshot taken before
        activation would keep reporting the account as unverified after it.
        """
        # GIVEN - a registered account whose pre-activation snapshot is cached
        register(client, "cached@example.com")
        token = _verify_token(fake_email)
        with app_session(client) as session:
            user = session.exec(select(User).where(User.email == "cached@example.com")).first()
            user_id = user.id
            get_user_cache().set(CachedUserData.from_user(user), 60)
        assert get_user_cache().get(user_id) is not None

        # WHEN
        response = client.post("/api/v1/auth/verify-email", json={"token": token})

        # THEN
        assert response.status_code == 200
        assert get_user_cache().get(user_id) is None


class TestResendVerification:
    """POST /api/v1/auth/resend-verification."""

    def test_answers_identically_for_unknown_unverified_and_verified(
        self, client, fake_email, unthrottled_email
    ):
        """The endpoint reveals nothing about which addresses have accounts."""
        # GIVEN - one unverified and one activated account
        register(client, "pending@example.com")
        register_verified(client, "active@example.com")

        # WHEN
        unknown = client.post(
            "/api/v1/auth/resend-verification", json={"email": "ghost@example.com"}
        )
        pending = client.post(
            "/api/v1/auth/resend-verification", json={"email": "pending@example.com"}
        )
        active = client.post(
            "/api/v1/auth/resend-verification", json={"email": "active@example.com"}
        )

        # THEN
        assert unknown.status_code == pending.status_code == active.status_code == 202
        assert unknown.content == pending.content == active.content

    def test_sends_only_for_an_account_still_waiting(self, client, fake_email, unthrottled_email):
        """Only the unverified address triggers an actual send."""
        # GIVEN
        register(client, "pending@example.com")
        register_verified(client, "active@example.com")
        sends_after_setup = len(fake_email.verification_calls)

        # WHEN
        client.post("/api/v1/auth/resend-verification", json={"email": "ghost@example.com"})
        client.post("/api/v1/auth/resend-verification", json={"email": "active@example.com"})
        assert len(fake_email.verification_calls) == sends_after_setup

        client.post("/api/v1/auth/resend-verification", json={"email": "pending@example.com"})

        # THEN
        assert len(fake_email.verification_calls) == sends_after_setup + 1
        assert fake_email.verification_calls[-1]["to_email"] == "pending@example.com"

    def test_a_resent_link_activates_the_account(self, client, fake_email, unthrottled_email):
        """The link a resend mails works, and the one it replaced does not."""
        # GIVEN
        register(client, "again@example.com")
        first = _verify_token(fake_email)

        # WHEN
        client.post("/api/v1/auth/resend-verification", json={"email": "again@example.com"})
        second = _verify_token(fake_email)

        # THEN
        assert second != first
        assert client.post("/api/v1/auth/verify-email", json={"token": first}).status_code == 400
        assert client.post("/api/v1/auth/verify-email", json={"token": second}).status_code == 200


class TestEmailThrottling:
    """One per-address budget covers registration, notices, and resends."""

    def test_a_rapid_second_send_is_suppressed_without_changing_the_response(
        self, client, fake_email
    ):
        """Registration and resend share one budget, and suppression is invisible."""
        # GIVEN - registering already spent this address's allowance
        register(client, "flooded@example.com")
        assert len(fake_email.verification_calls) == 1

        # WHEN - two resends follow immediately
        first = client.post(
            "/api/v1/auth/resend-verification", json={"email": "flooded@example.com"}
        )
        second = client.post(
            "/api/v1/auth/resend-verification", json={"email": "flooded@example.com"}
        )

        # THEN - identical answers, and nothing more reached the inbox
        assert first.status_code == second.status_code == 202
        assert first.content == second.content
        assert len(fake_email.verification_calls) == 1

    def test_repeated_signups_cannot_flood_a_live_account_with_notices(self, client, fake_email):
        """Submitting a victim's address in a loop does not mail them repeatedly."""
        # GIVEN - an activated account whose allowance the registration send consumed
        register_verified(client, "victim@example.com")

        # WHEN - the address is submitted twice more
        first = register(client, "victim@example.com")
        second = register(client, "victim@example.com")

        # THEN
        assert first.status_code == second.status_code == 202
        assert first.content == second.content
        assert fake_email.notice_calls == []
