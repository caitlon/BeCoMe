"""Tests for centralized FastAPI dependencies."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.config import Settings
from api.dependencies import (
    AccessLevel,
    RequireProjectAccess,
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


class TestRequireProjectAccess:
    """Tests for the parameterized project access dependency."""

    def test_returns_project_when_access_granted(self):
        """Returns the project when the user has the required access level."""
        # GIVEN
        project = MagicMock()
        project_service = MagicMock()
        project_service.get_project.return_value = project
        membership_service = MagicMock()
        membership_service.is_admin.return_value = True
        current_user = MagicMock()
        current_user.id = uuid4()
        dependency = RequireProjectAccess(AccessLevel.ADMIN)

        # WHEN
        result = dependency(uuid4(), current_user, project_service, membership_service)

        # THEN
        assert result is project

    def test_raises_404_when_project_missing(self):
        """Raises 404 when the project does not exist."""
        # GIVEN
        project_service = MagicMock()
        project_service.get_project.return_value = None
        current_user = MagicMock()
        current_user.id = uuid4()
        dependency = RequireProjectAccess(AccessLevel.MEMBER)

        # WHEN / THEN
        with pytest.raises(HTTPException) as exc_info:
            dependency(uuid4(), current_user, project_service, MagicMock())

        assert exc_info.value.status_code == 404

    def test_logs_and_raises_403_when_access_denied(self):
        """Logs an access_denied warning and raises 403 when access is insufficient."""
        # GIVEN
        project_id = uuid4()
        user_id = uuid4()
        project_service = MagicMock()
        project_service.get_project.return_value = MagicMock()
        membership_service = MagicMock()
        membership_service.is_admin.return_value = False
        current_user = MagicMock()
        current_user.id = user_id
        dependency = RequireProjectAccess(AccessLevel.ADMIN)

        # WHEN
        with (
            patch("api.dependencies.logger") as mock_logger,
            pytest.raises(HTTPException) as exc_info,
        ):
            dependency(project_id, current_user, project_service, membership_service)

        # THEN
        assert exc_info.value.status_code == 403
        extra = mock_logger.warning.call_args[1]["extra"]
        assert extra["event"] == "access_denied"
        assert extra["project_id"] == str(project_id)
        assert extra["user_id"] == str(user_id)
        assert extra["required_level"] == "admin"
