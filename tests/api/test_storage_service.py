"""Unit tests for AzureBlobStorageService."""

from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import AzureError, ResourceNotFoundError

from api.services.storage.azure_blob_service import AzureBlobStorageService
from api.services.storage.exceptions import (
    StorageConfigurationError,
    StorageDeleteError,
    StorageUploadError,
)


class TestAzureBlobStorageServiceInit:
    """Tests for AzureBlobStorageService initialization."""

    def test_raises_error_when_connection_string_missing(self):
        """Raises StorageConfigurationError when connection string is None."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.azure_storage_connection_string = None

        # WHEN / THEN
        with pytest.raises(StorageConfigurationError, match="not configured"):
            AzureBlobStorageService(mock_settings)

    @patch("api.services.storage.azure_blob_service.BlobServiceClient")
    def test_creates_container_if_not_exists(self, mock_blob_client_class):
        """Container is created if it doesn't exist."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.azure_storage_connection_string = "DefaultEndpointsProtocol=https;..."
        mock_settings.azure_storage_account_name = "testaccount"
        mock_settings.azure_storage_container_name = "test-container"

        mock_client = MagicMock()
        mock_blob_client_class.from_connection_string.return_value = mock_client
        mock_container = MagicMock()
        mock_container.exists.return_value = False
        mock_client.get_container_client.return_value = mock_container

        # WHEN
        AzureBlobStorageService(mock_settings)

        # THEN
        mock_container.create_container.assert_called_once_with(public_access="blob")

    @patch("api.services.storage.azure_blob_service.BlobServiceClient")
    def test_skips_container_creation_if_exists(self, mock_blob_client_class):
        """Container creation is skipped if it already exists."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.azure_storage_connection_string = "DefaultEndpointsProtocol=https;..."
        mock_settings.azure_storage_account_name = "testaccount"
        mock_settings.azure_storage_container_name = "test-container"

        mock_client = MagicMock()
        mock_blob_client_class.from_connection_string.return_value = mock_client
        mock_container = MagicMock()
        mock_container.exists.return_value = True
        mock_client.get_container_client.return_value = mock_container

        # WHEN
        AzureBlobStorageService(mock_settings)

        # THEN
        mock_container.create_container.assert_not_called()

    @patch("api.services.storage.azure_blob_service.BlobServiceClient")
    def test_wraps_azure_error_during_init(self, mock_blob_client_class):
        """AzureError during container check is wrapped in StorageConfigurationError."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.azure_storage_connection_string = "DefaultEndpointsProtocol=https;..."
        mock_settings.azure_storage_account_name = "testaccount"
        mock_settings.azure_storage_container_name = "test-container"

        mock_client = MagicMock()
        mock_blob_client_class.from_connection_string.return_value = mock_client
        mock_container = MagicMock()
        mock_container.exists.side_effect = AzureError("Network error")
        mock_client.get_container_client.return_value = mock_container

        # WHEN / THEN
        with pytest.raises(StorageConfigurationError, match="Failed to ensure container"):
            AzureBlobStorageService(mock_settings)


class TestGenerateBlobName:
    """Tests for blob name generation."""

    @patch("api.services.storage.azure_blob_service.BlobServiceClient")
    def test_generates_unique_name_with_jpeg_extension(self, mock_blob_client_class):
        """Blob name includes user ID and .jpg extension for JPEG."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.azure_storage_connection_string = "conn"
        mock_settings.azure_storage_account_name = "acc"
        mock_settings.azure_storage_container_name = "container"

        mock_client = MagicMock()
        mock_blob_client_class.from_connection_string.return_value = mock_client
        mock_container = MagicMock()
        mock_container.exists.return_value = True
        mock_client.get_container_client.return_value = mock_container

        service = AzureBlobStorageService(mock_settings)

        # WHEN
        blob_name = service._generate_blob_name("user-123", "image/jpeg")

        # THEN
        assert blob_name.startswith("profiles/user-123/")
        assert blob_name.endswith(".jpg")

    @patch("api.services.storage.azure_blob_service.BlobServiceClient")
    def test_generates_png_extension(self, mock_blob_client_class):
        """Blob name uses .png extension for PNG content type."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.azure_storage_connection_string = "conn"
        mock_settings.azure_storage_account_name = "acc"
        mock_settings.azure_storage_container_name = "container"

        mock_client = MagicMock()
        mock_blob_client_class.from_connection_string.return_value = mock_client
        mock_container = MagicMock()
        mock_container.exists.return_value = True
        mock_client.get_container_client.return_value = mock_container

        service = AzureBlobStorageService(mock_settings)

        # WHEN
        blob_name = service._generate_blob_name("user-456", "image/png")

        # THEN
        assert blob_name.endswith(".png")


