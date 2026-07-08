"""User management routes: profile, password, photo, account deletion."""

from contextlib import suppress
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status

from api.auth.dependencies import CurrentUser
from api.auth.logging import log_account_deletion, log_data_export, log_password_change
from api.auth.revocation_store import RevocationStore, get_revocation_store
from api.db.models import Project
from api.dependencies import (
    get_data_export_service,
    get_project_membership_service,
    get_project_service,
    get_storage_service,
    get_user_service,
)
from api.exceptions import AccountHasOwnedProjectsError, InvalidProjectDispositionError
from api.middleware.rate_limit import (
    LIMIT_PHOTO,
    LIMIT_PWD_RESET,
    LIMIT_STANDARD,
    LIMIT_UPLOAD,
    limiter,
)
from api.schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    UpdateUserRequest,
    UserResponse,
)
from api.schemas.data_export import DataExportResponse
from api.services.data_export_service import DataExportService
from api.services.project_membership_service import ProjectMembershipService
from api.services.project_service import ProjectService
from api.services.storage import validation
from api.services.storage.base import StorageService
from api.services.storage.exceptions import StorageDeleteError, StorageUploadError
from api.services.user_service import UserService
from api.utils.upload import UploadTooLarge, read_within_limit

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", summary="Get current user profile")
def get_current_user_profile(current_user: CurrentUser) -> UserResponse:
    """Return the authenticated user's profile.

    :param current_user: User from JWT token
    :return: User profile data
    """
    return UserResponse.from_user(current_user)


@router.get(
    "/me/export",
    summary="Export current user's personal data (GDPR Article 20)",
)
@limiter.limit(LIMIT_STANDARD)
def export_current_user_data(
    request: Request,
    current_user: CurrentUser,
    service: Annotated[DataExportService, Depends(get_data_export_service)],
) -> DataExportResponse:
    """Return all of the authenticated user's data in machine-readable form.

    Serves the GDPR Article 20 right to data portability: profile, owned
    projects with results, memberships, submitted opinions, and pending
    invitations. Password material is never included.

    :param request: FastAPI request (for rate limiting and audit logging)
    :param current_user: User from JWT token
    :param service: Data export service
    :return: The user's full data export
    """
    export = service.build_export(current_user)
    log_data_export(current_user.id, request)
    return export


@router.put("/me", summary="Update current user profile")
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
    return UserResponse.from_user(updated)


@router.put(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change current user password",
)
@limiter.limit(LIMIT_PWD_RESET)
def change_password(
    request: Request,
    current_user: CurrentUser,
    data: ChangePasswordRequest,
    service: Annotated[UserService, Depends(get_user_service)],
    store: Annotated[RevocationStore, Depends(get_revocation_store)],
) -> None:
    """Change the authenticated user's password.

    InvalidCredentialsError is handled by centralized exception middleware.
    Rate limited to prevent password guessing attacks. Every token issued before
    the change is invalidated (M1).

    :param request: FastAPI request (for rate limiting)
    :param current_user: User from JWT token
    :param data: Current and new password
    :param service: User service
    :param store: Revocation store (invalidates sessions issued before the change)
    """
    service.change_password(
        user=current_user,
        current_password=data.current_password,
        new_password=data.new_password,
    )
    store.set_user_valid_after(current_user.id, datetime.now(UTC))

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
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    membership_service: Annotated[
        ProjectMembershipService, Depends(get_project_membership_service)
    ],
    storage_service: Annotated[StorageService | None, Depends(get_storage_service)],
    data: DeleteAccountRequest | None = None,
) -> None:
    """Delete the authenticated user's account (GDPR Article 17, right to erasure).

    Every project the user still admins must be handled first via ``data``: transfer it
    to another member, or delete it (its opinions and invitations cascade away). This
    keeps erasure from silently destroying other experts' contributions while still
    letting the user leave. The profile photo blob is removed from object storage too.

    :param request: FastAPI request (for logging)
    :param current_user: User from JWT token
    :param service: User service
    :param project_service: Project service (ownership handling)
    :param membership_service: Membership service (validates transfer targets)
    :param storage_service: Storage service (None when not configured)
    :param data: Per-owned-project dispositions (transfer or delete)
    :raises AccountHasOwnedProjectsError: If an owned project has no disposition
    :raises InvalidProjectDispositionError: If a transfer target is not another member
    """
    dispositions = data.project_dispositions if data else []
    owned_by_id = {p.id: p for p in project_service.get_owned_projects(current_user.id)}

    # Each owned project must be handled exactly once; no disposition may name a project
    # the user does not own.
    if {d.project_id for d in dispositions} != set(owned_by_id) or len(dispositions) != len(
        owned_by_id
    ):
        raise AccountHasOwnedProjectsError(
            "Provide a disposition (transfer or delete) for each project you own."
        )

    # Validate everything before mutating anything, so a bad disposition cannot leave the
    # account half-erased.
    transfers: list[tuple[Project, UUID]] = []
    deletes: list[UUID] = []
    for d in dispositions:
        if d.action == "delete":
            deletes.append(d.project_id)
        elif d.new_admin_id is None or d.new_admin_id == current_user.id:
            raise InvalidProjectDispositionError(
                "A transfer must name another member as the new admin."
            )
        elif not membership_service.is_member(d.project_id, d.new_admin_id):
            raise InvalidProjectDispositionError("The new admin must be a member of the project.")
        else:
            transfers.append((owned_by_id[d.project_id], d.new_admin_id))

    for project, new_admin_id in transfers:
        project_service.transfer_ownership(project, new_admin_id)
    for project_id in deletes:
        project_service.delete_project(project_id)

    user_id = current_user.id
    email = current_user.email

    # Remove the profile photo blob so erasure also covers object storage (GDPR Art. 17).
    if current_user.photo_url and storage_service:
        with suppress(StorageDeleteError):
            storage_service.delete(current_user.photo_url)

    service.delete_user(current_user)

    log_account_deletion(user_id, email, request)


