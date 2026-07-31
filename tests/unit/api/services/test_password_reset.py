"""Unit tests for PasswordResetService."""

import hashlib
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from api.auth.password import hash_password, verify_password
from api.db.models import PasswordResetToken, User
from api.db.utils import utc_now
from api.exceptions import InvalidResetTokenError, ResetTokenExpiredError
from api.services.email_verification_service import EmailVerificationService, PendingCredentials
from api.services.password_reset_service import PasswordResetService


def _hash(raw: str) -> str:
    """Hash a raw token the same way the service stores it."""
    return hashlib.sha256(raw.encode()).hexdigest()


def _token_from_url(url: str) -> str:
    """Extract the raw token from a reset URL (the part after ``token=``)."""
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
        hashed_password="old-hash",
        first_name="Test",
        last_name="User",
        email_verified_at=utc_now() if verified else None,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


class TestCreateResetToken:
    """Tests for issuing reset tokens."""

    def test_returns_reset_url_and_stores_only_hash(self, session):
        """
        GIVEN an existing user
        WHEN a reset token is created
        THEN a reset URL is returned and only the token's SHA-256 hash is stored
        """
        # GIVEN
        user = _make_user(session)
        service = PasswordResetService(session)

        # WHEN
        url = service.create_reset_token(user.email)

        # THEN
        assert url
        assert "/reset-password?token=" in url
        token = _token_from_url(url)
        stored = session.exec(select(PasswordResetToken)).all()
        assert len(stored) == 1
        assert stored[0].token_hash == _hash(token)
        assert token != stored[0].token_hash

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
        first_url = service.create_reset_token(user.email)

        # WHEN
        service.create_reset_token(user.email)

        # THEN
        first = session.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == _hash(_token_from_url(first_url))
            )
        ).first()
        assert first is not None
        assert first.used_at is not None


