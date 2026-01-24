"""User management routes: profile, password, photo, account deletion."""

from contextlib import suppress
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from api.auth.dependencies import CurrentUser
from api.auth.logging import log_account_deletion, log_password_change
from api.dependencies import get_storage_service, get_user_service
from api.middleware.rate_limit import RATE_LIMIT_PASSWORD, RATE_LIMIT_UPLOAD, limiter
from api.schemas import ChangePasswordRequest, UpdateUserRequest, UserResponse
from api.services.storage.supabase_storage_service import SupabaseStorageService
from api.services.storage.exceptions import StorageDeleteError, StorageUploadError
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
@limiter.limit(RATE_LIMIT_PASSWORD)
def change_password(
    request: Request,
    current_user: CurrentUser,
    data: ChangePasswordRequest,
    service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    """Change the authenticated user's password.

    InvalidCredentialsError is handled by centralized exception middleware.
    Rate limited to prevent password guessing attacks.

    :param request: FastAPI request (for rate limiting)
    :param current_user: User from JWT token
    :param data: Current and new password
    :param service: User service
    """
    service.change_password(
        user=current_user,
        current_password=data.current_password,
        new_password=data.new_password,
    )

    log_password_change(current_user.id, request)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete current user account",
)
def delete_current_user(
    request: Request,
    current_user: CurrentUser,
    service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    """Delete the authenticated user's account.

    :param request: FastAPI request (for logging)
    :param current_user: User from JWT token
    :param service: User service
    """
    user_id = current_user.id
    email = current_user.email

    service.delete_user(current_user)

    log_account_deletion(user_id, email, request)


@router.post(
    "/me/photo",
    response_model=UserResponse,
    summary="Upload profile photo",
    responses={
        400: {"description": "Invalid file type or file too large"},
        503: {"description": "Storage service unavailable"},
    },
)
@limiter.limit(RATE_LIMIT_UPLOAD)
async def upload_photo(
    request: Request,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File(description="Profile photo (JPEG, PNG, GIF, WebP, max 5MB)")],
    user_service: Annotated[UserService, Depends(get_user_service)],
    storage_service: Annotated[SupabaseStorageService | None, Depends(get_storage_service)],
) -> UserResponse:
    """Upload or replace user profile photo.

    Rate limited to prevent storage abuse.

    :param request: FastAPI request (for rate limiting)
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
    if file.content_type not in SupabaseStorageService.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed: JPEG, PNG, GIF, WebP",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > SupabaseStorageService.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5 MB",
        )

    # Validate actual file content matches claimed type (magic bytes check)
    if not SupabaseStorageService.validate_image_content(content, file.content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match declared type",
        )

    # Delete old photo if exists (ignore errors to allow upload to proceed)
    if current_user.photo_url:
        with suppress(StorageDeleteError):
            storage_service.delete_file(current_user.photo_url)

    # Upload new photo
    try:
        photo_url = storage_service.upload_file(
            file_content=content,
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
    storage_service: Annotated[SupabaseStorageService | None, Depends(get_storage_service)],
) -> None:
    """Remove user profile photo.

    :param current_user: Authenticated user
    :param user_service: User service
    :param storage_service: Storage service
    """
    if not current_user.photo_url:
        return

    # Try to delete from storage, but always clear DB record
    if storage_service:
        with suppress(StorageDeleteError):
            storage_service.delete_file(current_user.photo_url)

    user_service.update_photo_url(current_user, None)
