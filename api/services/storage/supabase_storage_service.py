"""Supabase Storage service implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar
from uuid import uuid4

from api.services.storage.exceptions import (
    StorageConfigurationError,
    StorageDeleteError,
    StorageUploadError,
)

if TYPE_CHECKING:
    from api.config import Settings

_MIME_JPEG = "image/jpeg"
_MIME_PNG = "image/png"
_MIME_GIF = "image/gif"
_MIME_WEBP = "image/webp"


class SupabaseStorageService:
    """Supabase Storage implementation for file operations.

    Handles profile photo uploads to Supabase Storage with
    automatic bucket management.

    :param settings: Application settings with Supabase configuration
    """

    # Map content types to file extensions (trusted, not from user input)
    CONTENT_TYPE_TO_EXTENSION: ClassVar[dict[str, str]] = {
        _MIME_JPEG: "jpg",
        _MIME_PNG: "png",
        _MIME_GIF: "gif",
        _MIME_WEBP: "webp",
    }
    ALLOWED_CONTENT_TYPES = frozenset(CONTENT_TYPE_TO_EXTENSION)
    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

    # Magic bytes for image file type verification
    IMAGE_SIGNATURES: ClassVar[dict[bytes, str]] = {
        b"\xff\xd8\xff": _MIME_JPEG,  # JPEG
        b"\x89PNG\r\n\x1a\n": _MIME_PNG,  # PNG
        b"GIF87a": _MIME_GIF,  # GIF87a
        b"GIF89a": _MIME_GIF,  # GIF89a
        b"RIFF": _MIME_WEBP,  # WebP (need to check for WEBP after RIFF)
    }

    @classmethod
    def validate_image_content(cls, content: bytes, claimed_content_type: str) -> bool:
        """Validate that file content matches claimed content type using magic bytes.

        :param content: Raw file bytes
        :param claimed_content_type: Content type claimed by client
        :return: True if content matches claimed type
        """
        if not content:
            return False

        # Check common image signatures
        for signature, actual_type in cls.IMAGE_SIGNATURES.items():
            if content.startswith(signature):
                # Special case for WebP: RIFF header needs WEBP check
                if signature == b"RIFF":
                    if len(content) >= 12 and content[8:12] == b"WEBP":
                        return claimed_content_type == _MIME_WEBP
                    continue
                return claimed_content_type == actual_type

        return False

    def __init__(self, settings: Settings) -> None:
        """Initialize Supabase Storage client.

        :param settings: Application settings with Supabase credentials
        :raises StorageConfigurationError: If Supabase settings are missing
        """
        if not settings.supabase_url or not settings.supabase_key:
            raise StorageConfigurationError("Supabase credentials not configured")

        # Import here to avoid import errors when supabase is not installed
        from supabase import create_client

        self._supabase_url = settings.supabase_url
        self._bucket_name = settings.supabase_storage_bucket
        self._client = create_client(settings.supabase_url, settings.supabase_key)

    def _generate_file_path(self, user_id: str, content_type: str) -> str:
        """Generate unique file path with user ID prefix.

        Extension is derived from content_type (already validated),
        not from user-provided filename to prevent spoofing.

        :param user_id: User UUID as string
        :param content_type: Validated MIME type
        :return: Sanitized file path like "profiles/user-id/uuid.ext"
        """
        extension = self.CONTENT_TYPE_TO_EXTENSION.get(content_type, "jpg")
        unique_id = uuid4().hex[:12]
        return f"profiles/{user_id}/{unique_id}.{extension}"

    def _extract_path_from_url(self, file_url: str) -> str | None:
        """Extract file path from a full Supabase Storage URL.

        :param file_url: Full URL like https://xxx.supabase.co/storage/v1/object/public/bucket/path
        :return: File path or None if URL doesn't match expected format
        """
        marker = f"/storage/v1/object/public/{self._bucket_name}/"
        if marker in file_url:
            return file_url.split(marker)[-1].split("?")[0]
        return None

    def upload_file(
        self,
        file_content: bytes,
        content_type: str,
        user_id: str,
    ) -> str:
        """Upload a file to Supabase Storage.

        :param file_content: Raw file bytes
        :param content_type: MIME type (must be validated before calling)
        :param user_id: User ID for organizing files
        :return: Public URL of uploaded file
        :raises StorageUploadError: If upload fails
        """
        file_path = self._generate_file_path(user_id, content_type)

        try:
            self._client.storage.from_(self._bucket_name).upload(
                path=file_path,
                file=file_content,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            return self._client.storage.from_(self._bucket_name).get_public_url(file_path)
        except Exception as e:
            raise StorageUploadError(f"Failed to upload file: {e}") from e

    def delete_file(self, file_url: str) -> bool:
        """Delete a file from Supabase Storage.

        :param file_url: Public URL of the file
        :return: True if deleted, False if not found
        :raises StorageDeleteError: If deletion fails unexpectedly
        """
        file_path = self._extract_path_from_url(file_url)
        if not file_path:
            return False

        try:
            self._client.storage.from_(self._bucket_name).remove([file_path])
            return True
        except Exception as e:
            # Supabase doesn't distinguish "not found" from other errors clearly,
            # so we treat all deletion attempts as successful if no exception
            raise StorageDeleteError(f"Failed to delete file: {e}") from e