class TestResolveValidToken:
    """Tests for resolving a reset token without consuming it."""

    def test_returns_the_user_without_touching_the_token(self, session):
        """
        GIVEN a valid reset token
        WHEN the token is resolved
        THEN its user is returned, the password is unchanged, and the token stays unused
        """
        # GIVEN
        user = _make_user(session)
        original_hash = user.hashed_password
        service = PasswordResetService(session)
        token = _token_from_url(service.create_reset_token(user.email))

        # WHEN
        resolved = service.resolve_valid_token(token)

        # THEN
        assert resolved.id == user.id
        assert resolved.hashed_password == original_hash
        record = session.exec(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash(token))
        ).first()
        assert record is not None
        assert record.used_at is None

    def test_raises_for_unknown_token(self, session):
        """
        GIVEN a token that does not exist
        WHEN it is resolved
        THEN InvalidResetTokenError is raised
        """
        # GIVEN
        service = PasswordResetService(session)

        # WHEN / THEN
        with pytest.raises(InvalidResetTokenError):
            service.resolve_valid_token("garbage-token")

    def test_raises_for_already_used_token(self, session):
        """
        GIVEN a token that has already been redeemed
        WHEN it is resolved
        THEN InvalidResetTokenError is raised
        """
        # GIVEN
        user = _make_user(session)
        service = PasswordResetService(session)
        token = _token_from_url(service.create_reset_token(user.email))
        service.reset_password(token, "NewSecurePass123!")

        # WHEN / THEN
        with pytest.raises(InvalidResetTokenError):
            service.resolve_valid_token(token)

    def test_raises_for_expired_token(self, session):
        """
        GIVEN a token whose expiry is in the past
        WHEN it is resolved
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
            service.resolve_valid_token(raw)


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
        token = _token_from_url(service.create_reset_token(user.email))

        # WHEN
        updated = service.reset_password(token, "NewSecurePass123!")

        # THEN
        assert verify_password("NewSecurePass123!", updated.hashed_password)
        record = session.exec(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash(token))
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
        token = _token_from_url(service.create_reset_token(user.email))
        service.reset_password(token, "NewSecurePass123!")

        # WHEN / THEN
        with pytest.raises(InvalidResetTokenError):
            service.reset_password(token, "AnotherPass123!")

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

    def test_raises_when_user_missing_for_valid_token(self, session):
        """
        GIVEN a non-expired token whose user no longer exists
        WHEN the password reset is attempted
        THEN InvalidResetTokenError is raised
        """
        # GIVEN — a token row pointing at a user id that was never created
        raw = "orphan-token-value"
        session.add(
            PasswordResetToken(
                user_id=uuid4(),
                token_hash=_hash(raw),
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        session.commit()
        service = PasswordResetService(session)

        # WHEN / THEN
        with pytest.raises(InvalidResetTokenError):
            service.reset_password(raw, "NewSecurePass123!")


class TestResetPasswordConfirmsTheAddress:
    """Tests for the address confirmation a completed reset also performs."""

    def test_confirms_an_address_that_was_still_unverified(self, session):
        """
        GIVEN an unverified account holding a valid reset token
        WHEN the password is reset
        THEN the address is confirmed, which retires its outstanding activation links
        """
        # GIVEN
        user = _make_user(session)
        service = PasswordResetService(session)
        token = _token_from_url(service.create_reset_token(user.email))

        # WHEN
        updated = service.reset_password(token, "NewSecurePass123!")

        # THEN
        assert updated.email_verified_at is not None
        assert verify_password("NewSecurePass123!", updated.hashed_password)

    def test_keeps_a_confirmation_the_account_already_had(self, session):
        """
        GIVEN an account confirmed at some earlier point
        WHEN the password is reset
        THEN the password changes and the original confirmation timestamp survives
        """
        # GIVEN
        user = _make_user(session, verified=True)
        confirmed_at = user.email_verified_at
        service = PasswordResetService(session)
        token = _token_from_url(service.create_reset_token(user.email))

        # WHEN
        updated = service.reset_password(token, "NewSecurePass123!")

        # THEN
        assert verify_password("NewSecurePass123!", updated.hashed_password)
        assert updated.email_verified_at == confirmed_at

    def test_a_reset_that_loses_to_an_activation_writes_nothing(self, session):
        """An activation committing mid-reset keeps the credentials it chose.

        A reset and an activation both prove control of the same mailbox and both
        confirm the address, so the two collide on an account that is still
        unverified. The reset loads the row, spends a few hundred milliseconds in
        bcrypt, and the activation commits inside that gap; the route holds the same
        loaded copy across both calls, so nothing re-reads the row in between.
        Writing by primary key afterwards replaced the password the activation had
        just applied, while the person who redeemed it had already been told to sign
        in with it.
        """
        # GIVEN - an unverified account whose reset token the service has resolved,
        # which is the point the route reaches before it starts hashing
        user = _make_user(session)
        reset = PasswordResetService(session)
        reset_token = _token_from_url(reset.create_reset_token(user.email))
        reset.resolve_valid_token(reset_token)

        # WHEN - an activation redeems its own link first, from its own session, so
        # the reset still holds the unverified copy of the row
        activation_password = "ActivationPass1!"
        with Session(session.get_bind()) as other:
            verification = EmailVerificationService(other)
            link = verification.create_verification_url(
                user,
                PendingCredentials(
                    hashed_password=hash_password(activation_password),
                    first_name="Acti",
                    last_name="Vated",
                ),
            )
            raw = _token_from_url(link)
            verification.activate(verification.resolve_pending_activation(raw), activation_password)

        # THEN - the reset is refused rather than reporting a password it did not set
        with pytest.raises(InvalidResetTokenError):
            reset.reset_password(reset_token, "NewSecurePass123!")
        session.rollback()
        assert verify_password(activation_password, session.get(User, user.id).hashed_password)

        # and its own link is left unspent, so retrying it lands on the uncontested
        # path instead of stranding whoever asked for the reset
        record = session.exec(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash(reset_token))
        ).first()
        assert record is not None
        assert record.used_at is None
        retried = reset.reset_password(reset_token, "NewSecurePass123!")
        assert verify_password("NewSecurePass123!", retried.hashed_password)
