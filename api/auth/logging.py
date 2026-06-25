"""Security event logging for authentication operations."""

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from api.utils.client_ip import get_client_ip

if TYPE_CHECKING:
    from fastapi import Request

# Configure security logger
logger = logging.getLogger("api.security")


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
            "email": email,
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
            "email": email,
            "reason": reason,
            "ip": ip,
        },
    )


def log_registration(user_id: UUID, email: str, request: "Request | None" = None) -> None:
    """Log new user registration.

    :param user_id: New user's ID
    :param email: User's email address
    :param request: FastAPI request (for IP extraction)
    """
    ip = get_client_ip(request)
    logger.info(
        "User registered",
        extra={
            "event": "registration",
            "user_id": str(user_id),
            "email": email,
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
            "email": email,
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
            "email": email,
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
