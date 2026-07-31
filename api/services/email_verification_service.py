"""Email verification business logic service."""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta

from sqlmodel import Session, select

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


@dataclass(frozen=True, slots=True)
class PendingCredentials:
    """The account details one registration submission asked for.

    Carried on the activation token instead of being written to the account, so a
    submission takes effect only when the link minted for *it* is redeemed. Writing
    them to the account at submission time is an account-takeover primitive: whoever
    submits last decides what everyone else's outstanding link opens.

    :param hashed_password: bcrypt hash of the submitted password.
    :param first_name: Submitted first name.
    :param last_name: Submitted last name.
    """

    hashed_password: str
    first_name: str
    last_name: str


def _carried_credentials(record: EmailVerificationToken) -> PendingCredentials | None:
    """Return the submission a token carries, if it carries one.

    The three columns are written together or left NULL together, which the table's
    ``ck_email_verification_tokens_credentials_complete`` constraint enforces; testing
    all three here is what lets the caller treat the result as a whole.

    :param record: A verification-token record.
    :return: The credentials to apply on redemption, or None for a link that only
        confirms the address.
    """
    if record.hashed_password is None or record.first_name is None or record.last_name is None:
        return None
    return PendingCredentials(
        hashed_password=record.hashed_password,
        first_name=record.first_name,
        last_name=record.last_name,
    )


class EmailVerificationService(BaseService):
    """Issue and redeem single-use, expiring email-verification tokens.

    Storage follows :class:`~api.services.password_reset_service.PasswordResetService`:
    only the SHA-256 hash of each token is stored and the raw token lives only long
    enough to be emailed. Issuing does *not* retire the outstanding tokens, which is
    where this flow deliberately parts company with password reset. Several people can
    submit a registration for the same unconfirmed address, each link carries its own
    submission, and retiring the others would let one submitter kill another's pending
    link. Each token is single-use and the first redemption verifies the address, after
    which the rest are refused.
    """

    def __init__(self, session: Session, user_cache: UserCacheStore | None = None) -> None:
        """Initialize with a DB session and an optional user cache.

        :param session: SQLModel session for database operations.
        :param user_cache: Cache to invalidate once an address becomes verified.
        """
        super().__init__(session)
        self._user_cache = user_cache

    def create_verification_url(
        self,
        user: User,
        credentials: PendingCredentials | None = None,
    ) -> str:
        """Issue an activation link for a user, optionally carrying a submission.

        Only the token hash is persisted; the raw token lives only inside the
        returned URL.

        :param user: The account whose address needs verifying.
        :param credentials: Details to write to the account when this link is
            redeemed, or None for a link that only confirms the address.
        :return: The full activation URL to email.
        """
        settings = get_settings()
        raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
        ttl = timedelta(hours=settings.email_verification_token_ttl_hours)
        token = EmailVerificationToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            hashed_password=credentials.hashed_password if credentials else None,
            first_name=credentials.first_name if credentials else None,
            last_name=credentials.last_name if credentials else None,
            expires_at=utc_now() + ttl,
        )
        self._save_and_refresh(token)
        logger.info(
            "Email verification token created",
            extra={"event": "verification_token_created", "user_id": str(user.id)},
        )
        return f"{settings.frontend_base_url}/verify-email?token={raw_token}"

    def find_unverified_account(self, email: str) -> User | None:
        """Return the account still waiting on this address, if there is one.

        Kept separate from minting so a caller can consult its own send budget before
        a token exists: charging a resend request for an address with nothing to send
        would let a stranger spend the budget a real signup needs.

        :param email: Email address from a resend request.
        :return: The unverified account, or None when no account has that address or
            it is already verified. The caller must respond identically either way to
            avoid user enumeration.
        """
        user = self._get_user_by_email(email)
        if user is None or user.email_verified_at is not None:
            logger.info(
                "Verification resend had nothing to send",
                extra={"event": "verification_resend_noop"},
            )
            return None
        return user

    def verify_email(self, token: str) -> User:
        """Consume an activation token, apply what it carries, and verify the address.

        Redeeming is refused once the address is verified, even for a token that is
        otherwise live. Without that, a token minted while the account was still
        unconfirmed could be redeemed later to overwrite the password of an account
        somebody is already using.

        :param token: The raw token from the activation link.
        :return: The now-verified user.
        :raises InvalidVerificationTokenError: If the token is unknown, already used,
            or its account is already verified.
        :raises VerificationTokenExpiredError: If the token has expired.
        """
        record = self._get_valid_record(token)
        user = self._get_account_to_activate(record)

        credentials = _carried_credentials(record)
        if credentials is not None:
            user.hashed_password = credentials.hashed_password
            user.first_name = credentials.first_name
            user.last_name = credentials.last_name

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

    def _get_account_to_activate(self, record: EmailVerificationToken) -> User:
        """Load the account a token record points at, and check it still needs activating.

        :param record: A validated verification-token record.
        :return: The unverified user the activation link belongs to.
        :raises InvalidVerificationTokenError: If the user no longer exists or the
            address is already verified.
        """
        user = self._session.get(User, record.user_id)
        if user is None or user.email_verified_at is not None:
            raise InvalidVerificationTokenError(_INVALID_MESSAGE)
        return user

    def _get_user_by_email(self, email: str) -> User | None:
        """Find a user by normalized email.

        :param email: Email address (case-insensitive).
        :return: The user, or None when not found.
        """
        statement = select(User).where(User.email == email.lower())
        return self._session.exec(statement).first()
