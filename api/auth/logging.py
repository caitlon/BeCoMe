"""Security event logging for authentication operations."""

import hmac
import logging
from hashlib import sha256
from typing import TYPE_CHECKING
from uuid import UUID

from api.config import get_settings
from api.utils.client_ip import get_client_ip

if TYPE_CHECKING:
    from fastapi import Request

# Configure security logger
logger = logging.getLogger("api.security")

# Length of the hex tag written to logs. Enough to correlate attempts on one account
# without carrying the full digest around.
_EMAIL_TAG_LENGTH = 16


def hash_email(email: str) -> str:
    """Return a short, keyed tag for an email.

    Security events log this instead of the raw address so a log drain or Sentry
    breach cannot harvest a registry of user emails, while repeated attempts on the
    same account can still be correlated (log data-minimization, GDPR).

    The tag is an HMAC, not a plain digest: a plain SHA-256 of an address is
    reproducible by anyone holding the logs, so they could confirm whether a given
    person has an account by hashing a guess. Keying it makes the tag meaningless
    outside this application. The key is ``log_hash_key`` when set, otherwise
    ``secret_key`` -- note that rotating the fallback also re-tags every future
    record, so set ``LOG_HASH_KEY`` explicitly to keep tags stable across a rotation.

    :param email: The email address to tag.
    :return: A truncated hex HMAC-SHA-256 of the normalized email.
    """
    settings = get_settings()
    key = settings.log_hash_key or settings.secret_key
    tag = hmac.new(key.encode(), email.strip().lower().encode(), sha256)
    return tag.hexdigest()[:_EMAIL_TAG_LENGTH]


def log_login_success(user_id: UUID, email: str, request: "Request | None" = None) -> None:
    """Log successful login attempt.

    :param user_id: Authenticated user's ID
    :param email: User's email address
    :param request: FastAPI request (for IP extraction)
    """
    ip = get_client_ip(request)
    logger.info(
        "Login successful",
        extra={
            "event": "login_success",
            "user_id": str(user_id),
            "email_hash": hash_email(email),
            "ip": ip,
        },
    )


def log_login_failure(email: str, reason: str, request: "Request | None" = None) -> None:
    """Log failed login attempt.

    :param email: Attempted email address
    :param reason: Failure reason
    :param request: FastAPI request (for IP extraction)
    """
    ip = get_client_ip(request)
    logger.warning(
        "Login failed",
        extra={
            "event": "login_failure",
            "email_hash": hash_email(email),
            "reason": reason,
            "ip": ip,
        },
    )


def log_registration_attempt(email: str, request: "Request | None" = None) -> None:
    """Log a registration submission, whatever the endpoint decided to do with it.

    Deliberately identical for all three branches (new account, replaced unverified
    account, notice to an existing verified account) and carries no ``user_id``: the
    endpoint answers the same way in every case, and a log line that gave the branch
    away would turn the security log itself into an account-existence oracle for
    anyone who can read it. The account that actually gets created is recorded
    separately by ``UserService.create_user`` as ``user_created``.

    :param email: Email address the registration was submitted for
    :param request: FastAPI request (for IP extraction)
    """
    ip = get_client_ip(request)
    logger.info(
        "Registration attempted",
        extra={
            "event": "registration_attempt",
            "email_hash": hash_email(email),
            "ip": ip,
        },
    )


def log_login_blocked_unverified(user_id: UUID, request: "Request | None" = None) -> None:
    """Log a login refused because the account's address is still unverified.

    Kept apart from ``login_failure``: the password was correct, so counting it as a
    failed attempt would distort brute-force alerting.

    :param user_id: ID of the account that was refused
    :param request: FastAPI request (for IP extraction)
    """
    ip = get_client_ip(request)
    logger.warning(
        "Login blocked for an unverified account",
        extra={
            "event": "login_blocked_unverified",
            "user_id": str(user_id),
            "ip": ip,
        },
    )


def log_verification_email_requested(email: str, request: "Request | None" = None) -> None:
    """Log a resend-verification request.

    Carries no ``user_id`` for the same reason as the registration attempt: the
    endpoint answers identically for a known and an unknown address.

    :param email: Email address from the request
    :param request: FastAPI request (for IP extraction)
    """
    ip = get_client_ip(request)
    logger.info(
        "Verification email requested",
        extra={
            "event": "verification_email_requested",
            "email_hash": hash_email(email),
            "ip": ip,
        },
    )


def log_email_verified(user_id: UUID, request: "Request | None" = None) -> None:
    """Log a redeemed activation link.

    :param user_id: ID of the account that was activated
    :param request: FastAPI request (for IP extraction)
    """
    ip = get_client_ip(request)
    logger.info(
        "Email address verified",
        extra={
            "event": "email_verified",
            "user_id": str(user_id),
            "ip": ip,
        },
    )


def log_password_change(user_id: UUID, request: "Request | None" = None) -> None:
    """Log password change event.

    :param user_id: User's ID
    :param request: FastAPI request (for IP extraction)
    """
    ip = get_client_ip(request)
    logger.info(
        "Password changed",
        extra={
            "event": "password_change",
            "user_id": str(user_id),
            "ip": ip,
        },
    )


def log_password_change_failure(request: "Request | None" = None) -> None:
    """Log a failed password change (wrong current password).

    Kept as a distinct event so brute-force alerting on ``login_failure`` is not
    polluted by password-change attempts. The acting ``user_id`` is bound by the
    logging ContextFilter from the authenticated request.

    :param request: FastAPI request (for IP extraction)
    """
    ip = get_client_ip(request)
    logger.warning(
        "Password change failed",
        extra={
            "event": "password_change_failure",
            "ip": ip,
        },
    )


def log_password_reset_requested(email: str, request: "Request | None" = None) -> None:
    """Log a password reset request (forgot-password).

    :param email: Email address from the request
    :param request: FastAPI request (for IP extraction)
    """
    ip = get_client_ip(request)
    logger.info(
        "Password reset requested",
        extra={
            "event": "password_reset_requested",
            "email_hash": hash_email(email),
            "ip": ip,
        },
    )


def log_password_reset_completed(user_id: UUID, request: "Request | None" = None) -> None:
    """Log a completed password reset.

    :param user_id: User's ID
    :param request: FastAPI request (for IP extraction)
    """
    ip = get_client_ip(request)
    logger.info(
        "Password reset completed",
        extra={
            "event": "password_reset_completed",
            "user_id": str(user_id),
            "ip": ip,
        },
    )


def log_account_deletion(user_id: UUID, email: str, request: "Request | None" = None) -> None:
    """Log account deletion event.

    :param user_id: Deleted user's ID
    :param email: User's email address
    :param request: FastAPI request (for IP extraction)
    """
    ip = get_client_ip(request)
    logger.info(
        "Account deleted",
        extra={
            "event": "account_deletion",
            "user_id": str(user_id),
            "email_hash": hash_email(email),
            "ip": ip,
        },
    )


def log_data_export(user_id: UUID, request: "Request | None" = None) -> None:
    """Log a GDPR data export download (Article 20).

    :param user_id: ID of the user who exported their data
    :param request: FastAPI request (for IP extraction)
    """
    ip = get_client_ip(request)
    logger.info(
        "Data export downloaded",
        extra={
            "event": "data_export",
            "user_id": str(user_id),
            "ip": ip,
        },
    )
