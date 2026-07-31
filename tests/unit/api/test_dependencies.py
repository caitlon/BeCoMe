"""Tests for centralized FastAPI dependencies."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import dns.resolver
import pytest
from fastapi import HTTPException

from api.config import Settings, get_settings
from api.dependencies import (
    AccessLevel,
    RequireProjectAccess,
    get_email_address_policy,
    get_email_service,
    get_password_reset_service,
    get_storage_service,
)
from api.exceptions import DisposableEmailDomainError, UnresolvableEmailDomainError
from api.services.email.console_email_sender import ConsoleEmailSender
from api.services.email.resend_email_sender import ResendEmailSender
from api.services.email_policy import get_domain_verdict_cache
from api.services.password_reset_service import PasswordResetService
from api.services.storage.exceptions import StorageConfigurationError
from api.services.storage.railway_bucket_storage_service import RailwayBucketStorageService


class TestGetStorageService:
    """Tests for the get_storage_service factory function."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        """Reset the cached singleton so each case exercises the factory fresh.

        get_storage_service is an ``lru_cache`` process singleton; without this
        the first call's result would be reused by the others.
        """
        get_storage_service.cache_clear()
        yield
        get_storage_service.cache_clear()

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


class TestGetEmailAddressPolicy:
    """Tests for the get_email_address_policy factory function.

    These exercise the real factory end-to-end so a setting change is proven to
    reach the constructed policy's actual behaviour, not just the constructor
    kwarg it is passed to. The DNS resolver is always mocked; no test performs
    real DNS I/O.
    """

    @pytest.fixture(autouse=True)
    def _clear_caches(self, monkeypatch):
        """Reset every process-singleton cache the factory reaches into.

        get_email_address_policy is itself an lru_cache singleton, and building
        one with no explicit cache= override reaches get_domain_verdict_cache
        (another lru_cache singleton keyed on the real, separately-cached
        Settings). REDIS_URL is forced empty so that cache backend is always the
        deterministic in-memory one, never a real Redis client.
        """
        monkeypatch.setenv("REDIS_URL", "")
        get_email_address_policy.cache_clear()
        get_domain_verdict_cache.cache_clear()
        get_settings.cache_clear()
        yield
        get_email_address_policy.cache_clear()
        get_domain_verdict_cache.cache_clear()
        get_settings.cache_clear()

    def test_disposable_check_enabled_true_rejects_a_blocklisted_domain(self):
        """
        GIVEN disposable_email_blocking_enabled=True in settings
        WHEN the factory-built policy checks a well-known disposable domain
        THEN DisposableEmailDomainError is raised
        """
        # GIVEN
        mock_settings = MagicMock(spec=Settings)
        mock_settings.disposable_email_blocking_enabled = True
        mock_settings.mx_check_enabled = False  # isolate the disposable switch

        # WHEN / THEN
        # The resolver is still constructed (mx_check_enabled only skips using
        # it), so it is stubbed here too even though nothing calls .resolve().
        with (
            patch("api.dependencies.get_settings", return_value=mock_settings),
            patch("dns.asyncresolver.Resolver", return_value=MagicMock()),
        ):
            policy = get_email_address_policy()
            with pytest.raises(DisposableEmailDomainError):
                asyncio.run(policy.check("user@mailinator.com"))

    def test_disposable_check_enabled_false_lets_a_blocklisted_domain_through(self):
        """
        GIVEN disposable_email_blocking_enabled=False in settings
        WHEN the factory-built policy checks the same well-known disposable domain
        THEN no error is raised

        This is the behaviour the setting must actually control -- not merely a
        value it parses into.
        """
        # GIVEN
        mock_settings = MagicMock(spec=Settings)
        mock_settings.disposable_email_blocking_enabled = False
        mock_settings.mx_check_enabled = False  # isolate the disposable switch

        # WHEN / THEN (no raise)
        # The resolver is still constructed (mx_check_enabled only skips using
        # it), so it is stubbed here too even though nothing calls .resolve().
        with (
            patch("api.dependencies.get_settings", return_value=mock_settings),
            patch("dns.asyncresolver.Resolver", return_value=MagicMock()),
        ):
            policy = get_email_address_policy()
            asyncio.run(policy.check("user@mailinator.com"))

    def test_mx_check_enabled_true_rejects_an_unresolvable_domain(self):
        """
        GIVEN mx_check_enabled=True in settings
        WHEN the factory-built policy checks a domain the resolver cannot find
        THEN UnresolvableEmailDomainError is raised
        """
        # GIVEN
        mock_settings = MagicMock(spec=Settings)
        mock_settings.disposable_email_blocking_enabled = False
        mock_settings.mx_check_enabled = True
        stub_resolver = MagicMock()
        stub_resolver.resolve = AsyncMock(side_effect=dns.resolver.NXDOMAIN())

        # WHEN / THEN
        with (
            patch("api.dependencies.get_settings", return_value=mock_settings),
            patch("dns.asyncresolver.Resolver", return_value=stub_resolver),
        ):
            policy = get_email_address_policy()
            with pytest.raises(UnresolvableEmailDomainError):
                asyncio.run(policy.check("user@example.com"))

    def test_mx_check_enabled_false_skips_the_dns_lookup_entirely(self):
        """
        GIVEN mx_check_enabled=False in settings
        WHEN the factory-built policy checks a domain that would otherwise be
        rejected
        THEN no error is raised and the resolver is never consulted

        This is the behaviour the setting must actually control -- not merely a
        value it parses into.
        """
        # GIVEN
        mock_settings = MagicMock(spec=Settings)
        mock_settings.disposable_email_blocking_enabled = False
        mock_settings.mx_check_enabled = False
        stub_resolver = MagicMock()
        stub_resolver.resolve = AsyncMock(side_effect=dns.resolver.NXDOMAIN())

        # WHEN
        with (
            patch("api.dependencies.get_settings", return_value=mock_settings),
            patch("dns.asyncresolver.Resolver", return_value=stub_resolver),
        ):
            policy = get_email_address_policy()
            asyncio.run(policy.check("user@example.com"))

        # THEN
        stub_resolver.resolve.assert_not_awaited()

    def test_is_a_singleton(self):
        """
        GIVEN two calls to get_email_address_policy()
        WHEN compared
        THEN they return the identical instance, so the resolver is built once
        """
        # GIVEN / WHEN
        first = get_email_address_policy()
        second = get_email_address_policy()

        # THEN
        assert first is second


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
        mock_cache = MagicMock()

        # WHEN
        result = get_password_reset_service(mock_session, mock_cache)

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

    def test_logs_and_raises_403_when_member_lacks_level(self):
        """A member without the required level gets a logged 403, not a 404."""
        # GIVEN
        project_id = uuid4()
        user_id = uuid4()
        project_service = MagicMock()
        project_service.get_project.return_value = MagicMock()
        membership_service = MagicMock()
        membership_service.is_member.return_value = True
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
        assert extra["reason"] == "insufficient_level"

    def test_returns_404_when_not_member(self):
        """A non-member gets a 404 so project existence stays hidden."""
        # GIVEN
        project_id = uuid4()
        user_id = uuid4()
        project_service = MagicMock()
        project_service.get_project.return_value = MagicMock()
        membership_service = MagicMock()
        membership_service.is_member.return_value = False
        current_user = MagicMock()
        current_user.id = user_id
        dependency = RequireProjectAccess(AccessLevel.MEMBER)

        # WHEN / THEN
        with pytest.raises(HTTPException) as exc_info:
            dependency(project_id, current_user, project_service, membership_service)

        assert exc_info.value.status_code == 404
