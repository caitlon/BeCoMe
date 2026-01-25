"""Authentication routes: register, login, logout, refresh, profile.

Exception handling follows OCP: all exceptions are handled
by centralized middleware, routes focus on business logic only.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from api.auth.dependencies import CurrentUser, get_current_token_payload
from api.auth.jwt import (
    TokenError,
    TokenPayload,
    create_access_token,
    create_token_pair,
    decode_refresh_token,
    revoke_token,
)
from api.auth.logging import log_login_success, log_registration
from api.config import get_settings
from api.dependencies import get_user_service
from api.middleware.rate_limit import RATE_LIMIT_AUTH, limiter
from api.schemas.auth import RefreshTokenRequest, RegisterRequest, TokenResponse, UserResponse
from api.services.user_service import UserService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
@limiter.limit(RATE_LIMIT_AUTH)
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


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get access + refresh tokens",
)
@limiter.limit(RATE_LIMIT_AUTH)
def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[UserService, Depends(get_user_service)],
) -> TokenResponse:
    """Authenticate user and return JWT tokens.

    Uses OAuth2 password flow: username field contains email.
    Returns both access token (short-lived) and refresh token (long-lived).
    InvalidCredentialsError is handled by centralized exception middleware.
    Rate limited to prevent brute-force password attacks.

    :param request: FastAPI request (for rate limiting)
    :param form_data: OAuth2 form with username (email) and password
    :param service: User service
    :return: JWT access and refresh tokens
    """
    user = service.authenticate(form_data.username, form_data.password)
    token_pair = create_token_pair(user.id)

    log_login_success(user.id, user.email, request)

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
@limiter.limit(RATE_LIMIT_AUTH)
def refresh_token(
    request: Request,
    data: RefreshTokenRequest,
) -> TokenResponse:
    """Get new access token using refresh token.

    The refresh token remains valid until expiration.
    Rate limited to prevent token abuse.

    :param request: FastAPI request (for rate limiting)
    :param data: Refresh token request
    :return: New access token
    :raises HTTPException: If refresh token is invalid
    """
    try:
        payload = decode_refresh_token(data.refresh_token)
    except TokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    settings = get_settings()
    new_access_token = create_access_token(payload.user_id, payload.jti)

    return TokenResponse(
        access_token=new_access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and revoke current token",
)
def logout(
    token_payload: Annotated[TokenPayload, Depends(get_current_token_payload)],
) -> None:
    """Revoke current access token.

    Adds the token's JTI to blacklist for the full refresh token lifetime,
    preventing further use of both access and refresh tokens.

    :param token_payload: Current token payload from JWT
    """
    revoke_token(token_payload.jti)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
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
