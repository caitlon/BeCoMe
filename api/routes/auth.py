"""Authentication routes: register, login, profile.

Exception handling follows OCP: all exceptions are handled
by centralized middleware, routes focus on business logic only.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from api.auth.dependencies import CurrentUser
from api.auth.jwt import create_access_token
from api.dependencies import get_user_service
from api.schemas import RegisterRequest, TokenResponse, UserResponse
from api.services.user_service import UserService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(
    request: RegisterRequest,
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Create a new user account.

    UserExistsError is handled by centralized exception middleware.

    :param request: Registration data (email, password, name)
    :param service: User service
    :return: Created user profile
    """
    user = service.create_user(
        email=request.email,
        password=request.password,
        first_name=request.first_name,
        last_name=request.last_name,
    )

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
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[UserService, Depends(get_user_service)],
) -> TokenResponse:
    """Authenticate user and return JWT token.

    Uses OAuth2 password flow: username field contains email.
    InvalidCredentialsError is handled by centralized exception middleware.

    :param form_data: OAuth2 form with username (email) and password
    :param service: User service
    :return: JWT access token
    """
    user = service.authenticate(form_data.username, form_data.password)
    token = create_access_token(user.id)
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
