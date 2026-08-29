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
from api.auth.login_throttle import (
    InMemoryLoginThrottle,
    get_activation_throttle,
    get_login_throttle,
)
from api.auth.password import hash_password
from api.db.models import EmailVerificationToken, User
from api.db.utils import utc_now
from api.dependencies import get_email_address_policy, get_email_service
from api.middleware.exception_handlers import (
    EMAIL_NOT_VERIFIED_DETAIL,
    VERIFICATION_PASSWORD_MISMATCH_DETAIL,
)
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


def _activate(client, token: str, password: str = DEFAULT_TEST_PASSWORD):
    """Post an activation token together with the password it should open on."""
    return client.post("/api/v1/auth/verify-email", json={"token": token, "password": password})


def _resend(client, email: str, password: str = DEFAULT_TEST_PASSWORD):
    """Ask for a fresh activation link bound to the given password."""
    return client.post(
        "/api/v1/auth/resend-verification", json={"email": email, "password": password}
    )


def _mails_to(sender, email: str) -> list[dict]:
    """Return every email of any kind that went to one address."""
    return [
        call
        for call in sender.verification_calls + sender.notice_calls
        if call["to_email"] == email
    ]


def _budget(client, *, cooldown_seconds: int = 0, daily_cap: int = DAILY_CAP) -> None:
    """Install a per-address email budget with known limits for one test.

    One instance for the whole test, not one per request: the override is called on
    every request, so returning a fresh throttle each time would hand every request an
    empty budget and quietly assert nothing.
    """
    throttle = InMemoryEmailSendThrottle(cooldown_seconds=cooldown_seconds, daily_cap=daily_cap)
    client.app.dependency_overrides[get_verification_email_throttle] = lambda: throttle


@pytest.fixture
def unthrottled_email(client):
    """Lift the per-address email cooldown for tests that need two sends in a row.

    The cooldown is one minute, so back-to-back sends to one address are suppressed by
    design. Tests about which branch mails what override it; the throttle's own
    behaviour is asserted in TestEmailThrottling.
    """
    _budget(client, cooldown_seconds=0)


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

        # AND: exactly one activation link went to that address, and no notice
        assert len(fake_email.verification_calls) == 1
        assert fake_email.verification_calls[0]["to_email"] == "fresh@example.com"
        assert "/verify-email?token=" in fake_email.verification_calls[0]["verify_url"]
        assert fake_email.notice_calls == []

    def test_taken_unverified_address_writes_nothing_and_mails_its_own_link(
        self, client, fake_email, unthrottled_email
    ):
        """A repeat signup leaves the account alone and gets a link of its own.

        The submission travels on the link it minted instead of being written to the
        account, so it takes effect only for whoever follows that link with the
        password behind it.
        """
        # GIVEN: an unverified account someone registered first
        register(client, "contested@example.com", password=DEFAULT_TEST_PASSWORD)
        first_link = _verify_token(fake_email)

        # WHEN: the address is registered again with different credentials and name
        response = register(
            client, "contested@example.com", password=OTHER_PASSWORD, first_name="Later"
        )

        # THEN: still one account, still carrying what the first submission stored
        assert response.status_code == 202
        accounts = stored_accounts(client, "contested@example.com")
        assert len(accounts) == 1
        assert accounts[0]["first_name"] == "Test"

        # AND: a second link was mailed and the first one is still alive
        assert len(fake_email.verification_calls) == 2
        second_link = _verify_token(fake_email)
        assert second_link != first_link

        # AND: following the second link with its own password applies that submission
        assert _activate(client, second_link, OTHER_PASSWORD).status_code == 200
        assert stored_accounts(client, "contested@example.com")[0]["first_name"] == "Later"
        assert _login(client, "contested@example.com", DEFAULT_TEST_PASSWORD).status_code == 401
        assert _login(client, "contested@example.com", OTHER_PASSWORD).status_code == 200

    def test_taken_verified_address_changes_nothing_and_mails_a_notice(
        self, client, fake_email, unthrottled_email
    ):
        """A signup on a live account leaves it alone and tells its owner."""
        # GIVEN: an activated account
        register_verified(client, "owner@example.com", password=DEFAULT_TEST_PASSWORD)
        created_id = stored_accounts(client, "owner@example.com")[0]["id"]
        sends_so_far = len(fake_email.verification_calls)

        # WHEN: someone registers the same address with their own password
        response = register(client, "owner@example.com", password=OTHER_PASSWORD, first_name="Imp")

        # THEN: the account is untouched
        assert response.status_code == 202
        accounts = stored_accounts(client, "owner@example.com")
        assert len(accounts) == 1
        assert accounts[0]["id"] == created_id
        assert accounts[0]["first_name"] == "Test"
        assert _login(client, "owner@example.com", OTHER_PASSWORD).status_code == 401
        assert _login(client, "owner@example.com", DEFAULT_TEST_PASSWORD).status_code == 200

        # AND: the owner got a notice, never an activation link an attacker could use
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
        # GIVEN: one address in each state
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

        # GIVEN: a sender that fails on every send
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

        # THEN: the account still exists, waiting for a resend
        assert response.status_code == 202
        assert stored_accounts(client, "unreachable@example.com")


