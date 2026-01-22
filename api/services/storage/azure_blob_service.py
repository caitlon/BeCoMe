"""Azure Blob Storage service implementation."""

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
        """Create container if it doesn't exist."""
        container_client = self._client.get_container_client(self._container_name)
        if not container_client.exists():
            container_client.create_container(public_access="blob")

    def _generate_blob_name(self, user_id: str, original_filename: str) -> str:
        """Generate unique blob name with user ID prefix.

        :param user_id: User UUID as string
        :param original_filename: Original uploaded filename
        :return: Sanitized blob name like "profiles/user-id/uuid.ext"
        """
        extension = (
            original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "jpg"
        )
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
        file_name: str,
        content_type: str,
        user_id: str,
    ) -> str:
        """Upload a file to Azure Blob Storage.

        :param file_content: Raw file bytes
        :param file_name: Original filename
        :param content_type: MIME type
        :param user_id: User ID for organizing blobs
        :return: Public URL of uploaded blob
        :raises StorageUploadError: If upload fails
        """
        blob_name = self._generate_blob_name(user_id, file_name)
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
