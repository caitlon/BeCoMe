"""Password reset business logic service."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from sqlmodel import col, select

from api.auth.password import hash_password
from api.config import get_settings
from api.db.models import PasswordResetToken, User
from api.db.utils import ensure_utc, utc_now
from api.exceptions import InvalidResetTokenError, ResetTokenExpiredError
from api.services.base import BaseService

logger = logging.getLogger("api.service.password_reset")

# Entropy for the raw reset token; token_urlsafe(32) yields a ~43-character string.
_TOKEN_BYTES = 32

# One opaque message for unknown, used, and expired tokens so a caller cannot
# tell them apart (avoids a token-state oracle).
_INVALID_MESSAGE = "Invalid or expired reset token"


def _hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of a raw reset token.

    :param raw_token: The raw, high-entropy token sent to the user.
    :return: 64-character hex digest stored in the database.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


class PasswordResetService(BaseService):
    """Issue and redeem single-use, expiring password-reset tokens.

    Only the SHA-256 hash of each token is stored; the raw token lives only long
    enough to be emailed. Redeeming a token does not revoke the user's existing
    access tokens (the JTI blacklist has no per-user revoke); this is acceptable
    given the short access-token lifetime.
    """

    def create_reset_token(self, email: str) -> str | None:
        """Issue a reset token for the given email, if a matching user exists.

        Any outstanding tokens for the user are invalidated first, so only the
        newest link works. Only the token hash is persisted; the raw token lives
        only inside the returned URL.

        :param email: Email address from the forgot-password request.
        :return: The full password-reset URL to email, or None when no user has
            that email. The caller must respond identically either way to avoid
            user enumeration.
        """
        user = self._get_user_by_email(email)
        if user is None:
            logger.info(
                "Password reset requested for unknown email",
                extra={"event": "password_reset_unknown_email"},
            )
            return None

        self._invalidate_outstanding(user)

        settings = get_settings()
        raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
        ttl = timedelta(minutes=settings.password_reset_token_ttl_minutes)
        token = PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            expires_at=utc_now() + ttl,
        )
        # Commits the invalidations queued above together with the new token.
        self._save_and_refresh(token)
        logger.info(
            "Password reset token created",
            extra={"event": "password_reset_token_created", "user_id": str(user.id)},
        )
        return f"{settings.frontend_base_url}/reset-password?token={raw_token}"

    def reset_password(self, token: str, new_password: str) -> User:
        """Consume a reset token and set the user's new password.

        :param token: The raw reset token from the reset link.
        :param new_password: The new plaintext password (already strength-checked).
        :return: The updated user.
        :raises InvalidResetTokenError: If the token is unknown or already used.
        :raises ResetTokenExpiredError: If the token has expired.
        """
        record = self._session.exec(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(token))
        ).first()

        if record is None or record.used_at is not None:
            raise InvalidResetTokenError(_INVALID_MESSAGE)
        if ensure_utc(record.expires_at) < utc_now():
            raise ResetTokenExpiredError(_INVALID_MESSAGE)

        user = self._session.get(User, record.user_id)
        if user is None:
            raise InvalidResetTokenError(_INVALID_MESSAGE)

        user.hashed_password = hash_password(new_password)
        record.used_at = utc_now()
        self._session.add(user)
        self._session.add(record)
        self._session.commit()
        self._session.refresh(user)

        logger.info(
            "Password reset completed",
            extra={"event": "password_reset_completed", "user_id": str(user.id)},
        )
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
        statement = select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            col(PasswordResetToken.used_at).is_(None),
        )
        now = utc_now()
        for token in self._session.exec(statement).all():
            token.used_at = now
            self._session.add(token)