class TestSignupTakeoverAttempts:
    """A stranger submitting a pending address cannot decide what its link opens.

    Both orderings are covered. Registering after the owner is the quieter one: a
    stored last-write-wins password would let anyone overwrite a pending signup and
    simply wait for the owner to click the link they already have. Registering *first*
    is the dangerous one: the stranger's link is then the only one in the victim's
    inbox, and it is the newest thing there, so the victim has every reason to click it.
    """

    def test_the_owners_own_link_opens_the_account_on_the_owners_terms(
        self, client, fake_email, unthrottled_email
    ):
        """A later submission does not change what an already-mailed link activates."""
        # GIVEN: the rightful owner signs up and gets their link
        register(client, "target@example.com", password=DEFAULT_TEST_PASSWORD)
        owners_link = _verify_token(fake_email)

        # WHEN: a stranger submits the same address with a password of their choosing,
        # then the owner follows the link they were sent
        register(client, "target@example.com", password=OTHER_PASSWORD, first_name="Stranger")
        activated = _activate(client, owners_link, DEFAULT_TEST_PASSWORD)

        # THEN: the account is live on the owner's password, not the stranger's
        assert activated.status_code == 200
        assert _login(client, "target@example.com", DEFAULT_TEST_PASSWORD).status_code == 200
        assert _login(client, "target@example.com", OTHER_PASSWORD).status_code == 401
        assert stored_accounts(client, "target@example.com")[0]["first_name"] == "Test"

    def test_the_victim_cannot_complete_a_link_a_stranger_pre_registered(
        self, client, fake_email, unthrottled_email
    ):
        """Attacker first: the only link in the victim's inbox is the attacker's.

        Nothing tells the victim that link is not theirs, since it arrives at their
        address from the real service. What stops it is the password: the victim types their
        own, the link carries the attacker's, and the account never opens.
        """
        # GIVEN: a stranger pre-registers the victim's address
        register(client, "victim@example.com", password=OTHER_PASSWORD, first_name="Stranger")
        strangers_link = _verify_token(fake_email)

        # WHEN: the victim clicks it and supplies the password they would have chosen
        refused = _activate(client, strangers_link, DEFAULT_TEST_PASSWORD)

        # THEN: refused, distinguishably from a broken link, and nothing was activated
        assert refused.status_code == 403
        assert refused.json()["detail"] == VERIFICATION_PASSWORD_MISMATCH_DETAIL
        assert stored_accounts(client, "victim@example.com")[0]["email_verified_at"] is None

        # AND: the stranger's password never becomes usable, before or after
        assert _login(client, "victim@example.com", OTHER_PASSWORD).status_code == 403
        assert _login(client, "victim@example.com", DEFAULT_TEST_PASSWORD).status_code == 401

    def test_the_victim_takes_the_address_back_by_registering_it_themselves(
        self, client, fake_email, unthrottled_email
    ):
        """Attacker first, then the victim signs up and follows their own link.

        The victim's submission mints its own link; following it with the victim's own
        password opens the account on the victim's terms and retires the stranger's.
        """
        # GIVEN: a stranger pre-registered the address
        register(client, "reclaim@example.com", password=OTHER_PASSWORD, first_name="Stranger")
        strangers_link = _verify_token(fake_email)

        # WHEN: the victim registers the same address and follows the link that mints
        register(client, "reclaim@example.com", password=DEFAULT_TEST_PASSWORD)
        victims_link = _verify_token(fake_email)
        activated = _activate(client, victims_link, DEFAULT_TEST_PASSWORD)

        # THEN: the account is theirs
        assert activated.status_code == 200
        assert stored_accounts(client, "reclaim@example.com")[0]["first_name"] == "Test"
        assert _login(client, "reclaim@example.com", DEFAULT_TEST_PASSWORD).status_code == 200
        assert _login(client, "reclaim@example.com", OTHER_PASSWORD).status_code == 401

        # AND: the stranger's link is dead, with the same opaque answer garbage gets
        stale = _activate(client, strangers_link, OTHER_PASSWORD)
        assert stale.status_code == 400
        assert stale.content == _activate(client, "garbage-token").content

    def test_a_suppressed_submission_cannot_ride_the_owners_link_either(self, client, fake_email):
        """Throttling a stranger's mail must not leave their password behind.

        The quiet variant of the same attack: the stranger's submission is suppressed
        by the per-address budget, so nothing lands in the owner's inbox to arouse
        suspicion, and the owner activates with the link they already had.
        """
        # GIVEN: the owner signs up, then a stranger submits twice; both sends are
        # suppressed by the per-address cooldown the signup started
        register(client, "quiet@example.com", password=DEFAULT_TEST_PASSWORD)
        owners_link = _verify_token(fake_email)
        register(client, "quiet@example.com", password=OTHER_PASSWORD)
        register(client, "quiet@example.com", password="ThirdChoice42!")
        assert len(fake_email.verification_calls) == 1  # the owner's, and nothing else

        # WHEN
        activated = _activate(client, owners_link, DEFAULT_TEST_PASSWORD)

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
        # GIVEN: the owner's link and a stranger's link, both live
        register(client, "held@example.com", password=DEFAULT_TEST_PASSWORD)
        owners_link = _verify_token(fake_email)
        register(client, "held@example.com", password=OTHER_PASSWORD)
        strangers_link = _verify_token(fake_email)
        assert _activate(client, owners_link, DEFAULT_TEST_PASSWORD).status_code == 200

        # WHEN: the stranger tries theirs afterwards, with the password it carries
        response = _activate(client, strangers_link, OTHER_PASSWORD)

        # THEN: refused, with the same opaque answer an unknown token gets
        assert response.status_code == 400
        assert response.content == _activate(client, "garbage-token").content
        assert _login(client, "held@example.com", DEFAULT_TEST_PASSWORD).status_code == 200
        assert _login(client, "held@example.com", OTHER_PASSWORD).status_code == 401

    def test_a_strangers_resend_cannot_produce_a_link_the_victim_can_complete(
        self, client, fake_email, unthrottled_email
    ):
        """A resend binds a password too, so it is no weaker than a repeat signup.

        An address-only resend minted a link with nothing to prove, which anyone
        receiving the mail could follow.
        """
        # GIVEN: the owner's pending signup, and a stranger asking for a "fresh" link
        register(client, "bound@example.com", password=DEFAULT_TEST_PASSWORD)
        _resend(client, "bound@example.com", OTHER_PASSWORD)
        strangers_link = _verify_token(fake_email)

        # WHEN: the owner follows it with their own password
        refused = _activate(client, strangers_link, DEFAULT_TEST_PASSWORD)

        # THEN: refused, and nothing was activated
        assert refused.status_code == 403
        assert stored_accounts(client, "bound@example.com")[0]["email_verified_at"] is None

        # AND: the stranger's password is not the account's either; the owner's is,
        # and it is still waiting on a link the owner can actually complete
        assert _login(client, "bound@example.com", OTHER_PASSWORD).status_code == 401
        assert _login(client, "bound@example.com", DEFAULT_TEST_PASSWORD).status_code == 403

    def test_a_resend_no_longer_opens_an_account_on_its_creators_password(
        self, client, fake_email, unthrottled_email
    ):
        """Reclaiming through a resend now opens the account on the resender's password.

        This is the accepted risk the address-only resend carried: a link it minted
        confirmed the address without touching the stored password, so activating an
        account somebody else had pre-registered opened it on *their* password.
        """
        # GIVEN: a stranger pre-registered the address
        register(client, "resent@example.com", password=OTHER_PASSWORD, first_name="Stranger")

        # WHEN: the real owner asks for a link, naming the password they want
        _resend(client, "resent@example.com", DEFAULT_TEST_PASSWORD)
        owners_link = _verify_token(fake_email)
        activated = _activate(client, owners_link, DEFAULT_TEST_PASSWORD)

        # THEN: the account is theirs, not the stranger's
        assert activated.status_code == 200
        assert _login(client, "resent@example.com", DEFAULT_TEST_PASSWORD).status_code == 200
        assert _login(client, "resent@example.com", OTHER_PASSWORD).status_code == 401


