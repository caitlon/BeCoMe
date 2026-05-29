"""Tests for centralized FastAPI dependencies."""

from unittest.mock import MagicMock, patch

from api.config import Settings
from api.dependencies import get_storage_service
from api.services.storage.exceptions import StorageConfigurationError
from api.services.storage.railway_bucket_storage_service import RailwayBucketStorageService


class TestGetStorageService:
    """Tests for the get_storage_service factory function."""

    def test_returns_none_when_storage_disabled(self):
        """
        GIVEN bucket storage is not configured
        WHEN get_storage_service is called
        THEN it returns None
        """
        # GIVEN
        mock_settings = MagicMock(spec=Settings)
        mock_settings.storage_enabled = False

        # WHEN
        with patch("api.dependencies.get_settings", return_value=mock_settings):
            result = get_storage_service()

        # THEN
        assert result is None

    def test_returns_service_when_configured(self):
        """
        GIVEN bucket storage is properly configured
        WHEN get_storage_service is called
        THEN it returns a RailwayBucketStorageService instance
        """
        # GIVEN
        mock_settings = MagicMock(spec=Settings)
        mock_settings.storage_enabled = True
        mock_service = MagicMock(spec=RailwayBucketStorageService)

        # WHEN
        with (
            patch("api.dependencies.get_settings", return_value=mock_settings),
            patch(
                "api.dependencies.RailwayBucketStorageService", return_value=mock_service
            ) as mock_class,
        ):
            result = get_storage_service()

        # THEN
        assert result is mock_service
        mock_class.assert_called_once_with(mock_settings)

    def test_returns_none_on_configuration_error(self):
        """
        GIVEN bucket storage is enabled but initialization fails
        WHEN get_storage_service is called
        THEN it returns None (graceful degradation)
        """
        # GIVEN
        mock_settings = MagicMock(spec=Settings)
        mock_settings.storage_enabled = True

        # WHEN
        with (
            patch("api.dependencies.get_settings", return_value=mock_settings),
            patch(
                "api.dependencies.RailwayBucketStorageService",
                side_effect=StorageConfigurationError("Invalid config"),
            ),
        ):
            result = get_storage_service()

        # THEN
        assert result is None
