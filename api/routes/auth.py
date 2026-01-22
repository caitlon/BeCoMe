"""Authentication routes: register, login, profile.

Exception handling follows OCP: all exceptions are handled
by centralized middleware, routes focus on business logic only.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from api.auth.dependencies import CurrentUser
from api.auth.jwt import create_access_token
from api.auth.logging import log_login_success, log_registration
from api.dependencies import get_user_service
from api.middleware.rate_limit import RATE_LIMIT_AUTH, limiter
from api.schemas import RegisterRequest, TokenResponse, UserResponse
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
    summary="Login and get access token",
)
@limiter.limit(RATE_LIMIT_AUTH)
def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[UserService, Depends(get_user_service)],
) -> TokenResponse:
    """Authenticate user and return JWT token.

    Uses OAuth2 password flow: username field contains email.
    InvalidCredentialsError is handled by centralized exception middleware.
    Rate limited to prevent brute-force password attacks.

    :param request: FastAPI request (for rate limiting)
    :param form_data: OAuth2 form with username (email) and password
    :param service: User service
    :return: JWT access token
    """
    user = service.authenticate(form_data.username, form_data.password)
    token = create_access_token(user.id)

    log_login_success(user.id, user.email, request)

    return TokenResponse(access_token=token)


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
    )
