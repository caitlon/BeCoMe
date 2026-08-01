"""User management routes: profile, password, photo, account deletion."""

import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status

from api.auth.dependencies import CurrentUser, CurrentUserFresh
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
from api.services.storage.exceptions import (
    StorageDeleteError,
    StorageError,
    StorageUploadError,
)
from api.services.user_service import UserService
from api.utils.photo_links import photo_version
from api.utils.streaming import StoredObjectResponse
from api.utils.upload import UploadTooLarge, read_within_limit

# Password change, account deletion, and the GDPR export are logged by
# api/auth/logging.py; the storage layer logs its own s3_* events and the dimension
# rejection. What is left for this router is the profile write and the photo refusals,
# which are raised as HTTPException and so never reach the app's exception handlers.
logger = logging.getLogger("api.route.users")

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _photo_upload_rejected(reason: str, user_id: UUID, **fields: object) -> None:
    """Record a refused photo upload.

    :param reason: Which check refused it, e.g. ``content_type``.
    :param user_id: Uploader.
    :param fields: Extra context, never the file's bytes.
    """
    logger.warning(
        "Photo upload rejected",
        extra={
            "event": "photo_upload_rejected",
            "reason": reason,
            "user_id": str(user_id),
            **fields,
        },
    )


def _photo_not_found(reason: str, user_id: UUID) -> None:
    """Record a 404 from the public photo proxy.

    DEBUG rather than WARNING: the endpoint is public and fires on every avatar render,
    so a missing photo is ordinary traffic rather than a signal.

    :param reason: Which branch answered 404.
    :param user_id: User whose photo was requested.
    """
    logger.debug(
        "Photo not found",
        extra={"event": "photo_not_found", "reason": reason, "user_id": str(user_id)},
    )


# Profile photo URLs are versioned: build_photo_url appends ?v=<token> taken from the
# stored object key, and every upload mints a fresh key. A versioned URL therefore always
# resolves to the same bytes and can be cached for as long as a cache will hold it.
_VERSIONED_PHOTO_CACHE_CONTROL = "public, max-age=31536000, immutable"

