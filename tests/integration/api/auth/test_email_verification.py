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

from api.auth.email_throttle import (
    DAILY_CAP,
    InMemoryEmailSendThrottle,
    get_verification_email_throttle,
)
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

    def test_taken_unverified_address_writes_nothing_and_mails_its_own_link(
        self, client, fake_email, unthrottled_email
    ):
        """A repeat signup leaves the account alone and gets a link of its own.

        The submission travels on the link it minted instead of being written to the
        account, so it takes effect only for whoever follows that link.
        """
        # GIVEN - an unverified account someone registered first
        register(client, "contested@example.com", password=DEFAULT_TEST_PASSWORD)
        first_link = _verify_token(fake_email)

        # WHEN - the address is registered again with different credentials and name
        response = register(
            client, "contested@example.com", password=OTHER_PASSWORD, first_name="Later"
        )

        # THEN - still one account, still carrying what the first submission stored
        assert response.status_code == 202
        accounts = stored_accounts(client, "contested@example.com")
        assert len(accounts) == 1
        assert accounts[0]["first_name"] == "Test"

        # AND - a second link was mailed and the first one is still alive
        assert len(fake_email.verification_calls) == 2
        second_link = _verify_token(fake_email)
        assert second_link != first_link

        # AND - following the second link applies the second submission
        assert (
            client.post("/api/v1/auth/verify-email", json={"token": second_link}).status_code == 200
        )
        assert stored_accounts(client, "contested@example.com")[0]["first_name"] == "Later"
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


class TestSignupTakeoverAttempts:
    """A stranger submitting a pending address cannot decide what its link opens.

    Both orderings are covered. Registering first is the familiar one, and registering
    *after* the owner is the dangerous one: a stored last-write-wins password would let
    anyone overwrite a pending signup and simply wait for the owner to click the link
    they already have.
    """

    def test_the_owners_own_link_opens_the_account_on_the_owners_terms(
        self, client, fake_email, unthrottled_email
    ):
        """A later submission does not change what an already-mailed link activates."""
        # GIVEN - the rightful owner signs up and gets their link
        register(client, "target@example.com", password=DEFAULT_TEST_PASSWORD)
        owners_link = _verify_token(fake_email)

        # WHEN - a stranger submits the same address with a password of their choosing,
        # then the owner follows the link they were sent
        register(client, "target@example.com", password=OTHER_PASSWORD, first_name="Stranger")
        activated = client.post("/api/v1/auth/verify-email", json={"token": owners_link})

        # THEN - the account is live on the owner's password, not the stranger's
        assert activated.status_code == 200
        assert _login(client, "target@example.com", DEFAULT_TEST_PASSWORD).status_code == 200
        assert _login(client, "target@example.com", OTHER_PASSWORD).status_code == 401
        assert stored_accounts(client, "target@example.com")[0]["first_name"] == "Test"

    def test_a_suppressed_submission_cannot_ride_the_owners_link_either(self, client, fake_email):
        """Throttling a stranger's mail must not leave their password behind.

        The quiet variant of the same attack: the stranger's second submission is
        suppressed by the per-address budget, so nothing lands in the owner's inbox to
        arouse suspicion, and the owner activates with the link they already had.
        """
        # GIVEN - the owner signs up, then a stranger submits twice; the second send is
        # suppressed by the per-address cooldown the first one started
        register(client, "quiet@example.com", password=DEFAULT_TEST_PASSWORD)
        owners_link = _verify_token(fake_email)
        register(client, "quiet@example.com", password=OTHER_PASSWORD)
        register(client, "quiet@example.com", password="ThirdChoice42!")
        assert len(fake_email.verification_calls) == 2  # the owner's, and one stranger send

        # WHEN
        activated = client.post("/api/v1/auth/verify-email", json={"token": owners_link})

        # THEN
        assert activated.status_code == 200
        assert _login(client, "quiet@example.com", DEFAULT_TEST_PASSWORD).status_code == 200
        assert _login(client, "quiet@example.com", OTHER_PASSWORD).status_code == 401
        assert _login(client, "quiet@example.com", "ThirdChoice42!").status_code == 401

    def test_a_link_minted_before_activation_cannot_reopen_a_live_account(
        self, client, fake_email, unthrottled_email
    ):
        """An unspent link goes dead the moment the address is confirmed.

        It carries a password, so redeeming one after activation would rewrite the
        credentials of an account somebody is already using.
        """
        # GIVEN - the owner's link and a stranger's link, both live
        register(client, "held@example.com", password=DEFAULT_TEST_PASSWORD)
        owners_link = _verify_token(fake_email)
        register(client, "held@example.com", password=OTHER_PASSWORD)
        strangers_link = _verify_token(fake_email)
        assert client.post(
            "/api/v1/auth/verify-email", json={"token": owners_link}
        ).status_code == (200)

        # WHEN - the stranger tries theirs afterwards
        response = client.post("/api/v1/auth/verify-email", json={"token": strangers_link})

        # THEN - refused, with the same opaque answer an unknown token gets
        assert response.status_code == 400
        assert response.content == (
            client.post("/api/v1/auth/verify-email", json={"token": "garbage-token"}).content
        )
        assert _login(client, "held@example.com", DEFAULT_TEST_PASSWORD).status_code == 200
        assert _login(client, "held@example.com", OTHER_PASSWORD).status_code == 401


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
        """The link a resend mails works, and it does not retire the earlier one.

        Retiring outstanding links is how one submitter would kill another's pending
        activation link, so a resend adds a link rather than replacing one. Whichever
        is followed first activates the address; the rest go dead with it.
        """
        # GIVEN
        register(client, "again@example.com")
        first = _verify_token(fake_email)

        # WHEN
        client.post("/api/v1/auth/resend-verification", json={"email": "again@example.com"})
        second = _verify_token(fake_email)

        # THEN
        assert second != first
        assert client.post("/api/v1/auth/verify-email", json={"token": second}).status_code == 200
        assert client.post("/api/v1/auth/verify-email", json={"token": first}).status_code == 400

    def test_a_resent_link_leaves_the_stored_credentials_alone(
        self, client, fake_email, unthrottled_email
    ):
        """A resend carries no submission, so following it changes no password.

        The endpoint takes an address and nothing else, so it has no submission to
        bind. Making it re-apply whatever the account happens to hold would undo a
        password reset the same person had just completed.
        """
        # GIVEN - an account that reset its password while still unactivated
        register(client, "reset-first@example.com", password=DEFAULT_TEST_PASSWORD)
        client.post("/api/v1/auth/forgot-password", json={"email": "reset-first@example.com"})
        reset_token = fake_email.calls[-1]["reset_url"].split("token=")[1]
        assert client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "new_password": OTHER_PASSWORD},
        ).status_code == (204)

        # WHEN - a resent link is followed
        client.post("/api/v1/auth/resend-verification", json={"email": "reset-first@example.com"})
        resent = _verify_token(fake_email)
        assert client.post("/api/v1/auth/verify-email", json={"token": resent}).status_code == 200

        # THEN - the password from the reset is the one that works
        assert _login(client, "reset-first@example.com", OTHER_PASSWORD).status_code == 200
        assert _login(client, "reset-first@example.com", DEFAULT_TEST_PASSWORD).status_code == 401


