"""Tests for application configuration."""

from typing import ClassVar

import pytest
from pydantic import ValidationError

from api.config import Environment, Settings


def _configure_prod(monkeypatch, tmp_path) -> None:
    """Set a fully valid production environment; each test then weakens one part."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://migrator:pass@host:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", "an-origin-verify-secret")
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("EMAIL_PROVIDER", "http")
    monkeypatch.setenv("EMAIL_API_KEY", "a-resend-api-key")
    monkeypatch.setenv("DEBUG", "false")


class TestStorageEnabled:
    """Tests for the storage_enabled property."""

    _BUCKET: ClassVar[dict[str, str]] = {
        "bucket_name": "become-photos",
        "bucket_endpoint": "https://storage.railway.app",
        "bucket_access_key_id": "key",
        "bucket_secret_access_key": "secret",
    }

    def test_returns_true_when_all_bucket_vars_set(self):
        """
        GIVEN Settings with all four bucket variables configured
        WHEN storage_enabled is accessed
        THEN it returns True
        """
        # GIVEN
        settings = Settings(secret_key="test-secret-key", **self._BUCKET)

        # WHEN/THEN
        assert settings.storage_enabled is True

    def test_returns_false_when_endpoint_missing(self):
        """
        GIVEN Settings missing the bucket endpoint
        WHEN storage_enabled is accessed
        THEN it returns False
        """
        # GIVEN
        settings = Settings(
            secret_key="test-secret-key",
            **{**self._BUCKET, "bucket_endpoint": None},
        )

        # WHEN/THEN
        assert settings.storage_enabled is False

    def test_returns_false_when_credentials_missing(self):
        """
        GIVEN Settings with only the bucket name and endpoint set
        WHEN storage_enabled is accessed
        THEN it returns False
        """
        # GIVEN
        settings = Settings(
            secret_key="test-secret-key",
            bucket_name="become-photos",
            bucket_endpoint="https://storage.railway.app",
        )

        # WHEN/THEN
        assert settings.storage_enabled is False

    def test_returns_false_when_unconfigured(self):
        """
        GIVEN Settings with no bucket variables
        WHEN storage_enabled is accessed
        THEN it returns False
        """
        # GIVEN
        settings = Settings(secret_key="test-secret-key")

        # WHEN/THEN
        assert settings.storage_enabled is False


class TestEmailEnabled:
    """Tests for email settings defaults and the email_enabled property."""

    @pytest.fixture(autouse=True)
    def _isolate_email_env(self, monkeypatch, tmp_path):
        """Isolate from the local .env file and any EMAIL_* process variables.

        Without this, a developer's local .env (which may set EMAIL_PROVIDER and
        EMAIL_API_KEY for real sending) leaks into these default-value tests and
        breaks them, even though CI -- with no .env -- stays green.
        """
        monkeypatch.chdir(tmp_path)
        for var in (
            "EMAIL_PROVIDER",
            "EMAIL_API_KEY",
            "EMAIL_FROM",
            "EMAIL_FROM_NAME",
            "FRONTEND_BASE_URL",
        ):
            monkeypatch.delenv(var, raising=False)

    def test_email_provider_defaults_to_console(self):
        """
        GIVEN Settings without an explicit email provider
        WHEN constructed
        THEN email_provider defaults to "console"
        """
        # GIVEN/WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.email_provider == "console"

    def test_token_ttl_defaults_to_60_minutes(self):
        """
        GIVEN Settings without an explicit reset-token TTL
        WHEN constructed
        THEN password_reset_token_ttl_minutes defaults to 60
        """
        # GIVEN/WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.password_reset_token_ttl_minutes == 60

    def test_verification_token_ttl_defaults_to_24_hours(self):
        """
        GIVEN Settings without an explicit verification-token TTL
        WHEN constructed
        THEN email_verification_token_ttl_hours defaults to 24
        """
        # GIVEN/WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.email_verification_token_ttl_hours == 24

    def test_returns_false_for_console_provider(self):
        """
        GIVEN the default console email provider
        WHEN email_enabled is accessed
        THEN it returns False (console never counts as a real send)
        """
        # GIVEN
        settings = Settings(secret_key="test-secret-key")

        # WHEN/THEN
        assert settings.email_enabled is False

    def test_returns_false_for_http_without_api_key(self):
        """
        GIVEN the http email provider but no API key
        WHEN email_enabled is accessed
        THEN it returns False
        """
        # GIVEN
        settings = Settings(secret_key="test-secret-key", email_provider="http")

        # WHEN/THEN
        assert settings.email_enabled is False

    def test_returns_true_for_http_with_api_key(self):
        """
        GIVEN the http email provider with an API key set
        WHEN email_enabled is accessed
        THEN it returns True
        """
        # GIVEN
        settings = Settings(
            secret_key="test-secret-key",
            email_provider="http",
            email_api_key="re_test_key",
        )

        # WHEN/THEN
        assert settings.email_enabled is True


class TestEmailPolicySettings:
    """Tests for the registration email-address policy kill switches."""

    def test_disposable_email_blocking_defaults_to_enabled(self):
        """
        GIVEN Settings without an explicit override
        WHEN constructed
        THEN disposable_email_blocking_enabled defaults to True
        """
        # GIVEN/WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.disposable_email_blocking_enabled is True

    def test_mx_check_defaults_to_enabled(self):
        """
        GIVEN Settings without an explicit override
        WHEN constructed
        THEN mx_check_enabled defaults to True
        """
        # GIVEN/WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.mx_check_enabled is True

    def test_disposable_email_blocking_can_be_disabled_via_env(self, monkeypatch, tmp_path):
        """
        GIVEN DISPOSABLE_EMAIL_BLOCKING_ENABLED=false in the environment
        WHEN Settings is constructed
        THEN the kill switch is off, with no code deploy required
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "irrelevant-for-dev")
        monkeypatch.setenv("DISPOSABLE_EMAIL_BLOCKING_ENABLED", "false")

        # WHEN
        settings = Settings()

        # THEN
        assert settings.disposable_email_blocking_enabled is False

    def test_mx_check_can_be_disabled_via_env(self, monkeypatch, tmp_path):
        """
        GIVEN MX_CHECK_ENABLED=false in the environment
        WHEN Settings is constructed
        THEN the kill switch is off, with no code deploy required
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "irrelevant-for-dev")
        monkeypatch.setenv("MX_CHECK_ENABLED", "false")

        # WHEN
        settings = Settings()

        # THEN
        assert settings.mx_check_enabled is False


class TestEnvironmentResolution:
    """Tests for APP_ENV profile resolution."""

    def test_defaults_to_dev_when_app_env_unset(self, monkeypatch, tmp_path):
        """
        GIVEN APP_ENV is not set in the environment
        WHEN Settings is constructed
        THEN the development profile is selected
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("APP_ENV", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.setenv("SECRET_KEY", "irrelevant-for-dev")

        # WHEN
        settings = Settings()

        # THEN
        assert settings.environment is Environment.DEV

    def test_reads_profile_from_app_env(self, monkeypatch, tmp_path):
        """
        GIVEN APP_ENV is set to a valid profile name
        WHEN Settings is constructed
        THEN the matching profile is selected
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", "an-origin-verify-secret")
        monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')
        monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.example.com")
        monkeypatch.setenv("EMAIL_PROVIDER", "http")
        monkeypatch.setenv("EMAIL_API_KEY", "a-resend-api-key")
        monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://migrator:pass@host:5432/db")

        # WHEN
        settings = Settings()

        # THEN
        assert settings.environment is Environment.PROD

    def test_invalid_app_env_raises(self, monkeypatch, tmp_path):
        """
        GIVEN APP_ENV holds a value outside the enum
        WHEN Settings is constructed
        THEN a ValueError is raised
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "bogus")
        monkeypatch.setenv("SECRET_KEY", "irrelevant")

        # WHEN/THEN
        with pytest.raises(ValueError):
            Settings()

    def test_testing_flag_reads_testing_var(self, monkeypatch, tmp_path):
        """
        GIVEN the TESTING variable is truthy
        WHEN Settings is constructed
        THEN the testing flag is True regardless of profile
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "irrelevant-for-dev")
        monkeypatch.setenv("TESTING", "1")

        # WHEN
        settings = Settings()

        # THEN
        assert settings.testing is True

    def test_rejects_environment_var_without_app_env(self, monkeypatch, tmp_path):
        """
        GIVEN ENVIRONMENT is set but APP_ENV is not
        WHEN Settings is constructed
        THEN a ValueError points the operator at APP_ENV
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("APP_ENV", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.setenv("SECRET_KEY", "irrelevant")

        # WHEN/THEN
        with pytest.raises(ValueError):
            Settings()


class TestEnvFileLayering:
    """Tests for base plus per-profile dotenv layering."""

    def test_profile_file_overrides_base_env(self, monkeypatch, tmp_path):
        """
        GIVEN a base .env and a profile .env.dev that both set DATABASE_URL
        WHEN Settings is constructed under the dev profile
        THEN the profile value overrides the base value
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text(
            "DATABASE_URL=postgresql://base/db\nSECRET_KEY=base-secret\n"
        )
        (tmp_path / ".env.dev").write_text("DATABASE_URL=postgresql://override/db\n")
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("SECRET_KEY", raising=False)

        # WHEN
        settings = Settings()

        # THEN
        assert settings.database_url == "postgresql://override/db"
        assert settings.secret_key == "base-secret"


class TestProductionInvariants:
    """Tests for production safety validation."""

    def test_rejects_insecure_secret_in_production(self, monkeypatch, tmp_path):
        """
        GIVEN the production profile with a default secret key
        WHEN Settings is constructed
        THEN validation fails
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("SECRET_KEY", "changeme")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")

        # WHEN/THEN
        with pytest.raises(ValidationError):
            Settings()

    def test_rejects_sqlite_in_production(self, monkeypatch, tmp_path):
        """
        GIVEN the production profile with a SQLite database URL
        WHEN Settings is constructed
        THEN validation fails
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./prod.db")

        # WHEN/THEN
        with pytest.raises(ValidationError):
            Settings()

    def test_accepts_strong_secret_and_postgres(self, monkeypatch, tmp_path):
        """
        GIVEN the production profile with a strong secret and PostgreSQL
        WHEN Settings is constructed
        THEN validation passes
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", "an-origin-verify-secret")
        monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')
        monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.example.com")
        monkeypatch.setenv("EMAIL_PROVIDER", "http")
        monkeypatch.setenv("EMAIL_API_KEY", "a-resend-api-key")
        monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://migrator:pass@host:5432/db")

        # WHEN
        settings = Settings()

        # THEN
        assert settings.environment is Environment.PROD

    def test_rejects_missing_redis_url_in_production(self, monkeypatch, tmp_path):
        """
        GIVEN the production profile with no REDIS_URL
        WHEN Settings is constructed
        THEN validation fails
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        monkeypatch.delenv("REDIS_URL", raising=False)

        # WHEN/THEN
        with pytest.raises(ValidationError, match="redis_url is required"):
            Settings()

    def test_rejects_missing_cloudflare_secret_in_production(self, monkeypatch, tmp_path):
        """
        GIVEN the production profile with no CLOUDFLARE_ORIGIN_SECRET
        WHEN Settings is constructed
        THEN validation fails so the client IP cannot be spoofed at the origin
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.delenv("CLOUDFLARE_ORIGIN_SECRET", raising=False)

        # WHEN/THEN
        with pytest.raises(ValidationError, match="cloudflare_origin_secret"):
            Settings()

    def test_rejects_short_secret_in_production(self, monkeypatch, tmp_path):
        """
        GIVEN the production profile with a short secret not in the blocklist
        WHEN Settings is constructed
        THEN validation fails
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("SECRET_KEY", "short-but-not-listed")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")

        # WHEN/THEN
        with pytest.raises(ValidationError):
            Settings()

    def test_rejects_localhost_cors_in_production(self, monkeypatch, tmp_path):
        """
        GIVEN the production profile with only localhost CORS origins
        WHEN Settings is constructed
        THEN validation fails so a forgotten frontend origin is caught at boot
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", "an-origin-verify-secret")
        monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000"]')

        # WHEN/THEN
        with pytest.raises(ValidationError, match="cors_origins"):
            Settings()

    def test_rejects_loopback_frontend_base_url_in_production(self, monkeypatch, tmp_path):
        """
        GIVEN a fully configured production profile still on the default frontend URL
        WHEN Settings is constructed
        THEN validation fails, so a deploy cannot mail activation links to localhost
        """
        # GIVEN
        _configure_prod(monkeypatch, tmp_path)
        monkeypatch.setenv("FRONTEND_BASE_URL", "http://localhost:5173")

        # WHEN/THEN
        with pytest.raises(ValidationError, match="frontend_base_url"):
            Settings()

    def test_rejects_unparseable_frontend_base_url_in_production(self, monkeypatch, tmp_path):
        """
        GIVEN a production profile whose frontend URL has no host at all
        WHEN Settings is constructed
        THEN validation fails, since a hostless value builds links to nowhere
        """
        # GIVEN
        _configure_prod(monkeypatch, tmp_path)
        monkeypatch.setenv("FRONTEND_BASE_URL", "app.example.com")

        # WHEN/THEN
        with pytest.raises(ValidationError, match="frontend_base_url"):
            Settings()

    def test_rejects_unconfigured_email_in_production(self, monkeypatch, tmp_path):
        """
        GIVEN the production profile with the HTTP email provider but no API key
        WHEN Settings is constructed
        THEN validation fails, so the console sender cannot silently take over and
            write reset links to the log instead of delivering them
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", "an-origin-verify-secret")
        monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')
        monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.example.com")
        monkeypatch.setenv("EMAIL_PROVIDER", "http")
        monkeypatch.delenv("EMAIL_API_KEY", raising=False)

        # WHEN/THEN
        with pytest.raises(ValidationError, match="email_api_key is required"):
            Settings()

    def test_rejects_console_email_provider_in_production(self, monkeypatch, tmp_path):
        """
        GIVEN the production profile left on the console email provider
        WHEN Settings is constructed
        THEN validation fails
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", "an-origin-verify-secret")
        monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')
        monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.example.com")
        monkeypatch.setenv("EMAIL_PROVIDER", "console")

        # WHEN/THEN
        with pytest.raises(ValidationError, match="email_api_key is required"):
            Settings()

    def test_rejects_debug_in_production(self, monkeypatch, tmp_path):
        """
        GIVEN a fully configured production profile with DEBUG on
        WHEN Settings is constructed
        THEN validation fails
        """
        # GIVEN
        _configure_prod(monkeypatch, tmp_path)
        monkeypatch.setenv("DEBUG", "true")

        # WHEN/THEN
        with pytest.raises(ValidationError, match="debug must be off"):
            Settings()

    def test_rejects_missing_migration_url_in_production(self, monkeypatch, tmp_path):
        """
        GIVEN a production profile with no MIGRATION_DATABASE_URL
        WHEN Settings is constructed
        THEN validation fails, so migrations cannot silently run as the app role
        """
        # GIVEN
        _configure_prod(monkeypatch, tmp_path)
        monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)

        # WHEN/THEN
        with pytest.raises(ValidationError, match="migration_database_url is required"):
            Settings()


