"""Centralized exception handlers for the API.

This module implements the Open/Closed Principle (OCP) by providing
a single place to handle all API exceptions. Adding new exception types
requires only adding a new entry to EXCEPTION_MAP, not modifying route handlers.
"""

import logging
import math

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.auth.logging import log_login_failure, log_password_change_failure
from api.auth.revocation_store import RevocationStoreError
from api.exceptions import (
    AccountHasOwnedProjectsError,
    AlreadyInvitedError,
    BeCoMeAPIError,
    CurrentPasswordIncorrectError,
    DisposableEmailDomainError,
    EmailNotVerifiedError,
    ExampleProjectInvitationError,
    InvalidCredentialsError,
    InvalidResetTokenError,
    InvalidVerificationTokenError,
    InvitationAlreadyUsedError,
    InvitationExpiredError,
    InvitationNotFoundError,
    LoginThrottledError,
    MemberNotFoundError,
    NotFoundError,
    OpinionNotFoundError,
    PhotoContentMismatchError,
    PhotoDimensionsTooLargeError,
    PhotoTooLargeError,
    PhotoTypeNotAllowedError,
    PhotoUnreadableError,
    ProjectNotFoundError,
    ResetTokenExpiredError,
    ScaleExcludesOpinionsError,
    ScaleRangeError,
    TurnstileVerificationError,
    UnresolvableEmailDomainError,
    UserAlreadyMemberError,
    UserExistsError,
    UserNotFoundForInvitationError,
    ValidationError,
    ValuesOutOfRangeError,
    VerificationPasswordMismatchError,
    VerificationTokenExpiredError,
)
from api.services.storage.exceptions import (
    StorageConfigurationError,
    StorageDeleteError,
    StorageError,
    StorageUploadError,
)

logger = logging.getLogger("api.exception")

# The 403 an unverified account gets when its password was correct. Kept distinct from
# every other 403 wording so the SPA can recognize this one case and offer to resend the
# activation link instead of showing a generic "forbidden".
EMAIL_NOT_VERIFIED_DETAIL = "Email address not verified. Check your inbox for the activation link."

# The 403 an activation link gets when the password posted with it is not the one the
# link carries. Deliberately its own status and wording: the opaque 400 the token errors
# share would tell a user who mistyped that their link is dead and send them off to
# request another, and the caller already holds the link, so confirming it is live
# concedes nothing. Repeated mismatches feed the account's login lockout.
VERIFICATION_PASSWORD_MISMATCH_DETAIL = (
    "That password does not match the sign-up this link was created for."  # noqa: S105
)

# The 403 a request gets when the Turnstile bot check refuses it. One wording for every
# refusal, an absent header included, so the response tells a caller nothing about what
# the check saw or whether it is switched on at all.
TURNSTILE_REFUSED_DETAIL = "Could not confirm you are human. Reload the page and try again."

# The machine-readable half of that answer. POST /auth/login can answer 403 for two
# unrelated reasons - an unverified account and a refused bot check - and they need
# different screens. Without a code the only thing separating them in the body is the
# English sentence above, and a client matching on that breaks the moment it is reworded.
#
# The code is one value for every refusal, exactly as the wording is, so it discriminates
# for the SPA without conceding anything to a caller: it cannot say whether a token was
# presented, which part of the check failed, or whether an account exists.
TURNSTILE_REFUSED_CODE = "turnstile_refused"

# The machine-readable half of the 409 a scale change gets when an existing opinion would
# fall outside the new range. PATCH /projects/{id} has no other 409, but a client acting on
# this one (offer to widen the range, point at the opinions) should not have to match the
# English sentence to tell it apart.
SCALE_EXCLUDES_OPINIONS_CODE = "scale_excludes_opinions"

# The machine-readable half of the 400 a password change gets when the current password is
# wrong. It is a 400 and not a 401 because on an authenticated request a 401 means "no
# session": the SPA refreshes the token, retries, and signs the user out. The session here
# is fine, so the answer carries a code the form can show beside the field instead.
CURRENT_PASSWORD_INCORRECT_CODE = "current_password_incorrect"  # noqa: S105  # pragma: allowlist secret

