"""Unit tests for SupabaseStorageService."""

from unittest.mock import MagicMock, patch

import pytest

from api.services.storage.supabase_storage_service import SupabaseStorageService
from api.services.storage.exceptions import (
    StorageConfigurationError,
    StorageDeleteError,
    StorageUploadError,
)


class TestSupabaseStorageServiceInit:
    """Tests for SupabaseStorageService initialization."""

    def test_raises_error_when_url_missing(self):
        """Raises StorageConfigurationError when supabase_url is None."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.supabase_url = None
        mock_settings.supabase_key = "test-key"

        # WHEN / THEN
        with pytest.raises(StorageConfigurationError, match="not configured"):
            SupabaseStorageService(mock_settings)

    def test_raises_error_when_key_missing(self):
        """Raises StorageConfigurationError when supabase_key is None."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key = None

        # WHEN / THEN
        with pytest.raises(StorageConfigurationError, match="not configured"):
            SupabaseStorageService(mock_settings)

    @patch("supabase.create_client")
    def test_creates_bucket_if_not_exists(self, mock_create_client):
        """Bucket is created if it doesn't exist."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_settings.supabase_storage_bucket = "test-bucket"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Return empty bucket list
        mock_bucket = MagicMock()
        mock_bucket.name = "other-bucket"
        mock_client.storage.list_buckets.return_value = [mock_bucket]

        # WHEN
        SupabaseStorageService(mock_settings)

        # THEN
        mock_client.storage.create_bucket.assert_called_once_with(
            "test-bucket",
            options={"public": True},
        )

    @patch("supabase.create_client")
    def test_skips_bucket_creation_if_exists(self, mock_create_client):
        """Bucket creation is skipped if it already exists."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_settings.supabase_storage_bucket = "test-bucket"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Return bucket list with our bucket
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_client.storage.list_buckets.return_value = [mock_bucket]

        # WHEN
        SupabaseStorageService(mock_settings)

        # THEN
        mock_client.storage.create_bucket.assert_not_called()

    @patch("supabase.create_client")
    def test_wraps_exception_during_init(self, mock_create_client):
        """Exception during bucket check is wrapped in StorageConfigurationError."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_settings.supabase_storage_bucket = "test-bucket"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_client.storage.list_buckets.side_effect = Exception("Network error")

        # WHEN / THEN
        with pytest.raises(StorageConfigurationError, match="Failed to ensure bucket"):
            SupabaseStorageService(mock_settings)


class TestGenerateFilePath:
    """Tests for file path generation."""

    @patch("supabase.create_client")
    def test_generates_unique_path_with_jpeg_extension(self, mock_create_client):
        """File path includes user ID and .jpg extension for JPEG."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_settings.supabase_storage_bucket = "test-bucket"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_client.storage.list_buckets.return_value = [mock_bucket]

        service = SupabaseStorageService(mock_settings)

        # WHEN
        file_path = service._generate_file_path("user-123", "image/jpeg")

        # THEN
        assert file_path.startswith("profiles/user-123/")
        assert file_path.endswith(".jpg")

    @patch("supabase.create_client")
    def test_generates_png_extension(self, mock_create_client):
        """File path uses .png extension for PNG content type."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_settings.supabase_storage_bucket = "test-bucket"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_client.storage.list_buckets.return_value = [mock_bucket]

        service = SupabaseStorageService(mock_settings)

        # WHEN
        file_path = service._generate_file_path("user-456", "image/png")

        # THEN
        assert file_path.endswith(".png")


class TestUploadFile:
    """Tests for file upload."""

    @patch("supabase.create_client")
    def test_uploads_file_successfully(self, mock_create_client):
        """File is uploaded and URL returned."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_settings.supabase_storage_bucket = "test-bucket"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_client.storage.list_buckets.return_value = [mock_bucket]

        mock_storage_bucket = MagicMock()
        mock_client.storage.from_.return_value = mock_storage_bucket
        mock_storage_bucket.get_public_url.return_value = (
            "https://test.supabase.co/storage/v1/object/public/test-bucket/test.jpg"
        )

        service = SupabaseStorageService(mock_settings)

        # WHEN
        url = service.upload_file(b"image data", "image/jpeg", "user-123")

        # THEN
        assert "supabase.co" in url
        mock_storage_bucket.upload.assert_called_once()

    @patch("supabase.create_client")
    def test_raises_error_on_upload_failure(self, mock_create_client):
        """StorageUploadError is raised when upload fails."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_settings.supabase_storage_bucket = "test-bucket"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_client.storage.list_buckets.return_value = [mock_bucket]

        mock_storage_bucket = MagicMock()
        mock_client.storage.from_.return_value = mock_storage_bucket
        mock_storage_bucket.upload.side_effect = Exception("Upload failed")

        service = SupabaseStorageService(mock_settings)

        # WHEN / THEN
        with pytest.raises(StorageUploadError, match="Failed to upload"):
            service.upload_file(b"image data", "image/jpeg", "user-123")


class TestDeleteFile:
    """Tests for file deletion."""

    @patch("supabase.create_client")
    def test_deletes_file_successfully(self, mock_create_client):
        """File is deleted and True returned."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_settings.supabase_storage_bucket = "test-bucket"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_client.storage.list_buckets.return_value = [mock_bucket]

        mock_storage_bucket = MagicMock()
        mock_client.storage.from_.return_value = mock_storage_bucket

        service = SupabaseStorageService(mock_settings)

        # WHEN
        result = service.delete_file(
            "https://test.supabase.co/storage/v1/object/public/test-bucket/profiles/user/photo.jpg"
        )

        # THEN
        assert result is True
        mock_storage_bucket.remove.assert_called_once_with(["profiles/user/photo.jpg"])

    @patch("supabase.create_client")
    def test_returns_false_for_invalid_url(self, mock_create_client):
        """Returns False when URL doesn't match expected format."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_settings.supabase_storage_bucket = "test-bucket"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_client.storage.list_buckets.return_value = [mock_bucket]

        service = SupabaseStorageService(mock_settings)

        # WHEN
        result = service.delete_file("https://other-service.com/photo.jpg")

        # THEN
        assert result is False

    @patch("supabase.create_client")
    def test_raises_error_on_delete_failure(self, mock_create_client):
        """StorageDeleteError is raised when deletion fails unexpectedly."""
        # GIVEN
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_settings.supabase_storage_bucket = "test-bucket"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_client.storage.list_buckets.return_value = [mock_bucket]

        mock_storage_bucket = MagicMock()
        mock_client.storage.from_.return_value = mock_storage_bucket
        mock_storage_bucket.remove.side_effect = Exception("Delete failed")

        service = SupabaseStorageService(mock_settings)

        # WHEN / THEN
        with pytest.raises(StorageDeleteError, match="Failed to delete"):
            service.delete_file(
                "https://test.supabase.co/storage/v1/object/public/test-bucket/profiles/user/photo.jpg"
            )


class TestValidateImageContent:
    """Tests for magic bytes validation."""

    def test_valid_jpeg(self):
        """Valid JPEG content passes validation."""
        content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 100
        assert SupabaseStorageService.validate_image_content(content, "image/jpeg")

    def test_valid_png(self):
        """Valid PNG content passes validation."""
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert SupabaseStorageService.validate_image_content(content, "image/png")

    def test_valid_gif87a(self):
        """Valid GIF87a content passes validation."""
        content = b"GIF87a" + b"\x00" * 100
        assert SupabaseStorageService.validate_image_content(content, "image/gif")

    def test_valid_gif89a(self):
        """Valid GIF89a content passes validation."""
        content = b"GIF89a" + b"\x00" * 100
        assert SupabaseStorageService.validate_image_content(content, "image/gif")

    def test_valid_webp(self):
        """Valid WebP content passes validation."""
        content = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
        assert SupabaseStorageService.validate_image_content(content, "image/webp")

    def test_invalid_content(self):
        """Non-image content fails validation."""
        content = b"This is just text"
        assert not SupabaseStorageService.validate_image_content(content, "image/jpeg")

    def test_mismatched_type(self):
        """JPEG content with PNG claimed type fails."""
        jpeg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 100
        assert not SupabaseStorageService.validate_image_content(jpeg_content, "image/png")

    def test_empty_content(self):
        """Empty content fails validation."""
        assert not SupabaseStorageService.validate_image_content(b"", "image/jpeg")

    def test_riff_without_webp(self):
        """RIFF file that's not WebP fails validation."""
        content = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 100  # WAV file
        assert not SupabaseStorageService.validate_image_content(content, "image/webp")