@router.post(
    "/me/photo",
    summary="Upload profile photo",
    responses={
        400: {"description": "Invalid file type or file too large"},
        503: {"description": "Storage service unavailable"},
    },
)
@limiter.limit(LIMIT_UPLOAD)
async def upload_photo(
    request: Request,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File(description="Profile photo (JPEG, PNG, GIF, WebP, max 5MB)")],
    user_service: Annotated[UserService, Depends(get_user_service)],
    storage_service: Annotated[StorageService | None, Depends(get_storage_service)],
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
    content_type = file.content_type
    if content_type is None or content_type not in validation.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed: JPEG, PNG, GIF, WebP",
        )

    # Read the upload in bounded chunks so an over-large file never fully buffers.
    try:
        content = await read_within_limit(file, validation.MAX_FILE_SIZE_BYTES)
    except UploadTooLarge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5 MB",
        ) from None

    # Validate actual file content matches claimed type (magic bytes check)
    if not validation.validate_image_content(content, content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match declared type",
        )

    # Delete the previous photo if any (ignore errors so the upload can proceed)
    if current_user.photo_url:
        with suppress(StorageDeleteError):
            storage_service.delete(current_user.photo_url)

    # Upload the new photo and store its object key
    try:
        photo_key = storage_service.upload(content, content_type, str(current_user.id))
    except StorageUploadError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to upload photo",
        ) from err

    updated_user = user_service.update_photo_url(current_user, photo_key)
    return UserResponse.from_user(updated_user)


@router.delete(
    "/me/photo",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete profile photo",
)
def delete_photo(
    current_user: CurrentUser,
    user_service: Annotated[UserService, Depends(get_user_service)],
    storage_service: Annotated[StorageService | None, Depends(get_storage_service)],
) -> None:
    """Remove user profile photo.

    :param current_user: Authenticated user
    :param user_service: User service
    :param storage_service: Storage service
    """
    if not current_user.photo_url:
        return

    # Try to delete from storage, but always clear the DB record
    if storage_service:
        with suppress(StorageDeleteError):
            storage_service.delete(current_user.photo_url)

    user_service.update_photo_url(current_user, None)


@router.get(
    "/{user_id}/photo",
    summary="Get a user's profile photo",
    responses={404: {"description": "No photo for this user"}},
)
@limiter.limit(LIMIT_PHOTO)
def get_user_photo(
    request: Request,
    user_id: UUID,
    user_service: Annotated[UserService, Depends(get_user_service)],
    storage_service: Annotated[StorageService | None, Depends(get_storage_service)],
) -> Response:
    """Stream a user's profile photo from private storage.

    Public endpoint: image tags cannot send auth headers, and avatars are shown
    for every project member. Returns 404 when the user has no photo or storage
    is unavailable.

    :param request: FastAPI request (for rate limiting)
    :param user_id: User whose photo to serve
    :param user_service: User service for the photo key lookup
    :param storage_service: Storage service (None when not configured)
    :return: The image bytes with public caching headers
    """
    if storage_service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    user = user_service.get_by_id(user_id)
    if user is None or not user.photo_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    result = storage_service.open(user.photo_url)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    content, content_type = result
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