class TestUploadFile:
    """Tests for file upload."""

    @patch("api.services.storage.azure_blob_service.BlobServiceClient")
    def test_uploads_file_successfully(self, mock_blob_client_class):
        """File is uploaded and URL returned."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.azure_storage_connection_string = "conn"
        mock_settings.azure_storage_account_name = "testaccount"
        mock_settings.azure_storage_container_name = "container"

        mock_client = MagicMock()
        mock_blob_client_class.from_connection_string.return_value = mock_client
        mock_container = MagicMock()
        mock_container.exists.return_value = True
        mock_client.get_container_client.return_value = mock_container

        mock_blob = MagicMock()
        mock_blob.url = "https://testaccount.blob.core.windows.net/container/test.jpg"
        mock_client.get_blob_client.return_value = mock_blob

        service = AzureBlobStorageService(mock_settings)

        # WHEN
        url = service.upload_file(b"image data", "image/jpeg", "user-123")

        # THEN
        assert url == "https://testaccount.blob.core.windows.net/container/test.jpg"
        mock_blob.upload_blob.assert_called_once()

    @patch("api.services.storage.azure_blob_service.BlobServiceClient")
    def test_raises_error_on_upload_failure(self, mock_blob_client_class):
        """StorageUploadError is raised when upload fails."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.azure_storage_connection_string = "conn"
        mock_settings.azure_storage_account_name = "testaccount"
        mock_settings.azure_storage_container_name = "container"

        mock_client = MagicMock()
        mock_blob_client_class.from_connection_string.return_value = mock_client
        mock_container = MagicMock()
        mock_container.exists.return_value = True
        mock_client.get_container_client.return_value = mock_container

        mock_blob = MagicMock()
        mock_blob.upload_blob.side_effect = AzureError("Upload failed")
        mock_client.get_blob_client.return_value = mock_blob

        service = AzureBlobStorageService(mock_settings)

        # WHEN / THEN
        with pytest.raises(StorageUploadError, match="Failed to upload"):
            service.upload_file(b"image data", "image/jpeg", "user-123")


