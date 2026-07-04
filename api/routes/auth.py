"""Authentication routes: register, login, logout, refresh, profile.

Exception handling follows OCP: all exceptions are handled
by centralized middleware, routes focus on business logic only.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from api.auth.cookies import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    new_csrf_token,
    set_auth_cookies,
)
from api.auth.dependencies import CurrentUser, get_current_token_payload
from api.auth.jwt import (
    TokenError,
    TokenPair,
    TokenPayload,
    create_token_pair,
    decode_refresh_token,
    refresh_token_ttl_seconds,
    revoke_token,
)
from api.auth.logging import (
    log_login_success,
    log_password_reset_completed,
    log_password_reset_requested,
    log_registration,
)
from api.auth.login_throttle import LoginThrottle, get_login_throttle
from api.auth.reset_throttle import ResetEmailThrottle, get_reset_email_throttle
from api.auth.revocation_store import RevocationStore, get_revocation_store
from api.dependencies import get_email_service, get_password_reset_service, get_user_service
from api.exceptions import InvalidCredentialsError, LoginThrottledError
from api.middleware.rate_limit import LIMIT_AUTH_ENDPOINTS, LIMIT_PWD_RESET, limiter
from api.schemas.auth import (
    ForgotPasswordRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from api.services.email.base import EmailSender
from api.services.email.exceptions import EmailSendError
from api.services.password_reset_service import PasswordResetService
from api.services.user_service import UserService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

logger = logging.getLogger("api.route.auth")


def _set_session_cookies(response: Response, token_pair: TokenPair) -> None:
    """Attach the access, refresh, and CSRF cookies for a freshly issued token pair.

    :param response: The response to set cookies on.
    :param token_pair: The newly minted access/refresh pair.
    """
    set_auth_cookies(
        response,
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        csrf_token=new_csrf_token(),
        access_ttl=token_pair.expires_in,
        refresh_ttl=refresh_token_ttl_seconds(),
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
@limiter.limit(LIMIT_AUTH_ENDPOINTS)
def register(
    request: Request,
    data: RegisterRequest,
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Create a new user account.

    UserExistsError is handled by centralized exception middleware.
    Rate limited to prevent mass registration attacks.

    :param request: FastAPI request (for rate limiting)
    :param data: Registration data (email, password, name)
    :param service: User service
    :return: Created user profile
    """
    user = service.create_user(
        email=data.email,
        password=data.password,
        first_name=data.first_name,
        last_name=data.last_name,
    )

    log_registration(user.id, user.email, request)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
    )


@router.post("/login", summary="Login and get access + refresh tokens")
@limiter.limit(LIMIT_AUTH_ENDPOINTS)
def login(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[UserService, Depends(get_user_service)],
    store: Annotated[RevocationStore, Depends(get_revocation_store)],
    throttle: Annotated[LoginThrottle, Depends(get_login_throttle)],
) -> TokenResponse:
    """Authenticate user and return JWT tokens.

    Uses OAuth2 password flow: username field contains email.
    Returns both access token (short-lived) and refresh token (long-lived).
    A fresh session (rotation family) is registered so later refreshes can be
    rotated atomically and a reused refresh token can be contained.
    Failed attempts are counted per account and the account is locked for a cooldown
    once the threshold is passed, so guesses cannot simply be spread across many IPs.
    InvalidCredentialsError is handled by centralized exception middleware.
    Rate limited to prevent brute-force password attacks.

    :param request: FastAPI request (for rate limiting)
    :param form_data: OAuth2 form with username (email) and password
    :param service: User service
    :param store: Revocation store (records the new session's current token)
    :param throttle: Per-account login throttle (lockout after repeated failures)
    :return: JWT access and refresh tokens
    """
    if throttle.is_locked(form_data.username):
        raise LoginThrottledError
    try:
        user = service.authenticate(form_data.username, form_data.password)
    except InvalidCredentialsError:
        throttle.record_failure(form_data.username)
        raise
    throttle.reset(form_data.username)
    token_pair = create_token_pair(user.id)
    store.start_session(token_pair.sid, token_pair.jti, refresh_token_ttl_seconds())
    _set_session_cookies(response, token_pair)

    log_login_success(user.id, user.email, request)

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
    )


