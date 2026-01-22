"""User management routes: profile, password, photo, account deletion."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.auth.dependencies import CurrentUser
from api.dependencies import get_storage_service, get_user_service
from api.schemas import ChangePasswordRequest, UpdateUserRequest, UserResponse
from api.services.storage.azure_blob_service import AzureBlobStorageService
from api.services.storage.exceptions import StorageUploadError
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
        photo_url=current_user.photo_url,
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
        photo_url=updated.photo_url,
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


@router.post(
    "/me/photo",
    response_model=UserResponse,
    summary="Upload profile photo",
    responses={
        400: {"description": "Invalid file type or file too large"},
        503: {"description": "Storage service unavailable"},
    },
)
async def upload_photo(
    current_user: CurrentUser,
    file: Annotated[UploadFile, File(description="Profile photo (JPEG, PNG, GIF, WebP, max 5MB)")],
    user_service: Annotated[UserService, Depends(get_user_service)],
    storage_service: Annotated[AzureBlobStorageService | None, Depends(get_storage_service)],
) -> UserResponse:
    """Upload or replace user profile photo.

    :param current_user: Authenticated user
    :param file: Uploaded image file
    :param user_service: User service
    :param storage_service: Storage service (None if not configured)
    :return: Updated user profile
    """
    if storage_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo upload is not available",
        )

    # Validate content type
    if file.content_type not in AzureBlobStorageService.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed: JPEG, PNG, GIF, WebP",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > AzureBlobStorageService.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5 MB",
        )

    # Delete old photo if exists
    if current_user.photo_url:
        storage_service.delete_file(current_user.photo_url)

    # Upload new photo
    try:
        photo_url = storage_service.upload_file(
            file_content=content,
            file_name=file.filename or "photo.jpg",
            content_type=file.content_type,
            user_id=str(current_user.id),
        )
    except StorageUploadError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to upload photo",
        ) from err

    # Update user record
    updated_user = user_service.update_photo_url(current_user, photo_url)
    return UserResponse(
        id=str(updated_user.id),
        email=updated_user.email,
        first_name=updated_user.first_name,
        last_name=updated_user.last_name,
        photo_url=updated_user.photo_url,
    )


@router.delete(
    "/me/photo",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete profile photo",
)
def delete_photo(
    current_user: CurrentUser,
    user_service: Annotated[UserService, Depends(get_user_service)],
    storage_service: Annotated[AzureBlobStorageService | None, Depends(get_storage_service)],
) -> None:
    """Remove user profile photo.

    :param current_user: Authenticated user
    :param user_service: User service
    :param storage_service: Storage service
    """
    if not current_user.photo_url:
        return

    if storage_service:
        storage_service.delete_file(current_user.photo_url)

    user_service.update_photo_url(current_user, None)