class TestDeployedDevInvariants:
    """The dev profile is held to the deploy invariants when it runs on Railway.

    A dev *service* has its own database and a public URL, so "dev" there means the
    data is separate, not that the service may be weakly configured. A laptop and a
    CI runner carry no RAILWAY_* marker and stay unconstrained.
    """

    def _configure_railway_dev(self, monkeypatch, tmp_path):
        """Set a fully valid *deployed* dev environment; each test weakens one part."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "dev")
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://migrator:pass@host:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CORS_ORIGINS", '["https://dev.your-domain.example"]')
        monkeypatch.setenv("FRONTEND_BASE_URL", "https://dev.your-domain.example")
        monkeypatch.setenv("EMAIL_PROVIDER", "http")
        monkeypatch.setenv("EMAIL_API_KEY", "a-resend-api-key")
        monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", "a-dev-origin-lock-value")

    def test_local_dev_stays_unconstrained(self, monkeypatch, tmp_path):
        """
        GIVEN the dev profile with development defaults and no Railway marker
        WHEN Settings is constructed
        THEN validation passes
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "weak")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./become.db")

        # WHEN
        settings = Settings()

        # THEN
        assert settings.environment is Environment.DEV

    def test_railway_dev_rejects_weak_secret(self, monkeypatch, tmp_path):
        """
        GIVEN the dev profile on a Railway service with a weak secret
        WHEN Settings is constructed
        THEN validation fails
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "dev")
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "weak")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")

        # WHEN/THEN
        with pytest.raises(ValidationError, match="secret_key"):
            Settings()

    def test_railway_dev_accepts_a_full_configuration(self, monkeypatch, tmp_path):
        """
        GIVEN the dev profile on Railway configured like a real deploy
        WHEN Settings is constructed
        THEN validation passes
        """
        # GIVEN
        self._configure_railway_dev(monkeypatch, tmp_path)

        # WHEN
        settings = Settings()

        # THEN
        assert settings.environment is Environment.DEV

    def test_railway_dev_rejects_missing_cloudflare_secret(self, monkeypatch, tmp_path):
        """
        GIVEN the dev profile on Railway with no CLOUDFLARE_ORIGIN_SECRET
        WHEN Settings is constructed
        THEN validation fails, because the dev service is fronted by Cloudflare too
        """
        # GIVEN
        self._configure_railway_dev(monkeypatch, tmp_path)
        monkeypatch.delenv("CLOUDFLARE_ORIGIN_SECRET", raising=False)

        # WHEN/THEN
        with pytest.raises(ValidationError, match="cloudflare_origin_secret"):
            Settings()

    def test_pytest_profile_is_exempt_on_railway(self, monkeypatch, tmp_path):
        """
        GIVEN TESTING=1 alongside a Railway marker on the dev profile
        WHEN Settings is constructed
        THEN validation passes, so a CI job on Railway is not held to deploy rules
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TESTING", "1")
        monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "dev")
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "weak")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./become.db")

        # WHEN
        settings = Settings()

        # THEN
        assert settings.environment is Environment.DEV


