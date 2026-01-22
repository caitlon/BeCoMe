"""Security event logging for authentication operations."""

import logging
from typing import TYPE_CHECKING
from uuid import UUID

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
    ip = _get_client_ip(request) if request else "unknown"
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
    ip = _get_client_ip(request) if request else "unknown"
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
    ip = _get_client_ip(request) if request else "unknown"
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
    ip = _get_client_ip(request) if request else "unknown"
    logger.info(
        "Password changed",
        extra={
            "event": "password_change",
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
    ip = _get_client_ip(request) if request else "unknown"
    logger.info(
        "Account deleted",
        extra={
            "event": "account_deletion",
            "user_id": str(user_id),
            "email": email,
            "ip": ip,
        },
    )


def _get_client_ip(request: "Request | None") -> str:
    """Extract client IP from request, considering proxies.

    :param request: FastAPI request object
    :return: Client IP address string
    """
    if not request:
        return "unknown"

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    if request.client:
        return request.client.host

    return "unknown"
