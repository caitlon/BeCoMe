"""Unit tests for EmailVerificationService."""

import hashlib
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from api.auth.password import hash_password
from api.db.models import EmailVerificationToken, User
from api.db.utils import utc_now
from api.exceptions import (
    InvalidVerificationTokenError,
    VerificationPasswordMismatchError,
    VerificationTokenExpiredError,
)
from api.services.email_verification_service import EmailVerificationService, PendingCredentials

# Hashed once at import: bcrypt costs 100-300 ms and every test here needs a real hash,
# since redemption runs the password through bcrypt rather than comparing strings.
SUBMITTED_PASSWORD = "SubmittedPass1!"
OTHER_PASSWORD = "SomeOtherPass99!"
SUBMITTED = PendingCredentials(
    hashed_password=hash_password(SUBMITTED_PASSWORD),
    first_name="Sub",
    last_name="Mitted",
)
OTHER = PendingCredentials(
    hashed_password=hash_password(OTHER_PASSWORD),
    first_name="Some",
    last_name="Body",
)


def _hash(raw: str) -> str:
    """Hash a raw token the same way the service stores it."""
    return hashlib.sha256(raw.encode()).hexdigest()


def _token_from_url(url: str) -> str:
    """Extract the raw token from a verification URL (the part after ``token=``)."""
    return url.split("token=")[1]


def _redeem(service: EmailVerificationService, token: str, password: str) -> User:
    """Resolve a raw token and redeem it, the way the route does."""
    return service.activate(service.resolve_pending_activation(token), password)


@pytest.fixture
def session():
    """In-memory SQLite session with all tables created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def _make_user(session: Session, email: str = "user@example.com", verified: bool = False) -> User:
    """Persist and return a user, verified or not."""
    user = User(
        email=email,
        hashed_password="stored-hash",
        first_name="Test",
        last_name="User",
        email_verified_at=utc_now() if verified else None,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _store_token(session: Session, user_id, raw: str, expires_at: datetime) -> None:
    """Write a token record straight into the table, bypassing the service."""
    session.add(
        EmailVerificationToken(
            user_id=user_id,
            token_hash=_hash(raw),
            hashed_password=SUBMITTED.hashed_password,
            first_name=SUBMITTED.first_name,
            last_name=SUBMITTED.last_name,
            expires_at=expires_at,
        )
    )
    session.commit()


class TestCreateVerificationUrl:
    """Tests for issuing activation links."""

    def test_returns_activation_url_and_stores_only_the_hash(self, session):
        """The raw token reaches the caller only inside the URL; the row holds its hash."""
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)

        # WHEN
        url = service.create_verification_url(user, SUBMITTED)

        # THEN
        assert "/verify-email?token=" in url
        raw = _token_from_url(url)
        record = session.exec(select(EmailVerificationToken)).one()
        assert record.token_hash == _hash(raw)
        assert raw not in record.token_hash

    def test_leaves_outstanding_links_alive(self, session):
        """Issuing a link must not retire the links issued before it.

        Each link carries the submission that minted it, so retiring the others is
        exactly how one submitter would kill another's pending activation link.
        """
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)
        first = _token_from_url(service.create_verification_url(user, SUBMITTED))

        # WHEN
        service.create_verification_url(user, SUBMITTED)

        # THEN - the older link still works
        assert _redeem(service, first, SUBMITTED_PASSWORD).email_verified_at is not None

    def test_stores_the_submission_the_link_was_minted_for(self, session):
        """The credentials ride on the token rather than on the account."""
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)

        # WHEN
        service.create_verification_url(user, SUBMITTED)

        # THEN
        record = session.exec(select(EmailVerificationToken)).one()
        assert record.hashed_password == SUBMITTED.hashed_password
        assert record.first_name == SUBMITTED.first_name
        assert record.last_name == SUBMITTED.last_name

        # AND - the account itself is untouched until the link is followed
        assert user.hashed_password == "stored-hash"

    def test_expiry_follows_the_configured_ttl(self, session):
        """The token expires the configured number of hours out, not minutes."""
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)

        # WHEN
        service.create_verification_url(user, SUBMITTED)

        # THEN - 24h by default, so comfortably more than an hour away
        record = session.exec(select(EmailVerificationToken)).one()
        assert record.expires_at > utc_now().replace(tzinfo=None) + timedelta(hours=23)


class TestCreateResendUrl:
    """Tests for the link a resend request mints."""

    def test_carries_the_submitted_password_and_the_accounts_names(self, session):
        """A resend binds its own password; the names are all it can take from the row.

        A link with nothing bound to it would be one anybody receiving the mail could
        follow, which is the takeover this flow exists to close.
        """
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)

        # WHEN
        service.create_resend_url(user, SUBMITTED.hashed_password)

        # THEN
        record = session.exec(select(EmailVerificationToken)).one()
        assert record.hashed_password == SUBMITTED.hashed_password
        assert record.first_name == user.first_name
        assert record.last_name == user.last_name

    def test_the_resent_link_opens_on_the_password_the_request_supplied(self, session):
        """Following a resend link sets the account's password to the resent one."""
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)
        raw = _token_from_url(service.create_resend_url(user, hash_password(OTHER_PASSWORD)))

        # WHEN
        verified = _redeem(service, raw, OTHER_PASSWORD)

        # THEN
        assert verified.email_verified_at is not None
        assert verified.hashed_password != "stored-hash"


