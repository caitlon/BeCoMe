"""Azure Blob Storage service implementation."""

from typing import ClassVar
from uuid import uuid4

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient

from api.config import Settings
from api.services.storage.exceptions import (
    StorageConfigurationError,
    StorageDeleteError,
    StorageUploadError,
)


class AzureBlobStorageService:
    """Azure Blob Storage implementation for file operations.

    Handles profile photo uploads to Azure Blob Storage with
    automatic container management.

    :param settings: Application settings with Azure configuration
    """

    ALLOWED_CONTENT_TYPES = frozenset(
        {
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
        }
    )
    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

    # Map content types to file extensions (trusted, not from user input)
    CONTENT_TYPE_TO_EXTENSION: ClassVar[dict[str, str]] = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
    }

    # Magic bytes for image file type verification
    IMAGE_SIGNATURES: ClassVar[dict[bytes, str]] = {
        b"\xff\xd8\xff": "image/jpeg",  # JPEG
        b"\x89PNG\r\n\x1a\n": "image/png",  # PNG
        b"GIF87a": "image/gif",  # GIF87a
        b"GIF89a": "image/gif",  # GIF89a
        b"RIFF": "image/webp",  # WebP (need to check for WEBP after RIFF)
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
                        return claimed_content_type == "image/webp"
                    continue
                return claimed_content_type == actual_type

        return False

    def __init__(self, settings: Settings) -> None:
        """Initialize Azure Blob Storage client.

        :param settings: Application settings with Azure credentials
        :raises StorageConfigurationError: If Azure settings are missing
        """
        if not settings.azure_storage_connection_string:
            raise StorageConfigurationError("Azure storage connection string not configured")

        self._account_name = settings.azure_storage_account_name
        self._container_name = settings.azure_storage_container_name
        self._client = BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        )
        self._ensure_container_exists()

    def _ensure_container_exists(self) -> None:
        """Create container if it doesn't exist.

        :raises StorageConfigurationError: If container operations fail
        """
        try:
            container_client = self._client.get_container_client(self._container_name)
            if not container_client.exists():
                container_client.create_container(public_access="blob")
        except AzureError as e:
            raise StorageConfigurationError(
                f"Failed to ensure container '{self._container_name}' exists: {e}"
            ) from e

    def _generate_blob_name(self, user_id: str, content_type: str) -> str:
        """Generate unique blob name with user ID prefix.

        Extension is derived from content_type (already validated),
        not from user-provided filename to prevent spoofing.

        :param user_id: User UUID as string
        :param content_type: Validated MIME type
        :return: Sanitized blob name like "profiles/user-id/uuid.ext"
        """
        extension = self.CONTENT_TYPE_TO_EXTENSION.get(content_type, "jpg")
        unique_id = uuid4().hex[:12]
        return f"profiles/{user_id}/{unique_id}.{extension}"

    def _extract_blob_name_from_url(self, file_url: str) -> str | None:
        """Extract blob name from a full Azure Blob URL.

        :param file_url: Full URL like https://account.blob.core.windows.net/container/blob
        :return: Blob name or None if URL doesn't match expected format
        """
        expected_prefix = (
            f"https://{self._account_name}.blob.core.windows.net/{self._container_name}/"
        )
        if file_url.startswith(expected_prefix):
            return file_url[len(expected_prefix) :].split("?")[0]
        return None

    def upload_file(
        self,
        file_content: bytes,
        content_type: str,
        user_id: str,
    ) -> str:
        """Upload a file to Azure Blob Storage.

        :param file_content: Raw file bytes
        :param content_type: MIME type (must be validated before calling)
        :param user_id: User ID for organizing blobs
        :return: Public URL of uploaded blob
        :raises StorageUploadError: If upload fails
        """
        blob_name = self._generate_blob_name(user_id, content_type)
        blob_client = self._client.get_blob_client(
            container=self._container_name,
            blob=blob_name,
        )

        try:
            blob_client.upload_blob(
                file_content,
                content_type=content_type,
                overwrite=True,
            )
            return blob_client.url
        except AzureError as e:
            raise StorageUploadError(f"Failed to upload file: {e}") from e

    def delete_file(self, file_url: str) -> bool:
        """Delete a file from Azure Blob Storage.

        :param file_url: Public URL of the blob
        :return: True if deleted, False if not found
        :raises StorageDeleteError: If deletion fails unexpectedly
        """
        blob_name = self._extract_blob_name_from_url(file_url)
        if not blob_name:
            return False

        blob_client = self._client.get_blob_client(
            container=self._container_name,
            blob=blob_name,
        )

        try:
            blob_client.delete_blob()
            return True
        except ResourceNotFoundError:
            return False
        except AzureError as e:
            raise StorageDeleteError(f"Failed to delete file: {e}") from e