class TestActivationPasswordGuessing:
    """Holding a link buys a password oracle, capped by its own lockout.

    That lockout is namespaced apart from login's: guessing wrong here still spends
    from the login counter too (the combined bound across both endpoints is unchanged),
    but nothing that happens at /login ever counts against this one, or can trip it.
    """

    def test_repeated_mismatches_lock_the_account_out(self, client, fake_email):
        """Guessing against a link trips its own lockout, sized like the login one."""
        # GIVEN: independent lockouts that trip after two failures, and a live link
        activation_throttle = InMemoryLoginThrottle(max_failures=2, window_seconds=3600)
        login_throttle = InMemoryLoginThrottle(max_failures=2, window_seconds=3600)
        client.app.dependency_overrides[get_activation_throttle] = lambda: activation_throttle
        client.app.dependency_overrides[get_login_throttle] = lambda: login_throttle
        try:
            register(client, "guessed@example.com", password=DEFAULT_TEST_PASSWORD)
            token = _verify_token(fake_email)

            # WHEN: the password is guessed wrong up to the threshold
            assert _activate(client, token, "WrongGuess111!").status_code == 403
            assert _activate(client, token, "WrongGuess222!").status_code == 403

            # THEN: even the right password is refused now, and so is a login: each
            # mismatch spent from both counters
            locked = _activate(client, token, DEFAULT_TEST_PASSWORD)
            assert locked.status_code == 429
            assert _login(client, "guessed@example.com").status_code == 429
            assert stored_accounts(client, "guessed@example.com")[0]["email_verified_at"] is None
        finally:
            client.app.dependency_overrides.pop(get_activation_throttle, None)
            client.app.dependency_overrides.pop(get_login_throttle, None)

    def test_locking_out_one_token_leaves_a_different_token_usable(
        self, client, fake_email, unthrottled_email
    ):
        """Burning one token's budget must not lock a distinct token for the account.

        The counter keys on the token's hash, not the account, so a token obtained
        without ongoing mailbox access, forwarded or intercepted, however it got out,
        can be burned without denying the owner a different, freshly resent link. A
        bucket shared by every token would let that one token deny every other one,
        which is a narrower instance of the same denial the login/activation split
        above already guards against.
        """
        # GIVEN: two live tokens for one account, and a lockout that trips after two
        # failures
        activation_throttle = InMemoryLoginThrottle(max_failures=2, window_seconds=3600)
        client.app.dependency_overrides[get_activation_throttle] = lambda: activation_throttle
        try:
            register(client, "twotokens@example.com", password=DEFAULT_TEST_PASSWORD)
            first = _verify_token(fake_email)
            _resend(client, "twotokens@example.com", OTHER_PASSWORD)
            second = _verify_token(fake_email)
            assert second != first

            # WHEN: the first token's budget is burned by repeated wrong guesses
            assert _activate(client, first, "WrongGuess111!").status_code == 403
            assert _activate(client, first, "WrongGuess222!").status_code == 403
            assert _activate(client, first, DEFAULT_TEST_PASSWORD).status_code == 429

            # THEN: the second, distinct token for the same account still activates
            assert _activate(client, second, OTHER_PASSWORD).status_code == 200
        finally:
            client.app.dependency_overrides.pop(get_activation_throttle, None)

    def test_failed_logins_do_not_block_the_victims_own_activation(self, client, fake_email):
        """A run of failed /login attempts must not deny someone their own activation.

        The login throttle is writable by anyone who merely knows the address, with no
        link required. Gating verify-email on it would let that unauthenticated caller
        lock out an activation they never touched.
        """
        # GIVEN: a live activation link, and enough wrong logins to lock the login
        # throttle for the same account
        login_throttle = InMemoryLoginThrottle(max_failures=2, window_seconds=3600)
        client.app.dependency_overrides[get_login_throttle] = lambda: login_throttle
        try:
            register(client, "targeted@example.com", password=DEFAULT_TEST_PASSWORD)
            token = _verify_token(fake_email)
            for _ in range(2):
                assert _login(client, "targeted@example.com", "WrongGuess111!").status_code == 401
            assert _login(client, "targeted@example.com").status_code == 429

            # WHEN: the victim activates with the correct password anyway
            activated = _activate(client, token, DEFAULT_TEST_PASSWORD)

            # THEN: the login lockout never touched activation
            assert activated.status_code == 200
        finally:
            client.app.dependency_overrides.pop(get_login_throttle, None)

    def test_a_mismatch_also_counts_against_the_login_throttle(self, client, fake_email):
        """Guessing wrong at activation still spends from the login budget too.

        Splitting the two lockouts must not double the total guessing budget: a wrong
        guess here is, in the same act, spending down the budget that would otherwise
        cover /login guesses against the same account.
        """
        # GIVEN: a login lockout that trips after two failures
        login_throttle = InMemoryLoginThrottle(max_failures=2, window_seconds=3600)
        client.app.dependency_overrides[get_login_throttle] = lambda: login_throttle
        try:
            register(client, "shared@example.com", password=DEFAULT_TEST_PASSWORD)
            token = _verify_token(fake_email)

            # WHEN: one wrong guess at activation, then one wrong guess at login
            assert _activate(client, token, "WrongGuess111!").status_code == 403
            assert _login(client, "shared@example.com", "WrongGuess222!").status_code == 401

            # THEN: together they already spent the login budget
            assert _login(client, "shared@example.com").status_code == 429
        finally:
            client.app.dependency_overrides.pop(get_login_throttle, None)

    def test_a_bad_token_never_reaches_either_lockout(self, client, fake_email):
        """An unknown token answers before any account is known, so neither is charged.

        Charging one would mean an unauthenticated caller could lock an account out by
        posting garbage, and there would be no account to charge in the first place.
        """
        # GIVEN
        activation_throttle = InMemoryLoginThrottle(max_failures=1, window_seconds=3600)
        login_throttle = InMemoryLoginThrottle(max_failures=1, window_seconds=3600)
        client.app.dependency_overrides[get_activation_throttle] = lambda: activation_throttle
        client.app.dependency_overrides[get_login_throttle] = lambda: login_throttle
        try:
            register_verified(client, "untouched@example.com")

            # WHEN
            for _ in range(3):
                assert _activate(client, "garbage-token").status_code == 400

            # THEN: neither counter was charged, so login still works on the first try
            assert _login(client, "untouched@example.com").status_code == 200
        finally:
            client.app.dependency_overrides.pop(get_activation_throttle, None)
            client.app.dependency_overrides.pop(get_login_throttle, None)


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

        # GIVEN: a resolver that reports every domain as missing
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

        # THEN: a 403 the SPA can tell apart from every other 403
        assert response.status_code == 403
        assert response.json()["detail"] == EMAIL_NOT_VERIFIED_DETAIL

    def test_login_after_verification_succeeds(self, client, fake_email):
        """Redeeming the activation link opens the same account for login."""
        # GIVEN
        register(client, "waiting@example.com")
        token = _verify_token(fake_email)

        # WHEN
        verified = _activate(client, token)

        # THEN
        assert verified.status_code == 200
        assert _login(client, "waiting@example.com").status_code == 200

    def test_wrong_password_on_an_unverified_account_still_returns_401(self, client, fake_email):
        """The gate never runs before the password check, so it cannot become an oracle.

        A 403 for a wrong password would tell an unauthenticated caller that the
        address has an account, which is exactly what the 401 hides.
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
        # GIVEN: a lockout that trips after two failures
        throttle = InMemoryLoginThrottle(max_failures=2, window_seconds=3600)
        client.app.dependency_overrides[get_login_throttle] = lambda: throttle
        try:
            register(client, "patient@example.com")

            # WHEN: more correct-password attempts than the lockout threshold
            for _ in range(3):
                assert _login(client, "patient@example.com").status_code == 403

            # THEN: activating still lets the owner in; nothing was counted as a failure
            mark_email_verified(client, "patient@example.com")
            assert _login(client, "patient@example.com").status_code == 200
        finally:
            client.app.dependency_overrides.pop(get_login_throttle, None)


class TestVerifyEmailEndpoint:
    """POST /api/v1/auth/verify-email."""

    def test_full_round_trip(self, client, fake_email):
        """Register, follow the emailed link, restate the password, then log in."""
        # GIVEN
        register(client, "roundtrip@example.com")
        token = _verify_token(fake_email)

        # WHEN
        response = _activate(client, token)

        # THEN
        assert response.status_code == 200
        assert stored_accounts(client, "roundtrip@example.com")[0]["email_verified_at"] is not None
        assert _login(client, "roundtrip@example.com").status_code == 200

    def test_unknown_reused_and_expired_tokens_give_the_same_answer(self, client, fake_email):
        """No response tells a caller which kind of bad token they hold."""
        # GIVEN: a spent token, and an expired one written straight into the table
        register(client, "tokens@example.com")
        spent = _verify_token(fake_email)
        assert _activate(client, spent).status_code == 200

        expired_raw = "expired-integration-token"
        user_id = stored_accounts(client, "tokens@example.com")[0]["id"]
        with app_session(client) as session:
            session.add(
                EmailVerificationToken(
                    user_id=user_id,
                    token_hash=hashlib.sha256(expired_raw.encode()).hexdigest(),
                    hashed_password=hash_password(DEFAULT_TEST_PASSWORD),
                    first_name="Test",
                    last_name="User",
                    expires_at=utc_now() - timedelta(minutes=1),
                )
            )
            session.commit()

        # WHEN
        unknown = _activate(client, "garbage-token")
        reused = _activate(client, spent)
        expired = _activate(client, expired_raw)

        # THEN
        assert unknown.status_code == reused.status_code == expired.status_code == 400
        assert unknown.content == reused.content == expired.content

    def test_a_mismatch_answers_differently_from_a_bad_token(self, client, fake_email):
        """A user who mistyped must not be told their link is broken.

        Sending them off to request another link would be worse than useless: the
        password would be wrong for that one too. The caller already holds a live link,
        so admitting the link is fine tells them nothing they did not have.
        """
        # GIVEN
        register(client, "mistyped@example.com")
        token = _verify_token(fake_email)

        # WHEN
        mismatch = _activate(client, token, "NotThePassword1!")
        unknown = _activate(client, "garbage-token")

        # THEN
        assert mismatch.status_code == 403
        assert unknown.status_code == 400
        assert mismatch.content != unknown.content

        # AND: the link survives the miss, so the second attempt works
        assert _activate(client, token).status_code == 200

    def test_verification_drops_the_cached_profile(self, client, fake_email):
        """Activation invalidates the cached snapshot instead of leaving it stale.

        The user cache holds a profile for a minute, so a snapshot taken before
        activation would keep reporting the account as unverified after it.
        """
        # GIVEN: a registered account whose pre-activation snapshot is cached
        register(client, "cached@example.com")
        token = _verify_token(fake_email)
        with app_session(client) as session:
            user = session.exec(select(User).where(User.email == "cached@example.com")).first()
            user_id = user.id
            get_user_cache().set(CachedUserData.from_user(user), 60)
        assert get_user_cache().get(user_id) is not None

        # WHEN
        response = _activate(client, token)

        # THEN
        assert response.status_code == 200
        assert get_user_cache().get(user_id) is None


class TestResendVerification:
    """POST /api/v1/auth/resend-verification."""

    def test_answers_identically_for_unknown_unverified_and_verified(
        self, client, fake_email, unthrottled_email
    ):
        """The endpoint reveals nothing about which addresses have accounts."""
        # GIVEN: one unverified and one activated account
        register(client, "pending@example.com")
        register_verified(client, "active@example.com")

        # WHEN
        unknown = _resend(client, "ghost@example.com")
        pending = _resend(client, "pending@example.com")
        active = _resend(client, "active@example.com")

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
        _resend(client, "ghost@example.com")
        _resend(client, "active@example.com")
        assert len(fake_email.verification_calls) == sends_after_setup

        _resend(client, "pending@example.com")

        # THEN
        assert len(fake_email.verification_calls) == sends_after_setup + 1
        assert fake_email.verification_calls[-1]["to_email"] == "pending@example.com"

    def test_a_resent_link_activates_on_the_password_it_was_asked_for(
        self, client, fake_email, unthrottled_email
    ):
        """The link a resend mails works, and it does not retire the earlier one.

        Retiring outstanding links is how one submitter would kill another's pending
        activation link, so a resend adds a link rather than replacing one. Whichever
        is followed first activates the address; the rest go dead with it.
        """
        # GIVEN
        register(client, "again@example.com", password=DEFAULT_TEST_PASSWORD)
        first = _verify_token(fake_email)

        # WHEN: the owner asks for another link, choosing a different password
        _resend(client, "again@example.com", OTHER_PASSWORD)
        second = _verify_token(fake_email)

        # THEN
        assert second != first
        assert _activate(client, second, OTHER_PASSWORD).status_code == 200
        assert _login(client, "again@example.com", OTHER_PASSWORD).status_code == 200
        assert _activate(client, first, DEFAULT_TEST_PASSWORD).status_code == 400

    def test_a_weak_password_is_rejected_before_anything_is_looked_up(self, client, fake_email):
        """The link a resend mints becomes the account's password, so it is strength-checked.

        The 422 is pure input validation: it depends only on the submitted string, so
        it says nothing about whether the address has an account.
        """
        # GIVEN
        register(client, "weak@example.com")
        sends_after_setup = len(fake_email.verification_calls)

        # WHEN
        known = _resend(client, "weak@example.com", "short")
        unknown = _resend(client, "ghost@example.com", "short")

        # THEN
        assert known.status_code == unknown.status_code == 422
        assert len(fake_email.verification_calls) == sends_after_setup


class TestPasswordResetActivatesTheAccount:
    """A reset link proves control of the address exactly as an activation link does."""

    def test_completing_a_reset_activates_an_unverified_account(self, client, fake_email):
        """Reclaiming an address somebody else registered is one step, not three."""
        # GIVEN: an account a stranger pre-registered, still unactivated
        register(client, "reclaimed@example.com", password=OTHER_PASSWORD, first_name="Stranger")
        client.post("/api/v1/auth/forgot-password", json={"email": "reclaimed@example.com"})
        reset_token = fake_email.calls[-1]["reset_url"].split("token=")[1]

        # WHEN
        reset = client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "new_password": DEFAULT_TEST_PASSWORD},
        )

        # THEN: the address is confirmed and the account opens straight away
        assert reset.status_code == 204
        assert stored_accounts(client, "reclaimed@example.com")[0]["email_verified_at"] is not None
        assert _login(client, "reclaimed@example.com", DEFAULT_TEST_PASSWORD).status_code == 200
        assert _login(client, "reclaimed@example.com", OTHER_PASSWORD).status_code == 401

    def test_a_reset_retires_every_outstanding_activation_link(self, client, fake_email):
        """An unspent link must not be able to put the old password and names back.

        Each carries a submission, so one redeemed after a reset would undo it. That is
        why forgot-password can only bound the risk if it also confirms the address.
        """
        # GIVEN: a stranger's link, and a reset the real owner then completes
        register(client, "stale@example.com", password=OTHER_PASSWORD, first_name="Stranger")
        strangers_link = _verify_token(fake_email)
        client.post("/api/v1/auth/forgot-password", json={"email": "stale@example.com"})
        reset_token = fake_email.calls[-1]["reset_url"].split("token=")[1]
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "new_password": DEFAULT_TEST_PASSWORD},
        )

        # WHEN: the stranger's link is followed afterwards, with its own password
        response = _activate(client, strangers_link, OTHER_PASSWORD)

        # THEN: dead, and the reset still stands
        assert response.status_code == 400
        assert _login(client, "stale@example.com", DEFAULT_TEST_PASSWORD).status_code == 200
        assert _login(client, "stale@example.com", OTHER_PASSWORD).status_code == 401
        assert stored_accounts(client, "stale@example.com")[0]["first_name"] == "Stranger"

    def test_a_reset_on_a_live_account_keeps_its_original_verification_time(
        self, client, fake_email
    ):
        """Confirming again must not rewrite when the address was actually confirmed."""
        # GIVEN
        register(client, "settled@example.com")
        assert _activate(client, _verify_token(fake_email)).status_code == 200
        verified_at = stored_accounts(client, "settled@example.com")[0]["email_verified_at"]

        # WHEN
        client.post("/api/v1/auth/forgot-password", json={"email": "settled@example.com"})
        reset_token = fake_email.calls[-1]["reset_url"].split("token=")[1]
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "new_password": OTHER_PASSWORD},
        )

        # THEN
        assert stored_accounts(client, "settled@example.com")[0]["email_verified_at"] == verified_at


class TestEmailThrottling:
    """One per-address budget covers repeat signups, notices, and resends."""

    def test_a_second_submission_mails_the_same_for_a_free_and_a_taken_address(
        self, client, fake_email
    ):
        """Two back-to-back submissions must not separate a free address from a taken one.

        The observable is the awaited round trip to the mail provider, which is exactly
        what the uniform 202 exists to hide. A creating branch that mailed without
        spending from the budget left it clean, so the free address mailed on both
        probes while the taken one had already gone quiet.
        """
        # GIVEN: a live account, and a fresh budget so the mail its own signup
        # triggered does not skew the comparison
        register_verified(client, "taken@example.com")
        _budget(client, cooldown_seconds=3600)
        taken_before = len(_mails_to(fake_email, "taken@example.com"))

        # WHEN: each address is submitted twice in a row
        for _ in range(2):
            assert register(client, "free@example.com").status_code == 202
            assert register(client, "taken@example.com").status_code == 202

        # THEN: one email each, and it went out on the first probe
        assert len(_mails_to(fake_email, "free@example.com")) == 1
        assert len(_mails_to(fake_email, "taken@example.com")) == taken_before + 1

    def test_a_rapid_second_send_is_suppressed_without_changing_the_response(
        self, client, fake_email
    ):
        """The signup's own link spends the allowance; a resend right after is suppressed."""
        # GIVEN: a registered account whose activation link just went out
        register(client, "flooded@example.com")
        assert len(fake_email.verification_calls) == 1

        # WHEN: two resends follow immediately
        first = _resend(client, "flooded@example.com")
        second = _resend(client, "flooded@example.com")

        # THEN: identical answers, and nothing more reached the inbox
        assert first.status_code == second.status_code == 202
        assert first.content == second.content
        assert len(fake_email.verification_calls) == 1

    def test_one_budget_covers_the_signup_and_the_notices_it_triggers(self, client, fake_email):
        """Submitting a victim's address in a loop does not mail them repeatedly."""
        # GIVEN: two emails a day for this address, one spent by its own signup
        _budget(client, daily_cap=2)
        register_verified(client, "flooded@example.com")
        assert len(fake_email.verification_calls) == 1

        # WHEN: the address is submitted twice more
        first = register(client, "flooded@example.com")
        second = register(client, "flooded@example.com")

        # THEN: one notice for the two attempts, and both answers are the same
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
        # GIVEN: a stranger burns the whole daily budget for an address with no account
        for _ in range(DAILY_CAP):
            _resend(client, "never@example.com")

        # WHEN: the real person signs up
        response = register(client, "never@example.com")

        # THEN: their activation link goes out, and it works
        assert response.status_code == 202
        assert len(fake_email.verification_calls) == 1
        assert fake_email.verification_calls[0]["to_email"] == "never@example.com"
        assert _activate(client, _verify_token(fake_email)).status_code == 200

    def test_a_resend_with_nothing_to_send_spends_nothing(self, client, fake_email):
        """A request naming an address with no pending signup leaves its budget intact.

        Nobody has to authenticate to name someone else's address here, so a request
        that sends no mail must not be able to spend the allowance a real one needs.
        """
        # GIVEN: two emails a day, one spent by the account's own signup, and a
        # stranger hammering resend at an address that has nothing to resend
        _budget(client, daily_cap=2)
        register_verified(client, "settled@example.com")
        for _ in range(DAILY_CAP * 2):
            _resend(client, "settled@example.com")
        assert len(fake_email.verification_calls) == 1  # only the original signup

        # WHEN: someone submits that address to the signup form
        register(client, "settled@example.com")

        # THEN: the owner is still told about it
        assert len(fake_email.notice_calls) == 1