class TestStagingInvariants:
    """The staging (TEST) profile enforces the same core invariants as prod."""

    def _configure_staging(self, monkeypatch, tmp_path):
        """Set a fully valid *deployed* staging environment; each test weakens one part.

        The conftest sets TESTING=1 for the whole suite, but the real staging deploy
        does not, so it is cleared here for the TEST-profile invariants to fire.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.setenv("APP_ENV", "test")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CORS_ORIGINS", '["https://staging.example.com"]')
        monkeypatch.setenv("FRONTEND_BASE_URL", "https://staging.example.com")
        monkeypatch.setenv("EMAIL_PROVIDER", "http")
        monkeypatch.setenv("EMAIL_API_KEY", "a-resend-api-key")
        monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://migrator:pass@host:5432/db")
        monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", "a-staging-origin-lock-value")

    def test_accepts_fully_configured_staging(self, monkeypatch, tmp_path):
        """
        GIVEN a fully configured staging profile
        WHEN Settings is constructed
        THEN validation passes
        """
        # GIVEN
        self._configure_staging(monkeypatch, tmp_path)

        # WHEN
        settings = Settings()

        # THEN
        assert settings.environment is Environment.TEST

    def test_rejects_missing_cloudflare_secret_in_staging(self, monkeypatch, tmp_path):
        """
        GIVEN the staging profile with no CLOUDFLARE_ORIGIN_SECRET
        WHEN Settings is constructed
        THEN validation fails, because staging is fronted by Cloudflare too
        """
        # GIVEN
        self._configure_staging(monkeypatch, tmp_path)
        monkeypatch.delenv("CLOUDFLARE_ORIGIN_SECRET", raising=False)

        # WHEN/THEN
        with pytest.raises(ValidationError, match="cloudflare_origin_secret"):
            Settings()

    def test_rejects_insecure_secret_in_staging(self, monkeypatch, tmp_path):
        """
        GIVEN the staging profile with a default secret key
        WHEN Settings is constructed
        THEN validation fails
        """
        # GIVEN
        self._configure_staging(monkeypatch, tmp_path)
        monkeypatch.setenv("SECRET_KEY", "changeme")

        # WHEN/THEN
        with pytest.raises(ValidationError, match="secret_key"):
            Settings()

    def test_rejects_missing_redis_url_in_staging(self, monkeypatch, tmp_path):
        """
        GIVEN the staging profile with no REDIS_URL
        WHEN Settings is constructed
        THEN validation fails
        """
        # GIVEN
        self._configure_staging(monkeypatch, tmp_path)
        monkeypatch.delenv("REDIS_URL", raising=False)

        # WHEN/THEN
        with pytest.raises(ValidationError, match="redis_url is required"):
            Settings()

    def test_rejects_localhost_cors_in_staging(self, monkeypatch, tmp_path):
        """
        GIVEN the staging profile with only localhost CORS origins
        WHEN Settings is constructed
        THEN validation fails
        """
        # GIVEN
        self._configure_staging(monkeypatch, tmp_path)
        monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000"]')

        # WHEN/THEN
        with pytest.raises(ValidationError, match="cors_origins"):
            Settings()

    def test_rejects_sqlite_in_staging(self, monkeypatch, tmp_path):
        """
        GIVEN the staging profile with a SQLite database URL
        WHEN Settings is constructed
        THEN validation fails
        """
        # GIVEN
        self._configure_staging(monkeypatch, tmp_path)
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./staging.db")

        # WHEN/THEN
        with pytest.raises(ValidationError, match="SQLite"):
            Settings()

    def test_rejects_unconfigured_email_in_staging(self, monkeypatch, tmp_path):
        """
        GIVEN the deployed staging profile with no email API key
        WHEN Settings is constructed
        THEN validation fails
        """
        # GIVEN
        self._configure_staging(monkeypatch, tmp_path)
        monkeypatch.delenv("EMAIL_API_KEY", raising=False)

        # WHEN/THEN
        with pytest.raises(ValidationError, match="email_api_key is required"):
            Settings()


class TestLoggingSettings:
    """Tests for logging-related settings."""

    def test_log_level_defaults_to_info(self):
        """
        GIVEN Settings without an explicit log level
        WHEN constructed
        THEN log_level defaults to INFO
        """
        # GIVEN/WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.log_level == "INFO"

    def test_log_file_defaults_to_none(self):
        """
        GIVEN Settings without an explicit log file
        WHEN constructed
        THEN log_file defaults to None
        """
        # GIVEN/WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.log_file is None

    def test_reads_log_level_from_env(self, monkeypatch, tmp_path):
        """
        GIVEN LOG_LEVEL is set in the environment
        WHEN Settings is constructed
        THEN log_level reflects the env value
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "irrelevant-for-dev")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        # WHEN
        settings = Settings()

        # THEN
        assert settings.log_level == "DEBUG"

    def test_normalizes_lowercase_log_level(self, monkeypatch, tmp_path):
        """
        GIVEN LOG_LEVEL set in lowercase
        WHEN Settings is constructed
        THEN log_level is upper-cased to a valid level
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "irrelevant-for-dev")
        monkeypatch.setenv("LOG_LEVEL", "debug")

        # WHEN
        settings = Settings()

        # THEN
        assert settings.log_level == "DEBUG"

    def test_rejects_invalid_log_level(self):
        """
        GIVEN an unsupported log level
        WHEN Settings is constructed
        THEN a validation error is raised at load time
        """
        # GIVEN/WHEN / THEN
        with pytest.raises(ValidationError):
            Settings(secret_key="test-secret-key", log_level="VERBOSE")

    def test_sentry_dsn_defaults_to_none(self):
        """
        GIVEN Settings without an explicit Sentry DSN
        WHEN constructed
        THEN sentry_dsn defaults to None
        """
        # GIVEN/WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.sentry_dsn is None

    def test_betterstack_fields_default_to_none(self):
        """
        GIVEN Settings without Better Stack variables
        WHEN constructed
        THEN both Better Stack fields default to None
        """
        # GIVEN/WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.betterstack_source_token is None
        assert settings.betterstack_ingesting_host is None


class TestProfileLogLevelDefault:
    """Tests for the per-profile LOG_LEVEL fallback."""

    @pytest.mark.parametrize(
        ("app_env", "expected"),
        [("dev", "DEBUG"), ("test", "INFO"), ("prod", "INFO")],
    )
    def test_unset_log_level_follows_the_profile(self, monkeypatch, tmp_path, app_env, expected):
        """
        GIVEN LOG_LEVEL is not set anywhere
        WHEN Settings is constructed under a given profile
        THEN log_level is that profile's default, not the bare field default
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.setenv("APP_ENV", app_env)
        monkeypatch.setenv("TESTING", "1")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value-for-tests")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://mig:pass@host:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", "an-origin-verify-secret-for-tests")
        monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')
        monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.example.com")
        monkeypatch.setenv("EMAIL_PROVIDER", "http")
        monkeypatch.setenv("EMAIL_API_KEY", "a-resend-api-key-for-tests")

        # WHEN
        settings = Settings()

        # THEN
        assert settings.log_level == expected

    def test_explicit_log_level_beats_the_profile_default(self, monkeypatch, tmp_path):
        """
        GIVEN LOG_LEVEL is set explicitly on a profile whose default differs
        WHEN Settings is constructed
        THEN the explicit value wins
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "irrelevant-for-dev")
        monkeypatch.setenv("LOG_LEVEL", "WARNING")

        # WHEN
        settings = Settings()

        # THEN: the dev default is DEBUG, so this proves the override, not the default
        assert settings.log_level == "WARNING"

    def test_explicit_kwarg_beats_the_profile_default(self, monkeypatch, tmp_path):
        """
        GIVEN log_level passed directly as a keyword argument
        WHEN Settings is constructed under the dev profile
        THEN the keyword wins over the profile default
        """
        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.setenv("APP_ENV", "dev")

        # WHEN
        settings = Settings(secret_key="irrelevant-for-dev", log_level="ERROR")

        # THEN
        assert settings.log_level == "ERROR"
