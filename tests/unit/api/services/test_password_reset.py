"""Unit tests for PasswordResetService."""

import hashlib
from datetime import timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from api.auth.password import verify_password
from api.db.models import PasswordResetToken, User
from api.db.utils import utc_now
from api.exceptions import InvalidResetTokenError, ResetTokenExpiredError
from api.services.password_reset_service import PasswordResetService


def _hash(raw: str) -> str:
    """Hash a raw token the same way the service stores it."""
    return hashlib.sha256(raw.encode()).hexdigest()


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


def _make_user(session: Session, email: str = "user@example.com") -> User:
    """Persist and return a user."""
    user = User(
        email=email,
        hashed_password="old-hash",
        first_name="Test",
        last_name="User",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


class TestCreateResetToken:
    """Tests for issuing reset tokens."""

    def test_returns_raw_token_and_stores_only_hash(self, session):
        """
        GIVEN an existing user
        WHEN a reset token is created
        THEN a raw token is returned and only its SHA-256 hash is stored
        """
        # GIVEN
        user = _make_user(session)
        service = PasswordResetService(session)

        # WHEN
        raw = service.create_reset_token(user.email)

        # THEN
        assert raw
        stored = session.exec(select(PasswordResetToken)).all()
        assert len(stored) == 1
        assert stored[0].token_hash == _hash(raw)
        assert raw != stored[0].token_hash

    def test_returns_none_for_unknown_email(self, session):
        """
        GIVEN no user with the requested email
        WHEN a reset token is requested
        THEN None is returned and no token row is written
        """
        # GIVEN
        service = PasswordResetService(session)

        # WHEN
        raw = service.create_reset_token("nobody@example.com")

        # THEN
        assert raw is None
        assert session.exec(select(PasswordResetToken)).all() == []

    def test_invalidates_previous_tokens(self, session):
        """
        GIVEN a user with an outstanding reset token
        WHEN a second token is requested
        THEN the first token is marked used
        """
        # GIVEN
        user = _make_user(session)
        service = PasswordResetService(session)
        first_raw = service.create_reset_token(user.email)

        # WHEN
        service.create_reset_token(user.email)

        # THEN
        first = session.exec(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash(first_raw))
        ).first()
        assert first is not None
        assert first.used_at is not None


class TestResetPassword:
    """Tests for redeeming reset tokens."""

    def test_sets_new_password_and_marks_token_used(self, session):
        """
        GIVEN a valid reset token
        WHEN the password is reset
        THEN the new password verifies and the token is marked used
        """
        # GIVEN
        user = _make_user(session)
        service = PasswordResetService(session)
        raw = service.create_reset_token(user.email)

        # WHEN
        updated = service.reset_password(raw, "NewSecurePass123!")

        # THEN
        assert verify_password("NewSecurePass123!", updated.hashed_password)
        record = session.exec(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash(raw))
        ).first()
        assert record is not None
        assert record.used_at is not None

    def test_raises_for_unknown_token(self, session):
        """
        GIVEN a token that does not exist
        WHEN the password reset is attempted
        THEN InvalidResetTokenError is raised
        """
        # GIVEN
        service = PasswordResetService(session)

        # WHEN / THEN
        with pytest.raises(InvalidResetTokenError):
            service.reset_password("garbage-token", "NewSecurePass123!")

    def test_raises_for_already_used_token(self, session):
        """
        GIVEN a token that has already been redeemed
        WHEN the password reset is attempted again
        THEN InvalidResetTokenError is raised
        """
        # GIVEN
        user = _make_user(session)
        service = PasswordResetService(session)
        raw = service.create_reset_token(user.email)
        service.reset_password(raw, "NewSecurePass123!")

        # WHEN / THEN
        with pytest.raises(InvalidResetTokenError):
            service.reset_password(raw, "AnotherPass123!")

    def test_raises_for_expired_token(self, session):
        """
        GIVEN a token whose expiry is in the past
        WHEN the password reset is attempted
        THEN ResetTokenExpiredError is raised
        """
        # GIVEN
        user = _make_user(session)
        raw = "expired-raw-token-value"
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=_hash(raw),
                expires_at=utc_now() - timedelta(hours=1),
            )
        )
        session.commit()
        service = PasswordResetService(session)

        # WHEN / THEN
        with pytest.raises(ResetTokenExpiredError):
            service.reset_password(raw, "NewSecurePass123!")