class TestFindUnverifiedAccount:
    """Tests for the resend lookup, which runs before any budget is spent."""

    def test_returns_the_account_still_waiting(self, session):
        # GIVEN
        pending = _make_user(session, "pending@example.com")
        service = EmailVerificationService(session)

        # WHEN / THEN
        assert service.find_unverified_account("pending@example.com") == pending

    def test_returns_none_for_an_unknown_address(self, session):
        # GIVEN
        service = EmailVerificationService(session)

        # WHEN / THEN
        assert service.find_unverified_account("ghost@example.com") is None

    def test_returns_none_for_an_already_verified_account(self, session):
        """A live account never gets another activation link mailed to it."""
        # GIVEN
        _make_user(session, "active@example.com", verified=True)
        service = EmailVerificationService(session)

        # WHEN / THEN
        assert service.find_unverified_account("active@example.com") is None

    def test_mints_nothing_by_itself(self, session):
        """Looking is free: no token exists until the caller decides to send one."""
        # GIVEN
        _make_user(session, "pending@example.com")
        service = EmailVerificationService(session)

        # WHEN
        service.find_unverified_account("pending@example.com")

        # THEN
        assert session.exec(select(EmailVerificationToken)).all() == []

    def test_matches_the_address_case_insensitively(self, session):
        # GIVEN
        _make_user(session, "mixed@example.com")
        service = EmailVerificationService(session)

        # WHEN / THEN
        assert service.find_unverified_account("Mixed@Example.COM") is not None