# The bare path carries no version, so its bytes change when the photo does. Nothing the
# API emits looks like that, but a hand-written or truncated URL would, and pinning it for
# a year in a shared cache would serve one person's old avatar to everyone who asked.
_UNVERSIONED_PHOTO_CACHE_CONTROL = "public, max-age=300"


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
    current_user: CurrentUserFresh,
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
    current_user: CurrentUserFresh,
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
    # Field names only. The values are the user's own name, which the record does not
    # need in order to say that the profile changed.
    logger.info(
        "Profile updated",
        extra={
            "event": "profile_updated",
            "user_id": str(current_user.id),
            "fields": [
                name
                for name, value in (
                    ("first_name", request.first_name),
                    ("last_name", request.last_name),
                )
                if value is not None
            ],
        },
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
    current_user: CurrentUserFresh,
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
    # Order matters: verify, then close the session window, then write. Revoking before
    # the write means a store fault surfaces as a 503 with the password unchanged, rather
    # than committing the new password while old sessions stay valid. Verifying first
    # keeps a mistyped current password from logging the user out everywhere.
    service.verify_current_password(current_user, data.current_password)
    store.set_user_valid_after(current_user.id, datetime.now(UTC))
    service.set_password(current_user, data.new_password)

    log_password_change(current_user.id, request)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete current user account",
)
def delete_current_user(
    request: Request,
    current_user: CurrentUserFresh,
    service: Annotated[UserService, Depends(get_user_service)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    membership_service: Annotated[
        ProjectMembershipService, Depends(get_project_membership_service)
    ],
    storage_service: Annotated[StorageService | None, Depends(get_storage_service)],
    store: Annotated[RevocationStore, Depends(get_revocation_store)],
    data: DeleteAccountRequest | None = None,
) -> None:
    """Delete the authenticated user's account (GDPR Article 17, right to erasure).

    Every project the user still admins must be handled first via ``data``: transfer it
    to another member, or delete it (its opinions and invitations cascade away). This
    keeps erasure from silently destroying other experts' contributions while still
    letting the user leave. The profile photo blob is removed from object storage too.
    Every token issued for this account is invalidated (M2), so a still-warm cache
    entry cannot serve the deleted account past this request.

    :param request: FastAPI request (for logging)
    :param current_user: User from JWT token
    :param service: User service
    :param project_service: Project service (ownership handling)
    :param membership_service: Membership service (validates transfer targets)
    :param storage_service: Storage service (None when not configured)
    :param store: Revocation store (invalidates tokens issued before the deletion)
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

    # M2: revoke the deleted user's tokens so the account cannot outlive its data
    # via a still-warm cache entry (decode rejects the token before the cache).
    store.set_user_valid_after(user_id, datetime.now(UTC))

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
    current_user: CurrentUserFresh,
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
        _photo_upload_rejected("storage_unavailable", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo upload is not available",
        )

    # Validate content type
    content_type = file.content_type
    if content_type is None or content_type not in validation.ALLOWED_CONTENT_TYPES:
        _photo_upload_rejected("content_type", current_user.id, content_type=content_type)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed: JPEG, PNG, GIF, WebP",
        )

    # Read the upload in bounded chunks so an over-large file never fully buffers.
    try:
        content = await read_within_limit(file, validation.MAX_FILE_SIZE_BYTES)
    except UploadTooLarge:
        _photo_upload_rejected(
            "too_large", current_user.id, limit_bytes=validation.MAX_FILE_SIZE_BYTES
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5 MB",
        ) from None

    # Validate actual file content matches claimed type (magic bytes check)
    if not validation.validate_image_content(content, content_type):
        _photo_upload_rejected("content_mismatch", current_user.id, content_type=content_type)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match declared type",
        )

    # The byte cap above says nothing about the pixel canvas: a small, highly
    # compressible file can declare a gigapixel image whose decode would exhaust memory.
    if not validation.validate_image_dimensions(content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image dimensions are too large. Maximum is 4096x4096 pixels",
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
    logger.info(
        "Profile photo uploaded",
        extra={
            "event": "photo_uploaded",
            "user_id": str(current_user.id),
            "size_bytes": len(content),
            "content_type": content_type,
        },
    )
    return UserResponse.from_user(updated_user)


@router.delete(
    "/me/photo",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete profile photo",
)
def delete_photo(
    current_user: CurrentUserFresh,
    user_service: Annotated[UserService, Depends(get_user_service)],
    storage_service: Annotated[StorageService | None, Depends(get_storage_service)],
) -> None:
    """Remove user profile photo.

    :param current_user: Authenticated user
    :param user_service: User service
    :param storage_service: Storage service
    """
    if not current_user.photo_url:
        # A 204 either way, so without this the no-op looks like a deletion.
        logger.debug(
            "Photo delete was a no-op",
            extra={"event": "photo_delete_noop", "user_id": str(current_user.id)},
        )
        return

    # Try to delete from storage, but always clear the DB record
    if storage_service:
        with suppress(StorageDeleteError):
            storage_service.delete(current_user.photo_url)

    user_service.update_photo_url(current_user, None)
    logger.info(
        "Profile photo deleted",
        extra={"event": "photo_deleted", "user_id": str(current_user.id)},
    )


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
    :return: The image streamed from the bucket, with public caching headers
    """
    if storage_service is None:
        _photo_not_found("no_storage", user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    user = user_service.get_by_id(user_id)
    if user is None or not user.photo_url:
        _photo_not_found("no_user_or_key", user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    # A storage fault must not surface here: this endpoint is public, and the raw
    # exception text carries the bucket host and object key.
    try:
        stored = storage_service.open(user.photo_url)
    except StorageError as err:
        # The bucket layer already logged the fault with its own s3_open_failed event;
        # this only records that the caller was answered 404 because of it.
        _photo_not_found("storage_error", user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found"
        ) from err

    if stored is None:
        _photo_not_found("object_missing", user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    # The version has to match the key being served, not merely be present. This route
    # always serves whatever photo the account holds now, so a stale or invented `v`
    # names bytes that already changed once and can change again -- pinning it for a
    # year would leave a shared cache handing out a replaced avatar under that URL.
    cache_control = (
        _VERSIONED_PHOTO_CACHE_CONTROL
        if request.query_params.get("v") == photo_version(user.photo_url)
        else _UNVERSIONED_PHOTO_CACHE_CONTROL
    )
    return StoredObjectResponse(stored, headers={"Cache-Control": cache_control})
