"""Unit tests for RailwayBucketStorageService."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from api.services.storage.exceptions import (
    StorageConfigurationError,
    StorageDeleteError,
    StorageError,
    StorageUploadError,
)
from api.services.storage.railway_bucket_storage_service import RailwayBucketStorageService


def _settings(**overrides: object) -> MagicMock:
    """Build a settings stub with valid bucket configuration."""
    settings = MagicMock()
    settings.storage_enabled = True
    settings.bucket_name = "test-bucket"
    settings.bucket_endpoint = "https://storage.railway.app"
    settings.bucket_access_key_id = "key"
    settings.bucket_secret_access_key = "secret"
    settings.bucket_region = "auto"
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def _client_error(code: str) -> ClientError:
    """Build a botocore ClientError carrying the given error code."""
    return ClientError({"Error": {"Code": code, "Message": code}}, "GetObject")


class TestInit:
    """Tests for service construction and configuration validation."""

    def test_raises_when_storage_disabled(self):
        """Raises StorageConfigurationError when storage is not enabled."""
        # GIVEN
        settings = _settings(storage_enabled=False)

        # WHEN / THEN
        with pytest.raises(StorageConfigurationError, match="not configured"):
            RailwayBucketStorageService(settings, client=MagicMock())

    def test_raises_when_bucket_name_missing(self):
        """Raises StorageConfigurationError when the bucket name is None."""
        # GIVEN
        settings = _settings(bucket_name=None)

        # WHEN / THEN
        with pytest.raises(StorageConfigurationError, match="not configured"):
            RailwayBucketStorageService(settings, client=MagicMock())

    def test_builds_client_from_settings_when_not_injected(self):
        """Builds a boto3 S3 client from settings when no client is injected."""
        # GIVEN
        settings = _settings()

        # WHEN
        with patch("boto3.client") as mock_boto_client:
            RailwayBucketStorageService(settings)

        # THEN
        mock_boto_client.assert_called_once()
        assert mock_boto_client.call_args.args[0] == "s3"
        assert mock_boto_client.call_args.kwargs["endpoint_url"] == settings.bucket_endpoint


class TestBuildKey:
    """Tests for object key generation."""

    def test_namespaces_by_user_with_jpeg_extension(self):
        """Key is namespaced by user and carries the JPEG extension."""
        # WHEN
        key = RailwayBucketStorageService.build_key("user-123", "image/jpeg")

        # THEN
        assert key.startswith("profiles/user-123/")
        assert key.endswith(".jpg")

    def test_uses_png_extension(self):
        """Key uses the PNG extension for a PNG content type."""
        # WHEN
        key = RailwayBucketStorageService.build_key("user-456", "image/png")

        # THEN
        assert key.endswith(".png")


class TestUpload:
    """Tests for uploading a file."""

    def test_stores_object_and_returns_key(self):
        """Uploads to the bucket and returns the generated key."""
        # GIVEN
        client = MagicMock()
        service = RailwayBucketStorageService(_settings(), client=client)

        # WHEN
        key = service.upload(b"image data", "image/jpeg", "user-123")

        # THEN
        assert key.startswith("profiles/user-123/")
        client.put_object.assert_called_once()
        call = client.put_object.call_args.kwargs
        assert call["Bucket"] == "test-bucket"
        assert call["Key"] == key
        assert call["Body"] == b"image data"
        assert call["ContentType"] == "image/jpeg"

    def test_raises_upload_error_on_failure(self):
        """Wraps a client failure in StorageUploadError."""
        # GIVEN
        client = MagicMock()
        client.put_object.side_effect = Exception("boom")
        service = RailwayBucketStorageService(_settings(), client=client)

        # WHEN / THEN
        with pytest.raises(StorageUploadError, match="Failed to upload"):
            service.upload(b"image data", "image/jpeg", "user-123")


class TestOpen:
    """Tests for fetching an object."""

    def test_returns_bytes_and_content_type(self):
        """Returns the object bytes together with its content type."""
        # GIVEN
        body = MagicMock()
        body.read.return_value = b"image bytes"
        client = MagicMock()
        client.get_object.return_value = {"Body": body, "ContentType": "image/png"}
        service = RailwayBucketStorageService(_settings(), client=client)

        # WHEN
        result = service.open("profiles/user/abc.png")

        # THEN
        assert result == (b"image bytes", "image/png")
        client.get_object.assert_called_once_with(Bucket="test-bucket", Key="profiles/user/abc.png")

    def test_returns_none_when_object_absent(self):
        """Returns None when the object does not exist."""
        # GIVEN
        client = MagicMock()
        client.get_object.side_effect = _client_error("NoSuchKey")
        service = RailwayBucketStorageService(_settings(), client=client)

        # WHEN
        result = service.open("profiles/user/missing.jpg")

        # THEN
        assert result is None

    def test_raises_storage_error_on_other_failure(self):
        """Raises StorageError for failures other than a missing object."""
        # GIVEN
        client = MagicMock()
        client.get_object.side_effect = _client_error("AccessDenied")
        service = RailwayBucketStorageService(_settings(), client=client)

        # WHEN / THEN
        with pytest.raises(StorageError, match="Failed to read"):
            service.open("profiles/user/denied.jpg")


class TestDelete:
    """Tests for deleting an object."""

    def test_deletes_object_and_returns_true(self):
        """Deletes the object and reports success."""
        # GIVEN
        client = MagicMock()
        service = RailwayBucketStorageService(_settings(), client=client)

        # WHEN
        result = service.delete("profiles/user/abc.jpg")

        # THEN
        assert result is True
        client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="profiles/user/abc.jpg"
        )

    def test_raises_delete_error_on_failure(self):
        """Wraps a client failure in StorageDeleteError."""
        # GIVEN
        client = MagicMock()
        client.delete_object.side_effect = Exception("boom")
        service = RailwayBucketStorageService(_settings(), client=client)

        # WHEN / THEN
        with pytest.raises(StorageDeleteError, match="Failed to delete"):
            service.delete("profiles/user/abc.jpg")
