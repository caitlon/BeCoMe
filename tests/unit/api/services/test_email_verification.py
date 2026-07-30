"""Unit tests for EmailVerificationService."""

import hashlib
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from api.db.models import EmailVerificationToken, User
from api.db.utils import utc_now
from api.exceptions import InvalidVerificationTokenError, VerificationTokenExpiredError
from api.services.email_verification_service import EmailVerificationService


def _hash(raw: str) -> str:
    """Hash a raw token the same way the service stores it."""
    return hashlib.sha256(raw.encode()).hexdigest()


def _token_from_url(url: str) -> str:
    """Extract the raw token from a verification URL (the part after ``token=``)."""
    return url.split("token=")[1]


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


class TestCreateVerificationUrl:
    """Tests for issuing activation links."""

    def test_returns_activation_url_and_stores_only_the_hash(self, session):
        """The raw token reaches the caller only inside the URL; the row holds its hash."""
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)

        # WHEN
        url = service.create_verification_url(user)

        # THEN
        assert "/verify-email?token=" in url
        raw = _token_from_url(url)
        record = session.exec(select(EmailVerificationToken)).one()
        assert record.token_hash == _hash(raw)
        assert raw not in record.token_hash

    def test_invalidates_outstanding_tokens(self, session):
        """Issuing a new link retires every link issued before it."""
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)
        first = _token_from_url(service.create_verification_url(user))

        # WHEN
        second = _token_from_url(service.create_verification_url(user))

        # THEN
        with pytest.raises(InvalidVerificationTokenError):
            service.verify_email(first)
        assert service.verify_email(second).email_verified_at is not None

    def test_expiry_follows_the_configured_ttl(self, session):
        """The token expires the configured number of hours out, not minutes."""
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)

        # WHEN
        service.create_verification_url(user)

        # THEN - 24h by default, so comfortably more than an hour away
        record = session.exec(select(EmailVerificationToken)).one()
        assert record.expires_at > utc_now().replace(tzinfo=None) + timedelta(hours=23)


class TestCreateVerificationUrlForEmail:
    """Tests for the resend entry point."""

    def test_issues_a_link_for_an_unverified_account(self, session):
        # GIVEN
        _make_user(session, "pending@example.com")
        service = EmailVerificationService(session)

        # WHEN
        url = service.create_verification_url_for_email("pending@example.com")

        # THEN
        assert url is not None
        assert "/verify-email?token=" in url

    def test_returns_none_for_an_unknown_address(self, session):
        # GIVEN
        service = EmailVerificationService(session)

        # WHEN / THEN
        assert service.create_verification_url_for_email("ghost@example.com") is None

    def test_returns_none_for_an_already_verified_account(self, session):
        """A live account never gets another activation link mailed to it."""
        # GIVEN
        _make_user(session, "active@example.com", verified=True)
        service = EmailVerificationService(session)

        # WHEN / THEN
        assert service.create_verification_url_for_email("active@example.com") is None
        assert session.exec(select(EmailVerificationToken)).all() == []

    def test_matches_the_address_case_insensitively(self, session):
        # GIVEN
        _make_user(session, "mixed@example.com")
        service = EmailVerificationService(session)

        # WHEN / THEN
        assert service.create_verification_url_for_email("Mixed@Example.COM") is not None


class TestVerifyEmail:
    """Tests for redeeming an activation token."""

    def test_marks_the_address_verified_and_spends_the_token(self, session):
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)
        raw = _token_from_url(service.create_verification_url(user))

        # WHEN
        verified = service.verify_email(raw)

        # THEN
        assert verified.email_verified_at is not None
        assert session.exec(select(EmailVerificationToken)).one().used_at is not None

    def test_invalidates_the_cached_profile(self, session):
        """A snapshot taken before activation must not survive it."""
        # GIVEN
        user = _make_user(session)
        cache = MagicMock()
        service = EmailVerificationService(session, cache)
        raw = _token_from_url(service.create_verification_url(user))

        # WHEN
        service.verify_email(raw)

        # THEN
        cache.invalidate.assert_called_once_with(user.id)

    def test_rejects_an_unknown_token(self, session):
        # GIVEN
        service = EmailVerificationService(session)

        # WHEN / THEN
        with pytest.raises(InvalidVerificationTokenError):
            service.verify_email("garbage-token")

    def test_rejects_a_reused_token(self, session):
        # GIVEN
        user = _make_user(session)
        service = EmailVerificationService(session)
        raw = _token_from_url(service.create_verification_url(user))
        service.verify_email(raw)

        # WHEN / THEN
        with pytest.raises(InvalidVerificationTokenError):
            service.verify_email(raw)

    def test_rejects_an_expired_token(self, session):
        # GIVEN
        user = _make_user(session)
        session.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=_hash("stale"),
                expires_at=utc_now() - timedelta(hours=1),
            )
        )
        session.commit()
        service = EmailVerificationService(session)

        # WHEN / THEN
        with pytest.raises(VerificationTokenExpiredError):
            service.verify_email("stale")

    def test_accepts_a_token_whose_expiry_is_stored_without_a_timezone(self, session):
        """The column is TIMESTAMP WITHOUT TIME ZONE, so the comparison must add UTC.

        Comparing a naive expires_at against an aware now() raises TypeError, which
        would surface as a 500 on a perfectly valid activation link.
        """
        # GIVEN - an expiry stored the way the database hands it back: naive
        user = _make_user(session)
        naive_future = datetime.now() + timedelta(hours=12)
        assert naive_future.tzinfo is None
        session.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=_hash("naive"),
                expires_at=naive_future,
            )
        )
        session.commit()
        service = EmailVerificationService(session)

        # WHEN
        verified = service.verify_email("naive")

        # THEN
        assert verified.email_verified_at is not None

    def test_rejects_a_token_whose_user_is_gone(self, session):
        """A token outliving its account is treated like any other bad token."""
        # GIVEN - a token pointing at a user id that no longer exists
        session.add(
            EmailVerificationToken(
                user_id=uuid4(),
                token_hash=_hash("orphan"),
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        session.commit()
        service = EmailVerificationService(session)

        # WHEN / THEN
        with pytest.raises(InvalidVerificationTokenError):
            service.verify_email("orphan")
