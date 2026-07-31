"""Email verification business logic service."""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import update
from sqlmodel import Session, col, select

from api.auth.password import verify_password
from api.config import get_settings
from api.db.models import EmailVerificationToken, User
from api.db.utils import ensure_utc, utc_now
from api.exceptions import (
    InvalidVerificationTokenError,
    VerificationPasswordMismatchError,
    VerificationTokenExpiredError,
)
from api.services.base import BaseService
from api.services.user_cache import UserCacheStore

logger = logging.getLogger("api.service.email_verification")

# Entropy for the raw verification token; token_urlsafe(32) yields a ~43-character string.
_TOKEN_BYTES = 32

# One opaque message for unknown, used, and expired tokens so a caller cannot
# tell them apart (avoids a token-state oracle).
_INVALID_MESSAGE = "Invalid or expired verification link"

# The password posted with the link is not the one the link carries. Kept separate from
# the message above on purpose -- see VerificationPasswordMismatchError.
_MISMATCH_MESSAGE = "Password does not match this activation link"


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
    submission takes effect only when the link minted for *it* is redeemed, and only
    for someone who can restate its password. Writing them to the account at submission
    time is an account-takeover primitive: whoever submits last decides what everyone
    else's outstanding link opens.

    :param hashed_password: bcrypt hash of the submitted password.
    :param first_name: Submitted first name.
    :param last_name: Submitted last name.
    """

    hashed_password: str
    first_name: str
    last_name: str


@dataclass(frozen=True, slots=True)
class PendingActivation:
    """A live activation token together with the account it would open.

    Resolving and redeeming are two calls rather than one so the route can weigh the
    account's login lockout in between: the account is only known once the token has
    been resolved, and a locked account must be refused before another password guess
    is evaluated.

    :param record: The validated, unspent token record.
    :param user: The still-unverified account the token belongs to.
    """

    record: EmailVerificationToken
    user: User

    @property
    def email(self) -> str:
        """Return the address of the account this link would activate.

        :return: The account's normalized email, used to key the login lockout.
        """
        return self.user.email

    @property
    def user_id(self) -> UUID:
        """Return the id of the account this link would activate.

        :return: The account's id, for the security log.
        """
        return self.user.id


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

    Redemption takes the token *and* the password that minted it. A link alone is
    therefore not enough: an activation mail that reaches an inbox its submitter does
    not control cannot be followed to completion by the recipient, who does not know
    the submitted password, nor by the submitter, who never sees the link.
    """

    def __init__(self, session: Session, user_cache: UserCacheStore | None = None) -> None:
        """Initialize with a DB session and an optional user cache.

        :param session: SQLModel session for database operations.
        :param user_cache: Cache to invalidate once an address becomes verified.
        """
        super().__init__(session)
        self._user_cache = user_cache

    def create_verification_url(self, user: User, credentials: PendingCredentials) -> str:
        """Issue an activation link carrying one submission.

        Only the token hash is persisted; the raw token lives only inside the
        returned URL.

        :param user: The account whose address needs verifying.
        :param credentials: Details to write to the account when this link is redeemed,
            whose password also has to be restated to redeem it.
        :return: The full activation URL to email.
        """
        settings = get_settings()
        raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
        ttl = timedelta(hours=settings.email_verification_token_ttl_hours)
        token = EmailVerificationToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            hashed_password=credentials.hashed_password,
            first_name=credentials.first_name,
            last_name=credentials.last_name,
            expires_at=utc_now() + ttl,
        )
        self._save_and_refresh(token)
        logger.info(
            "Email verification token created",
            extra={"event": "verification_token_created", "user_id": str(user.id)},
        )
        return f"{settings.frontend_base_url}/verify-email?token={raw_token}"

    def create_resend_url(self, user: User, hashed_password: str) -> str:
        """Issue an activation link for a resend request.

        A resend carries a submission like any other link: the password comes from the
        resend request, so redeeming it still requires restating that password, and the
        names come from the account, which is all a resend request supplies. Without a
        submission a resend would hand out a link anybody receiving the mail could
        follow, which is the primitive the whole flow removes.

        :param user: The unverified account the link belongs to.
        :param hashed_password: bcrypt hash of the password submitted with the request.
        :return: The full activation URL to email.
        """
        return self.create_verification_url(
            user,
            PendingCredentials(
                hashed_password=hashed_password,
                first_name=user.first_name,
                last_name=user.last_name,
            ),
        )

    def find_unverified_account(self, email: str) -> User | None:
        """Return the account still waiting on this address, if there is one.

        Kept separate from minting so a caller can consult its own send budget before
        a token exists: charging a resend request for an address with nothing to send
        would let a stranger spend the budget a real signup needs.

        The ``verification_resend_noop`` record this writes names no account, but it
        does say which branch ran, and it carries the request id every other record in
        the same request carries. A reader of the full application log can therefore
        recover whether the address had a pending signup; the response cannot.

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

    def resolve_pending_activation(self, token: str) -> PendingActivation:
        """Resolve an activation token to the account it opens, without redeeming it.

        Every rejection here is the same opaque error, so a caller holding a bad token
        learns nothing about which kind of bad it is. Refusing an account that is
        already verified belongs here too: a token minted while the account was
        unconfirmed carries a password, so redeeming one afterwards would rewrite the
        credentials of an account somebody is already using. Refusing before the
        password is weighed also keeps this endpoint from being able to lock a live
        account out of its own login.

        :param token: The raw token from the activation link.
        :return: The token and the account it would activate.
        :raises InvalidVerificationTokenError: If the token is unknown, already used,
            or its account is gone or already verified.
        :raises VerificationTokenExpiredError: If the token has expired.
        """
        record = self._get_valid_record(token)
        return PendingActivation(record=record, user=self._get_account_to_activate(record))

    def activate(self, pending: PendingActivation, password: str) -> User:
        """Apply a resolved activation, once its password is restated.

        :param pending: The resolved token and account, from
            :meth:`resolve_pending_activation`.
        :param password: The plaintext password posted with the link.
        :return: The now-verified user.
        :raises VerificationPasswordMismatchError: If the password is not the one the
            token carries.
        :raises InvalidVerificationTokenError: If a concurrent redemption verified the
            account first.
        """
        record = pending.record
        user = pending.user
        if not verify_password(password, record.hashed_password):
            raise VerificationPasswordMismatchError(_MISMATCH_MESSAGE)

        self._claim_account(user, record)
        record.used_at = utc_now()
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

    def _claim_account(self, user: User, record: EmailVerificationToken) -> None:
        """Write the token's submission to the account, if no other redemption won.

        A conditional UPDATE rather than a read-then-write: two links for one
        unconfirmed address can be redeemed at the same moment, and both would pass the
        ``email_verified_at IS NULL`` check made a few statements earlier. Letting the
        database decide the winner means the losing redemption writes nothing at all,
        instead of overwriting the credentials the winner just applied.

        :param user: The account being activated.
        :param record: The token whose submission is being applied.
        :raises InvalidVerificationTokenError: If another redemption got there first.
        """
        result = self._session.exec(
            update(User)
            .where(col(User.id) == user.id, col(User.email_verified_at).is_(None))
            .values(
                hashed_password=record.hashed_password,
                first_name=record.first_name,
                last_name=record.last_name,
                email_verified_at=utc_now(),
            )
        )
        if result.rowcount != 1:
            raise InvalidVerificationTokenError(_INVALID_MESSAGE)

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