class TestActivate:
    """Tests for redeeming an activation token."""

    def test_marks_the_address_verified_and_spends_the_token(self, session):
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)
        raw = _token_from_url(service.create_verification_url(user, SUBMITTED))

        # WHEN
        verified = _redeem(service, raw, SUBMITTED_PASSWORD)

        # THEN
        assert verified.email_verified_at is not None
        assert session.exec(select(EmailVerificationToken)).one().used_at is not None

    def test_writes_the_submission_the_redeemed_link_carries(self, session):
        """Following a link applies that link's submission, nobody else's."""
        # GIVEN - a link minted by one submission, and a later one by another
        user = _make_user(session)
        service = EmailVerificationService(session)
        mine = _token_from_url(service.create_verification_url(user, SUBMITTED))
        service.create_verification_url(user, OTHER)

        # WHEN
        verified = _redeem(service, mine, SUBMITTED_PASSWORD)

        # THEN
        assert verified.hashed_password == SUBMITTED.hashed_password
        assert verified.first_name == SUBMITTED.first_name
        assert verified.last_name == SUBMITTED.last_name

    def test_refuses_a_password_that_is_not_the_one_the_link_carries(self, session):
        """Holding the link is not enough; the submission behind it has to be restated.

        This is what makes a stranger's activation mail useless in the recipient's
        hands: the recipient knows their own password, not the one that minted it.
        """
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)
        raw = _token_from_url(service.create_verification_url(user, SUBMITTED))

        # WHEN / THEN
        with pytest.raises(VerificationPasswordMismatchError):
            _redeem(service, raw, OTHER_PASSWORD)

        # AND - nothing was written and the link was not spent
        session.refresh(user)
        assert user.email_verified_at is None
        assert user.hashed_password == "stored-hash"
        assert session.exec(select(EmailVerificationToken)).one().used_at is None

    def test_checks_the_password_against_the_token_not_the_account(self, session):
        """The stored password is irrelevant: only the token's submission counts.

        Checking against the account would let whoever created it decide what every
        outstanding link opens, which is the primitive being removed.
        """
        # GIVEN - an account whose stored password is not the one the link carries
        user = _make_user(session)
        user.hashed_password = hash_password(OTHER_PASSWORD)
        session.add(user)
        session.commit()
        service = EmailVerificationService(session)
        raw = _token_from_url(service.create_verification_url(user, SUBMITTED))

        # WHEN / THEN - the account's own password does not open its link
        with pytest.raises(VerificationPasswordMismatchError):
            _redeem(service, raw, OTHER_PASSWORD)
        assert _redeem(service, raw, SUBMITTED_PASSWORD).email_verified_at is not None

    def test_rejects_a_live_token_once_the_account_is_verified(self, session):
        """An unspent link cannot be used to rewrite an account that is already in use.

        A token minted while the address was unconfirmed carries a password. Redeeming
        it after activation would let whoever holds it replace the password of a live
        account, which is the takeover this refusal closes.
        """
        # GIVEN - two live links, one of them redeemed
        user = _make_user(session)
        service = EmailVerificationService(session)
        first = _token_from_url(service.create_verification_url(user, SUBMITTED))
        second = _token_from_url(service.create_verification_url(user, OTHER))
        _redeem(service, first, SUBMITTED_PASSWORD)

        # WHEN / THEN - the other one is refused like any unusable token, before its
        # password is even weighed
        with pytest.raises(InvalidVerificationTokenError):
            _redeem(service, second, OTHER_PASSWORD)
        assert session.get(User, user.id).hashed_password == SUBMITTED.hashed_password

    def test_a_redemption_that_loses_the_race_writes_nothing(self, session):
        """Two redemptions that both saw an unverified account: exactly one wins.

        Both resolve while ``email_verified_at`` is still NULL, so the read-then-write
        version had them both write and the later one silently overwrite the earlier.
        The conditional UPDATE makes the database pick.
        """
        # GIVEN - two links resolved before either is redeemed
        user = _make_user(session)
        service = EmailVerificationService(session)
        first = service.resolve_pending_activation(
            _token_from_url(service.create_verification_url(user, SUBMITTED))
        )
        second = service.resolve_pending_activation(
            _token_from_url(service.create_verification_url(user, OTHER))
        )

        # WHEN
        service.activate(first, SUBMITTED_PASSWORD)

        # THEN - the loser is refused and leaves the winner's credentials in place
        with pytest.raises(InvalidVerificationTokenError):
            service.activate(second, OTHER_PASSWORD)
        session.refresh(user)
        assert user.hashed_password == SUBMITTED.hashed_password
        assert user.first_name == SUBMITTED.first_name

    def test_invalidates_the_cached_profile(self, session):
        """A snapshot taken before activation must not survive it."""
        # GIVEN
        user = _make_user(session)
        cache = MagicMock()
        service = EmailVerificationService(session, cache)
        raw = _token_from_url(service.create_verification_url(user, SUBMITTED))

        # WHEN
        _redeem(service, raw, SUBMITTED_PASSWORD)

        # THEN
        cache.invalidate.assert_called_once_with(user.id)

    def test_rejects_an_unknown_token(self, session):
        # GIVEN
        service = EmailVerificationService(session)

        # WHEN / THEN
        with pytest.raises(InvalidVerificationTokenError):
            service.resolve_pending_activation("garbage-token")

    def test_rejects_a_reused_token(self, session):
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)
        raw = _token_from_url(service.create_verification_url(user, SUBMITTED))
        _redeem(service, raw, SUBMITTED_PASSWORD)

        # WHEN / THEN
        with pytest.raises(InvalidVerificationTokenError):
            service.resolve_pending_activation(raw)

    def test_rejects_an_expired_token(self, session):
        # GIVEN
        user = _make_user(session)
        _store_token(session, user.id, "stale", utc_now() - timedelta(hours=1))
        service = EmailVerificationService(session)

        # WHEN / THEN
        with pytest.raises(VerificationTokenExpiredError):
            service.resolve_pending_activation("stale")

    def test_accepts_a_token_whose_expiry_is_stored_without_a_timezone(self, session):
        """The column is TIMESTAMP WITHOUT TIME ZONE, so the comparison must add UTC.

        Comparing a naive expires_at against an aware now() raises TypeError, which
        would surface as a 500 on a perfectly valid activation link.
        """
        # GIVEN - an expiry stored the way the database hands it back: naive
        user = _make_user(session)
        naive_future = datetime.now() + timedelta(hours=12)
        assert naive_future.tzinfo is None
        _store_token(session, user.id, "naive", naive_future)
        service = EmailVerificationService(session)

        # WHEN
        verified = _redeem(service, "naive", SUBMITTED_PASSWORD)

        # THEN
        assert verified.email_verified_at is not None

    def test_rejects_a_token_whose_user_is_gone(self, session):
        """A token outliving its account is treated like any other bad token."""
        # GIVEN - a token pointing at a user id that no longer exists
        _store_token(session, uuid4(), "orphan", utc_now() + timedelta(hours=1))
        service = EmailVerificationService(session)

        # WHEN / THEN
        with pytest.raises(InvalidVerificationTokenError):
            service.resolve_pending_activation("orphan")
