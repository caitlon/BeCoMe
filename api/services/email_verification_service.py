"""Email verification business logic service."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from sqlmodel import Session, col, select

from api.config import get_settings
from api.db.models import EmailVerificationToken, User
from api.db.utils import ensure_utc, utc_now
from api.exceptions import InvalidVerificationTokenError, VerificationTokenExpiredError
from api.services.base import BaseService
from api.services.user_cache import UserCacheStore

logger = logging.getLogger("api.service.email_verification")

# Entropy for the raw verification token; token_urlsafe(32) yields a ~43-character string.
_TOKEN_BYTES = 32

# One opaque message for unknown, used, and expired tokens so a caller cannot
# tell them apart (avoids a token-state oracle).
_INVALID_MESSAGE = "Invalid or expired verification link"


def _hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of a raw verification token.

    :param raw_token: The raw, high-entropy token sent to the user.
    :return: 64-character hex digest stored in the database.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


class EmailVerificationService(BaseService):
    """Issue and redeem single-use, expiring email-verification tokens.

    Deliberately the same shape as :class:`~api.services.password_reset_service.PasswordResetService`:
    only the SHA-256 hash of each token is stored, the raw token lives only long
    enough to be emailed, and issuing a new token invalidates the outstanding ones
    so only the newest activation link works.
    """

    def __init__(self, session: Session, user_cache: UserCacheStore | None = None) -> None:
        """Initialize with a DB session and an optional user cache.

        :param session: SQLModel session for database operations.
        :param user_cache: Cache to invalidate once an address becomes verified.
        """
        super().__init__(session)
        self._user_cache = user_cache

    def create_verification_url(self, user: User) -> str:
        """Issue a fresh activation link for a user.

        Any outstanding tokens for that user are invalidated first, so a link mailed
        by an earlier registration attempt stops working. Only the token hash is
        persisted; the raw token lives only inside the returned URL.

        :param user: The account whose address needs verifying.
        :return: The full activation URL to email.
        """
        self._invalidate_outstanding(user)

        settings = get_settings()
        raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
        ttl = timedelta(hours=settings.email_verification_token_ttl_hours)
        token = EmailVerificationToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            expires_at=utc_now() + ttl,
        )
        # Commits the invalidations queued above together with the new token.
        self._save_and_refresh(token)
        logger.info(
            "Email verification token created",
            extra={"event": "verification_token_created", "user_id": str(user.id)},
        )
        return f"{settings.frontend_base_url}/verify-email?token={raw_token}"

    def create_verification_url_for_email(self, email: str) -> str | None:
        """Issue an activation link for an unverified account with this address.

        :param email: Email address from a resend request.
        :return: The full activation URL to email, or None when no account has that
            address or its address is already verified. The caller must respond
            identically either way to avoid user enumeration.
        """
        user = self._get_user_by_email(email)
        if user is None or user.email_verified_at is not None:
            logger.info(
                "Verification resend had nothing to send",
                extra={"event": "verification_resend_noop"},
            )
            return None
        return self.create_verification_url(user)

    def verify_email(self, token: str) -> User:
        """Consume an activation token and mark the user's address verified.

        :param token: The raw token from the activation link.
        :return: The now-verified user.
        :raises InvalidVerificationTokenError: If the token is unknown or already used.
        :raises VerificationTokenExpiredError: If the token has expired.
        """
        record = self._get_valid_record(token)
        user = self._get_token_user(record)

        user.email_verified_at = utc_now()
        record.used_at = utc_now()
        self._session.add(user)
        self._session.add(record)
        self._session.commit()
        self._session.refresh(user)

        # user_cache_ttl_seconds is 60, so without this a user who just activated could
        # keep reading a stale, still-unverified snapshot of their own profile.
        if self._user_cache is not None:
            self._user_cache.invalidate(user.id)

        logger.info(
            "Email address verified",
            extra={"event": "email_verification_completed", "user_id": str(user.id)},
        )
        return user

    def _get_valid_record(self, token: str) -> EmailVerificationToken:
        """Look up a verification token and reject it unless unused and unexpired.

        :param token: The raw token from the activation link.
        :return: The matching token record.
        :raises InvalidVerificationTokenError: If the token is unknown or already used.
        :raises VerificationTokenExpiredError: If the token has expired.
        """
        record = self._session.exec(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash == _hash_token(token)
            )
        ).first()

        if record is None or record.used_at is not None:
            raise InvalidVerificationTokenError(_INVALID_MESSAGE)
        # expires_at is a naive TIMESTAMP WITHOUT TIME ZONE; comparing it raw against an
        # aware utc_now() raises TypeError, so it has to be made aware first.
        if ensure_utc(record.expires_at) < utc_now():
            raise VerificationTokenExpiredError(_INVALID_MESSAGE)
        return record

    def _get_token_user(self, record: EmailVerificationToken) -> User:
        """Load the user a token record points at.

        :param record: A validated verification-token record.
        :return: The user the activation link belongs to.
        :raises InvalidVerificationTokenError: If the user no longer exists.
        """
        user = self._session.get(User, record.user_id)
        if user is None:
            raise InvalidVerificationTokenError(_INVALID_MESSAGE)
        return user

    def _get_user_by_email(self, email: str) -> User | None:
        """Find a user by normalized email.

        :param email: Email address (case-insensitive).
        :return: The user, or None when not found.
        """
        statement = select(User).where(User.email == email.lower())
        return self._session.exec(statement).first()

    def _invalidate_outstanding(self, user: User) -> None:
        """Queue all of the user's not-yet-used tokens to be marked used.

        The change is flushed by the caller's commit, keeping invalidation and
        new-token creation in a single transaction.

        :param user: The user whose outstanding tokens should be invalidated.
        """
        statement = select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id,
            col(EmailVerificationToken.used_at).is_(None),
        )
        now = utc_now()
        for token in self._session.exec(statement).all():
            token.used_at = now
            self._session.add(token)
