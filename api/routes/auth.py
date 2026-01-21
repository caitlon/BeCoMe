"""Authentication routes: register, login, profile."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from api.auth.dependencies import CurrentUser
from api.auth.jwt import create_access_token
from api.db.session import get_session
from api.exceptions import InvalidCredentialsError, UserExistsError
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
    session: Annotated[Session, Depends(get_session)],
) -> UserResponse:
    """Create a new user account.

    :param request: Registration data (email, password, name)
    :param session: Database session
    :return: Created user profile
    :raises HTTPException: 409 if email already registered
    """
    service = UserService(session)
    try:
        user = service.create_user(
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
        )
    except UserExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from e

    return UserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        photo_url=user.photo_url,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get access token",
)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
) -> TokenResponse:
    """Authenticate user and return JWT token.

    Uses OAuth2 password flow: username field contains email.

    :param form_data: OAuth2 form with username (email) and password
    :param session: Database session
    :return: JWT access token
    :raises HTTPException: 401 if credentials invalid
    """
    service = UserService(session)
    try:
        user = service.authenticate(form_data.username, form_data.password)
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

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
        photo_url=current_user.photo_url,
    )
