"""Centralized exception handlers for the API.

This module implements the Open/Closed Principle (OCP) by providing
a single place to handle all API exceptions. Adding new exception types
requires only adding a new entry to EXCEPTION_MAP, not modifying route handlers.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from api.exceptions import (
    BeCoMeAPIError,
    InvalidCredentialsError,
    InvitationAlreadyUsedError,
    InvitationExpiredError,
    InvitationNotFoundError,
    MemberNotFoundError,
    NotFoundError,
    OpinionNotFoundError,
    ProjectNotFoundError,
    ScaleRangeError,
    UserAlreadyMemberError,
    UserExistsError,
    ValidationError,
    ValuesOutOfRangeError,
)

# Exception to HTTP status code and message mapping
# Following OCP: extend by adding entries, not modifying handlers
# None as detail means: use exception message
EXCEPTION_MAP: dict[type[BeCoMeAPIError], tuple[int, str | None]] = {
    # 404 Not Found
    ProjectNotFoundError: (status.HTTP_404_NOT_FOUND, "Project not found"),
    MemberNotFoundError: (
        status.HTTP_404_NOT_FOUND,
        "User is not a member of this project",
    ),
    OpinionNotFoundError: (
        status.HTTP_404_NOT_FOUND,
        "You have not submitted an opinion for this project",
    ),
    InvitationNotFoundError: (status.HTTP_404_NOT_FOUND, "Invitation not found"),
    # 400 Bad Request
    InvitationExpiredError: (status.HTTP_400_BAD_REQUEST, "Invitation has expired"),
    InvitationAlreadyUsedError: (
        status.HTTP_400_BAD_REQUEST,
        "Invitation has already been used",
    ),
    # 401 Unauthorized
    InvalidCredentialsError: (
        status.HTTP_401_UNAUTHORIZED,
        "Incorrect email or password",
    ),
    # 409 Conflict
    UserExistsError: (status.HTTP_409_CONFLICT, "Email already registered"),
    UserAlreadyMemberError: (
        status.HTTP_409_CONFLICT,
        "You are already a member of this project",
    ),
    # 422 Unprocessable Content
    ValuesOutOfRangeError: (status.HTTP_422_UNPROCESSABLE_CONTENT, None),  # Use exception message
    ScaleRangeError: (status.HTTP_422_UNPROCESSABLE_CONTENT, None),  # Use exception message
}

# Default mappings for base exception classes
DEFAULT_STATUS_CODES: dict[type[BeCoMeAPIError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    BeCoMeAPIError: status.HTTP_400_BAD_REQUEST,
}


def _get_status_and_detail(exc: BeCoMeAPIError) -> tuple[int, str]:
    """Get HTTP status code and detail message for an exception.

    :param exc: The exception instance
    :return: Tuple of (status_code, detail_message)
    """
    exc_type = type(exc)

    # Check exact match first
    if exc_type in EXCEPTION_MAP:
        status_code, default_detail = EXCEPTION_MAP[exc_type]
        detail = default_detail if default_detail else str(exc)
        return status_code, detail

    # Fall back to base class mapping
    for base_class, default_status in DEFAULT_STATUS_CODES.items():
        if isinstance(exc, base_class):
            return default_status, str(exc)

    # Ultimate fallback
    return status.HTTP_400_BAD_REQUEST, str(exc)


async def become_api_error_handler(request: Request, exc: BeCoMeAPIError) -> JSONResponse:
    """Handle all BeCoMeAPIError exceptions.

    :param request: FastAPI request
    :param exc: The exception instance
    :return: JSON response with error detail
    """
    status_code, detail = _get_status_and_detail(exc)

    # Special headers for auth errors
    headers = None
    if isinstance(exc, InvalidCredentialsError):
        headers = {"WWW-Authenticate": "Bearer"}

    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app.

    Call this in create_app() to enable centralized error handling.

    :param app: FastAPI application instance
    """
    app.add_exception_handler(BeCoMeAPIError, become_api_error_handler)  # type: ignore[arg-type]