class TestDeleteFile:
    """Tests for file deletion."""

    @patch("api.services.storage.azure_blob_service.BlobServiceClient")
    def test_deletes_file_successfully(self, mock_blob_client_class):
        """File is deleted and True returned."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.azure_storage_connection_string = "conn"
        mock_settings.azure_storage_account_name = "testaccount"
        mock_settings.azure_storage_container_name = "container"

        mock_client = MagicMock()
        mock_blob_client_class.from_connection_string.return_value = mock_client
        mock_container = MagicMock()
        mock_container.exists.return_value = True
        mock_client.get_container_client.return_value = mock_container

        mock_blob = MagicMock()
        mock_client.get_blob_client.return_value = mock_blob

        service = AzureBlobStorageService(mock_settings)

        # WHEN
        result = service.delete_file(
            "https://testaccount.blob.core.windows.net/container/profiles/user/photo.jpg"
        )

        # THEN
        assert result is True
        mock_blob.delete_blob.assert_called_once()

    @patch("api.services.storage.azure_blob_service.BlobServiceClient")
    def test_returns_false_for_invalid_url(self, mock_blob_client_class):
        """Returns False when URL doesn't match expected format."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.azure_storage_connection_string = "conn"
        mock_settings.azure_storage_account_name = "testaccount"
        mock_settings.azure_storage_container_name = "container"

        mock_client = MagicMock()
        mock_blob_client_class.from_connection_string.return_value = mock_client
        mock_container = MagicMock()
        mock_container.exists.return_value = True
        mock_client.get_container_client.return_value = mock_container

        service = AzureBlobStorageService(mock_settings)

        # WHEN
        result = service.delete_file("https://other-account.blob.core.windows.net/photo.jpg")

        # THEN
        assert result is False

    @patch("api.services.storage.azure_blob_service.BlobServiceClient")
    def test_returns_false_when_not_found(self, mock_blob_client_class):
        """Returns False when blob doesn't exist."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.azure_storage_connection_string = "conn"
        mock_settings.azure_storage_account_name = "testaccount"
        mock_settings.azure_storage_container_name = "container"

        mock_client = MagicMock()
        mock_blob_client_class.from_connection_string.return_value = mock_client
        mock_container = MagicMock()
        mock_container.exists.return_value = True
        mock_client.get_container_client.return_value = mock_container

        mock_blob = MagicMock()
        mock_blob.delete_blob.side_effect = ResourceNotFoundError("Not found")
        mock_client.get_blob_client.return_value = mock_blob

        service = AzureBlobStorageService(mock_settings)

        # WHEN
        result = service.delete_file(
            "https://testaccount.blob.core.windows.net/container/profiles/user/photo.jpg"
        )

        # THEN
        assert result is False

    @patch("api.services.storage.azure_blob_service.BlobServiceClient")
    def test_raises_error_on_delete_failure(self, mock_blob_client_class):
        """StorageDeleteError is raised when deletion fails unexpectedly."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.azure_storage_connection_string = "conn"
        mock_settings.azure_storage_account_name = "testaccount"
        mock_settings.azure_storage_container_name = "container"

        mock_client = MagicMock()
        mock_blob_client_class.from_connection_string.return_value = mock_client
        mock_container = MagicMock()
        mock_container.exists.return_value = True
        mock_client.get_container_client.return_value = mock_container

        mock_blob = MagicMock()
        mock_blob.delete_blob.side_effect = AzureError("Delete failed")
        mock_client.get_blob_client.return_value = mock_blob

        service = AzureBlobStorageService(mock_settings)

        # WHEN / THEN
        with pytest.raises(StorageDeleteError, match="Failed to delete"):
            service.delete_file(
                "https://testaccount.blob.core.windows.net/container/profiles/user/photo.jpg"
            )


class TestValidateImageContent:
    """Tests for magic bytes validation."""

    def test_valid_jpeg(self):
        """Valid JPEG content passes validation."""
        content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 100
        assert AzureBlobStorageService.validate_image_content(content, "image/jpeg")

    def test_valid_png(self):
        """Valid PNG content passes validation."""
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert AzureBlobStorageService.validate_image_content(content, "image/png")

    def test_valid_gif87a(self):
        """Valid GIF87a content passes validation."""
        content = b"GIF87a" + b"\x00" * 100
        assert AzureBlobStorageService.validate_image_content(content, "image/gif")

    def test_valid_gif89a(self):
        """Valid GIF89a content passes validation."""
        content = b"GIF89a" + b"\x00" * 100
        assert AzureBlobStorageService.validate_image_content(content, "image/gif")

    def test_valid_webp(self):
        """Valid WebP content passes validation."""
        content = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
        assert AzureBlobStorageService.validate_image_content(content, "image/webp")

    def test_invalid_content(self):
        """Non-image content fails validation."""
        content = b"This is just text"
        assert not AzureBlobStorageService.validate_image_content(content, "image/jpeg")

    def test_mismatched_type(self):
        """JPEG content with PNG claimed type fails."""
        jpeg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 100
        assert not AzureBlobStorageService.validate_image_content(jpeg_content, "image/png")

    def test_empty_content(self):
        """Empty content fails validation."""
        assert not AzureBlobStorageService.validate_image_content(b"", "image/jpeg")

    def test_riff_without_webp(self):
        """RIFF file that's not WebP fails validation."""
        content = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 100  # WAV file
        assert not AzureBlobStorageService.validate_image_content(content, "image/webp")