class TestEmailThrottling:
    """One per-address budget covers repeat signups, notices, and resends."""

    def test_a_rapid_second_send_is_suppressed_without_changing_the_response(
        self, client, fake_email
    ):
        """A resend spends the address's allowance; the next one is suppressed."""
        # GIVEN - a registered account, its first resend already sent
        register(client, "flooded@example.com")
        first = client.post(
            "/api/v1/auth/resend-verification", json={"email": "flooded@example.com"}
        )
        assert len(fake_email.verification_calls) == 2

        # WHEN - another resend follows immediately
        second = client.post(
            "/api/v1/auth/resend-verification", json={"email": "flooded@example.com"}
        )

        # THEN - identical answers, and nothing more reached the inbox
        assert first.status_code == second.status_code == 202
        assert first.content == second.content
        assert len(fake_email.verification_calls) == 2

    def test_repeated_signups_cannot_flood_a_live_account_with_notices(self, client, fake_email):
        """Submitting a victim's address in a loop does not mail them repeatedly."""
        # GIVEN - an activated account
        register_verified(client, "victim@example.com")

        # WHEN - the address is submitted twice more
        first = register(client, "victim@example.com")
        second = register(client, "victim@example.com")

        # THEN - one notice for the two attempts, and both answers are the same
        assert first.status_code == second.status_code == 202
        assert first.content == second.content
        assert len(fake_email.notice_calls) == 1

    def test_a_first_signup_is_never_suppressed(self, client, fake_email):
        """Creating an account always mails its link, whatever the budget says.

        The branch that creates an account fires at most once per address, so it can
        flood nothing. Charging it to the shared budget lets an unauthenticated caller
        exhaust an address's allowance with resend requests before its owner has even
        signed up: the signup then answers 202, creates the account, mails nothing, and
        leaves a person who cannot log in and cannot get a link.
        """
        # GIVEN - a stranger burns the whole daily budget for an address with no account
        for _ in range(DAILY_CAP):
            client.post("/api/v1/auth/resend-verification", json={"email": "never@example.com"})

        # WHEN - the real person signs up
        response = register(client, "never@example.com")

        # THEN - their activation link goes out, and it works
        assert response.status_code == 202
        assert len(fake_email.verification_calls) == 1
        assert fake_email.verification_calls[0]["to_email"] == "never@example.com"
        token = _verify_token(fake_email)
        assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200

    def test_a_resend_with_nothing_to_send_spends_nothing(self, client, fake_email):
        """A request naming an address with no pending signup leaves its budget intact.

        Nobody has to authenticate to name someone else's address here, so a request
        that sends no mail must not be able to spend the allowance a real one needs.
        """
        # GIVEN - an activated account, and a stranger emptying the daily budget at it
        register_verified(client, "settled@example.com")
        for _ in range(DAILY_CAP):
            client.post("/api/v1/auth/resend-verification", json={"email": "settled@example.com"})
        assert len(fake_email.verification_calls) == 1  # only the original signup

        # WHEN - someone submits that address to the signup form
        register(client, "settled@example.com")

        # THEN - the owner is still told about it
        assert len(fake_email.notice_calls) == 1
