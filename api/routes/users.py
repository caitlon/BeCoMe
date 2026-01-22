"""User management routes: profile, password, account deletion."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from api.auth.dependencies import CurrentUser
from api.dependencies import get_user_service
from api.schemas import ChangePasswordRequest, UpdateUserRequest, UserResponse
from api.services.user_service import UserService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
def get_current_user_profile(current_user: CurrentUser) -> UserResponse:
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


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
)
def update_current_user(
    current_user: CurrentUser,
    request: UpdateUserRequest,
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Update the authenticated user's profile.

    :param current_user: User from JWT token
    :param request: Fields to update
    :param service: User service
    :return: Updated user profile
    """
    updated = service.update_user(
        user=current_user,
        first_name=request.first_name,
        last_name=request.last_name,
    )
    return UserResponse(
        id=str(updated.id),
        email=updated.email,
        first_name=updated.first_name,
        last_name=updated.last_name,
    )


@router.put(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change current user password",
)
def change_password(
    current_user: CurrentUser,
    request: ChangePasswordRequest,
    service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    """Change the authenticated user's password.

    InvalidCredentialsError is handled by centralized exception middleware.

    :param current_user: User from JWT token
    :param request: Current and new password
    :param service: User service
    """
    service.change_password(
        user=current_user,
        current_password=request.current_password,
        new_password=request.new_password,
    )


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete current user account",
)
def delete_current_user(
    current_user: CurrentUser,
    service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    """Delete the authenticated user's account.

    :param current_user: User from JWT token
    :param service: User service
    """
    service.delete_user(current_user)
