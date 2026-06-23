"""Tests for centralized FastAPI dependencies."""

from unittest.mock import MagicMock, patch

from api.config import Settings
from api.dependencies import (
    get_email_service,
    get_password_reset_service,
    get_storage_service,
)
from api.services.email.console_email_sender import ConsoleEmailSender
from api.services.email.resend_email_sender import ResendEmailSender
from api.services.password_reset_service import PasswordResetService
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


class TestGetEmailService:
    """Tests for the get_email_service factory function."""

    def test_returns_console_sender_for_console_provider(self):
        """
        GIVEN the console email provider
        WHEN get_email_service is called
        THEN it returns a ConsoleEmailSender
        """
        # GIVEN
        mock_settings = MagicMock(spec=Settings)
        mock_settings.email_provider = "console"
        mock_settings.email_enabled = False

        # WHEN
        with patch("api.dependencies.get_settings", return_value=mock_settings):
            result = get_email_service()

        # THEN
        assert isinstance(result, ConsoleEmailSender)

    def test_returns_resend_sender_for_configured_http_provider(self):
        """
        GIVEN the http email provider with credentials set
        WHEN get_email_service is called
        THEN it returns a ResendEmailSender
        """
        # GIVEN
        mock_settings = MagicMock(spec=Settings)
        mock_settings.email_provider = "http"
        mock_settings.email_enabled = True

        # WHEN
        with patch("api.dependencies.get_settings", return_value=mock_settings):
            result = get_email_service()

        # THEN
        assert isinstance(result, ResendEmailSender)

    def test_falls_back_to_console_when_http_unconfigured(self):
        """
        GIVEN the http provider selected but no credentials
        WHEN get_email_service is called
        THEN it falls back to a ConsoleEmailSender (no crash, preserves anti-enumeration)
        """
        # GIVEN
        mock_settings = MagicMock(spec=Settings)
        mock_settings.email_provider = "http"
        mock_settings.email_enabled = False

        # WHEN
        with patch("api.dependencies.get_settings", return_value=mock_settings):
            result = get_email_service()

        # THEN
        assert isinstance(result, ConsoleEmailSender)


class TestGetPasswordResetService:
    """Tests for the get_password_reset_service factory function."""

    def test_returns_service_bound_to_session(self):
        """
        GIVEN a database session
        WHEN get_password_reset_service is called
        THEN it returns a PasswordResetService bound to that session
        """
        # GIVEN
        mock_session = MagicMock()

        # WHEN
        result = get_password_reset_service(mock_session)

        # THEN
        assert isinstance(result, PasswordResetService)
        assert result.session is mock_session