@router.post("/refresh", summary="Refresh access token")
@limiter.limit(LIMIT_AUTH_ENDPOINTS)
def refresh_token(
    request: Request,
    response: Response,
    store: Annotated[RevocationStore, Depends(get_revocation_store)],
    data: RefreshTokenRequest | None = None,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> TokenResponse:
    """Exchange a refresh token for a new access + refresh pair (rotation).

    The session's current refresh token is atomically consumed and a fresh pair is
    issued in the same family. Presenting an already-rotated (reused) refresh token
    is treated as theft: the whole family is revoked so neither the stolen token nor
    the legitimate one keeps working, and the caller must log in again. Rate limited.

    :param request: FastAPI request (for rate limiting)
    :param data: Refresh token request
    :param store: Revocation store (rotates the session, contains reuse)
    :return: New access and refresh tokens
    :raises HTTPException: If the refresh token is invalid, expired, revoked, or reused
    """
    # The SPA sends the refresh token via the HttpOnly cookie (which it cannot read into
    # a body); programmatic clients still post it in the request body.
    refresh = refresh_cookie or (data.refresh_token if data else None)
    if refresh is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_refresh_token(refresh, store)
    except TokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    ttl = refresh_token_ttl_seconds()
    if payload.sid:
        # Atomically consume the family's current refresh token and issue the next
        # pair in the same session. If the presented token is not the current one it
        # is a reused (already-rotated) token: revoke the whole family so a stolen
        # token cannot keep rotating, and return the same opaque 401.
        token_pair = create_token_pair(payload.user_id, sid=payload.sid)
        if not store.rotate_session(payload.sid, payload.jti, token_pair.jti, ttl):
            store.revoke_session(payload.sid, ttl)
            logger.warning(
                "Refresh token reuse detected; session revoked",
                extra={"event": "refresh_reuse_detected"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        _set_session_cookies(response, token_pair)
        return TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
        )

    # Legacy refresh token minted before sessions existed: revoke it and migrate to
    # the session model by starting a fresh family.
    revoke_token(payload.jti, store)
    token_pair = create_token_pair(payload.user_id)
    store.start_session(token_pair.sid, token_pair.jti, ttl)
    _set_session_cookies(response, token_pair)
    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and revoke current token",
)
def logout(
    response: Response,
    token_payload: Annotated[TokenPayload, Depends(get_current_token_payload)],
    store: Annotated[RevocationStore, Depends(get_revocation_store)],
) -> None:
    """Revoke the current session and clear the auth cookies.

    Blacklists the token's JTI and revokes its whole session, so every access and
    refresh token in the family stops working -- even a still-valid access token
    issued before an earlier rotation.

    :param response: Response used to clear the auth cookies.
    :param token_payload: Current token payload from JWT
    :param store: Revocation store
    """
    revoke_token(token_payload.jti, store)
    if token_payload.sid:
        store.revoke_session(token_payload.sid, refresh_token_ttl_seconds())
    clear_auth_cookies(response)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password reset email",
)
@limiter.limit(LIMIT_PWD_RESET)
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    service: Annotated[PasswordResetService, Depends(get_password_reset_service)],
    email_service: Annotated[EmailSender, Depends(get_email_service)],
    throttle: Annotated[ResetEmailThrottle, Depends(get_reset_email_throttle)],
) -> dict[str, str]:
    """Start the password reset flow for the given email.

    Always returns the same 202 response whether or not the email is registered,
    so the endpoint cannot reveal which addresses have accounts. When a user
    exists a reset link is emailed; send failures are swallowed for the same
    reason. Rate limited to slow abuse.

    :param request: FastAPI request (for rate limiting and logging)
    :param data: Email to send the reset link to
    :param service: Password reset service
    :param email_service: Email sender
    :return: A fixed acknowledgement message
    """
    # Cap reset emails per address (a hashed key) so a known inbox cannot be flooded by
    # rotating IPs past the per-IP limiter. The response is unchanged whether or not a
    # send happens, preserving the anti-enumeration guarantee.
    if throttle.allow(data.email):
        reset_url = service.create_reset_token(data.email)
        if reset_url is not None:
            try:
                await email_service.send_password_reset(to_email=data.email, reset_url=reset_url)
            except EmailSendError:
                logger.warning(
                    "Failed to send password reset email",
                    extra={"event": "password_reset_email_failed"},
                )

    log_password_reset_requested(data.email, request)
    return {"detail": "If that email is registered, a reset link has been sent."}


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset password using a token",
)
@limiter.limit(LIMIT_PWD_RESET)
def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    service: Annotated[PasswordResetService, Depends(get_password_reset_service)],
    store: Annotated[RevocationStore, Depends(get_revocation_store)],
) -> None:
    """Set a new password using a valid reset token.

    InvalidResetTokenError and ResetTokenExpiredError are handled by centralized
    middleware and both map to 400 with the same opaque message. Rate limited.
    Every token issued before the reset is invalidated (M1).

    :param request: FastAPI request (for rate limiting and logging)
    :param data: Reset token and new password
    :param service: Password reset service
    :param store: Revocation store (invalidates sessions issued before the reset)
    """
    user = service.reset_password(data.token, data.new_password)
    store.set_user_valid_after(user.id, datetime.now(UTC))
    log_password_reset_completed(user.id, request)


@router.get("/me", summary="Get current user profile")
def get_me(current_user: CurrentUser) -> UserResponse:
    """Return the authenticated user's profile.

    :param current_user: User from JWT token
    :return: User profile data
    """
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        photo_url=current_user.photo_url,
    )