# The machine-readable halves of the invitation refusals, so the SPA can translate them by
# code and the English sentence can be reworded without breaking a screen. One code per
# exception, and each exception has exactly one status and sentence.
INVITEE_NOT_FOUND_CODE = "invitee_not_found"
ALREADY_INVITED_CODE = "already_invited"
ALREADY_MEMBER_CODE = "already_member"
EXAMPLE_PROJECT_NOT_INVITABLE_CODE = "example_project_not_invitable"
# One code for a missing invitation and for one that belongs to someone else: they share a
# body, so a code that told them apart would reopen the question that body closes.
INVITATION_NOT_FOUND_CODE = "invitation_not_found"

# The machine-readable halves of the five 400s a profile photo upload can get, one per check
# that refuses the file, so the form can say what to change.
PHOTO_TYPE_NOT_ALLOWED_CODE = "photo_type_not_allowed"
PHOTO_TOO_LARGE_CODE = "photo_too_large"
PHOTO_CONTENT_MISMATCH_CODE = "photo_content_mismatch"
PHOTO_UNREADABLE_CODE = "photo_unreadable"
PHOTO_DIMENSIONS_TOO_LARGE_CODE = "photo_dimensions_too_large"

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
    # Fixed copy on purpose: the exception message names the address that was invited, and
    # the response must not repeat it.
    UserNotFoundForInvitationError: (status.HTTP_404_NOT_FOUND, "No user found with this email"),
    # 400 Bad Request
    InvitationExpiredError: (status.HTTP_400_BAD_REQUEST, "Invitation has expired"),
    InvitationAlreadyUsedError: (
        status.HTTP_400_BAD_REQUEST,
        "Invitation has already been used",
    ),
    # Same opaque message for invalid and expired so neither can be distinguished.
    InvalidResetTokenError: (status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token"),
    ResetTokenExpiredError: (status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token"),
    # Same treatment for the activation link: unknown, spent, and expired are one message.
    InvalidVerificationTokenError: (
        status.HTTP_400_BAD_REQUEST,
        "Invalid or expired verification link",
    ),
    VerificationTokenExpiredError: (
        status.HTTP_400_BAD_REQUEST,
        "Invalid or expired verification link",
    ),
    # Email-policy rejections (api/services/email_policy.py). Each carries its own
    # distinguishable copy: both depend solely on the domain string, never on
    # database state, so neither can leak whether an account already exists.
    DisposableEmailDomainError: (
        status.HTTP_400_BAD_REQUEST,
        "That looks like a temporary address",
    ),
    UnresolvableEmailDomainError: (
        status.HTTP_400_BAD_REQUEST,
        "We could not find that domain. Check for a typo.",
    ),
    CurrentPasswordIncorrectError: (
        status.HTTP_400_BAD_REQUEST,
        "Current password is incorrect",
    ),
    # Profile-photo upload refusals (POST /users/me/photo).
    PhotoTypeNotAllowedError: (
        status.HTTP_400_BAD_REQUEST,
        "Invalid file type. Allowed: JPEG, PNG, GIF, WebP",
    ),
    PhotoTooLargeError: (status.HTTP_400_BAD_REQUEST, "File too large. Maximum size is 5 MB"),
    PhotoContentMismatchError: (
        status.HTTP_400_BAD_REQUEST,
        "File content does not match declared type",
    ),
    PhotoUnreadableError: (
        status.HTTP_400_BAD_REQUEST,
        "The image could not be read. Try saving it again as JPEG or PNG.",
    ),
    PhotoDimensionsTooLargeError: (
        status.HTTP_400_BAD_REQUEST,
        "Image dimensions are too large. Maximum is 4096x4096 pixels",
    ),
    # 401 Unauthorized
    InvalidCredentialsError: (
        status.HTTP_401_UNAUTHORIZED,
        "Incorrect email or password",
    ),
    # 403 Forbidden
    EmailNotVerifiedError: (status.HTTP_403_FORBIDDEN, EMAIL_NOT_VERIFIED_DETAIL),
    VerificationPasswordMismatchError: (
        status.HTTP_403_FORBIDDEN,
        VERIFICATION_PASSWORD_MISMATCH_DETAIL,
    ),
    TurnstileVerificationError: (status.HTTP_403_FORBIDDEN, TURNSTILE_REFUSED_DETAIL),
    # 429 Too Many Requests
    LoginThrottledError: (
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Too many failed login attempts. Please try again later.",
    ),
    # 409 Conflict
    AccountHasOwnedProjectsError: (
        status.HTTP_409_CONFLICT,
        "Cannot delete your account while you are the admin of one or more projects. "
        "Transfer ownership or delete those projects first.",
    ),
    ScaleExcludesOpinionsError: (
        status.HTTP_409_CONFLICT,
        "Existing opinions fall outside the new scale. "
        "Widen the range, or ask the experts to change their opinions first.",
    ),
    UserExistsError: (status.HTTP_409_CONFLICT, "Email already registered"),
    UserAlreadyMemberError: (
        status.HTTP_409_CONFLICT,
        "You are already a member of this project",
    ),
    AlreadyInvitedError: (status.HTTP_409_CONFLICT, "User already has a pending invitation"),
    # The invite route catches this to log the rejection and re-raises it, so the invite and
    # accept routes answer through this one entry.
    ExampleProjectInvitationError: (
        status.HTTP_409_CONFLICT,
        "The example project cannot take invitations",
    ),
    # 422 Unprocessable Content
    ValuesOutOfRangeError: (status.HTTP_422_UNPROCESSABLE_CONTENT, None),  # Use exception message
    ScaleRangeError: (status.HTTP_422_UNPROCESSABLE_CONTENT, None),  # Use exception message
    # 503 Service Unavailable, for storage faults.
    # These carry the raw botocore text (bucket host, object key, S3 error code), and the
    # lookup below matches types exactly, so every subclass needs its own entry: without
    # one it falls through to BeCoMeAPIError and returns str(exc) to the caller. The photo
    # endpoint is public, so that text would be world-readable.
    StorageError: (status.HTTP_503_SERVICE_UNAVAILABLE, "Storage temporarily unavailable"),
    StorageConfigurationError: (status.HTTP_503_SERVICE_UNAVAILABLE, "Storage is not available"),
    StorageUploadError: (status.HTTP_503_SERVICE_UNAVAILABLE, "Failed to upload photo"),
    StorageDeleteError: (status.HTTP_503_SERVICE_UNAVAILABLE, "Failed to delete photo"),
}

# Stable codes for the answers a client has to branch on, sent as a "code" field beside
# "detail". Only exceptions that need one appear here: everything else keeps a body of
# exactly {"detail": ...}, so adding a code to one error changes no other response.
#
# Looked up by exact type, as EXCEPTION_MAP is. A subclass added later without an entry
# here also misses EXCEPTION_MAP, so it answers 400 rather than a 403 the SPA could
# mistake for one of these - the omission is loud rather than silent.
ERROR_CODES: dict[type[BeCoMeAPIError], str] = {
    TurnstileVerificationError: TURNSTILE_REFUSED_CODE,
    ScaleExcludesOpinionsError: SCALE_EXCLUDES_OPINIONS_CODE,
    CurrentPasswordIncorrectError: CURRENT_PASSWORD_INCORRECT_CODE,
    UserNotFoundForInvitationError: INVITEE_NOT_FOUND_CODE,
    AlreadyInvitedError: ALREADY_INVITED_CODE,
    UserAlreadyMemberError: ALREADY_MEMBER_CODE,
    ExampleProjectInvitationError: EXAMPLE_PROJECT_NOT_INVITABLE_CODE,
    InvitationNotFoundError: INVITATION_NOT_FOUND_CODE,
    PhotoTypeNotAllowedError: PHOTO_TYPE_NOT_ALLOWED_CODE,
    PhotoTooLargeError: PHOTO_TOO_LARGE_CODE,
    PhotoContentMismatchError: PHOTO_CONTENT_MISMATCH_CODE,
    PhotoUnreadableError: PHOTO_UNREADABLE_CODE,
    PhotoDimensionsTooLargeError: PHOTO_DIMENSIONS_TOO_LARGE_CODE,
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

    # Ultimate fallback (unreachable: BeCoMeAPIError is in DEFAULT_STATUS_CODES)
    return status.HTTP_400_BAD_REQUEST, str(exc)  # pragma: no cover


def become_api_error_handler(request: Request, exc: BeCoMeAPIError) -> JSONResponse:
    """Handle all BeCoMeAPIError exceptions.

    :param request: FastAPI request
    :param exc: The exception instance
    :return: JSON response with the error detail, plus a ``code`` for the exceptions
        that carry one (see ``ERROR_CODES``)
    """
    status_code, detail = _get_status_and_detail(exc)

    # Server faults are logged as errors, client faults as warnings.
    log = logger.error if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR else logger.warning
    log(
        "%s -> %d",
        type(exc).__name__,
        status_code,
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "status_code": status_code,
            "path": request.url.path,
            "exception_type": type(exc).__name__,
        },
    )

    # Special handling for auth errors
    headers = None
    if isinstance(exc, InvalidCredentialsError):
        headers = {"WWW-Authenticate": "Bearer"}
        if exc.email:
            log_login_failure(exc.email, exc.reason, request)
    elif isinstance(exc, CurrentPasswordIncorrectError):
        # A wrong current password is a distinct security event from a failed
        # login, so it does not pollute brute-force alerting on login_failure.
        log_password_change_failure(request)

    content: dict[str, str] = {"detail": detail}
    code = ERROR_CODES.get(type(exc))
    if code is not None:
        content["code"] = code

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=headers,
    )


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle any exception not covered by a more specific handler.

    Logs the full traceback at ERROR level and returns an opaque 500 so internal
    details never leak to the client.

    :param request: FastAPI request
    :param exc: The unhandled exception
    :return: Generic 500 JSON response
    """
    logger.error(
        "Unhandled exception",
        exc_info=exc,
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "path": request.url.path,
            "exception_type": type(exc).__name__,
        },
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


def revocation_store_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return 503 when the revocation/session store (Redis) is unreachable.

    The store is fail-closed, so a Redis fault raises ``RevocationStoreError``. Token
    validation already converts that to a 401, but the session-write calls in login,
    refresh, and logout would otherwise surface a raw 500; this maps them to a clean 503.

    :param request: FastAPI request.
    :param exc: The raised ``RevocationStoreError``.
    :return: A 503 JSON response.
    """
    logger.error(
        "Revocation store unavailable",
        exc_info=exc,
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "path": request.url.path,
            "exception_type": type(exc).__name__,
        },
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Service temporarily unavailable, please try again"},
    )


def _finite_or_str(value: float) -> float | str:
    """Return a finite float unchanged and the string form of ``nan``, ``inf`` or ``-inf``."""
    return value if math.isfinite(value) else str(value)


def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return 422 for a failed request validation, in FastAPI's default body shape.

    ``JSONResponse`` cannot render a non-finite float, and Pydantic echoes the rejected
    input back in the error, so the default handler turned a rejected NaN into a 500.

    :param request: FastAPI request
    :param exc: The request validation error
    :return: 422 JSON response with ``{"detail": [...]}``, non-finite inputs as strings
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(exc.errors(), custom_encoder={float: _finite_or_str})},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app.

    Call this in create_app() to enable centralized error handling.

    :param app: FastAPI application instance
    """
    app.add_exception_handler(BeCoMeAPIError, become_api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RevocationStoreError, revocation_store_unavailable_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
