"""Tests for application configuration."""

from typing import ClassVar

import pytest
from pydantic import ValidationError

from api.config import Environment, Settings


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

        # WHEN / THEN
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

        # WHEN / THEN
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

        # WHEN / THEN
        assert settings.storage_enabled is False

    def test_returns_false_when_unconfigured(self):
        """
        GIVEN Settings with no bucket variables
        WHEN storage_enabled is accessed
        THEN it returns False
        """
        # GIVEN
        settings = Settings(secret_key="test-secret-key")

        # WHEN / THEN
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
        # GIVEN / WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.email_provider == "console"

    def test_token_ttl_defaults_to_60_minutes(self):
        """
        GIVEN Settings without an explicit reset-token TTL
        WHEN constructed
        THEN password_reset_token_ttl_minutes defaults to 60
        """
        # GIVEN / WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.password_reset_token_ttl_minutes == 60

    def test_returns_false_for_console_provider(self):
        """
        GIVEN the default console email provider
        WHEN email_enabled is accessed
        THEN it returns False (console never counts as a real send)
        """
        # GIVEN
        settings = Settings(secret_key="test-secret-key")

        # WHEN / THEN
        assert settings.email_enabled is False

    def test_returns_false_for_http_without_api_key(self):
        """
        GIVEN the http email provider but no API key
        WHEN email_enabled is accessed
        THEN it returns False
        """
        # GIVEN
        settings = Settings(secret_key="test-secret-key", email_provider="http")

        # WHEN / THEN
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

        # WHEN / THEN
        assert settings.email_enabled is True


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

        # WHEN / THEN
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

        # WHEN / THEN
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

        # WHEN / THEN
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

        # WHEN / THEN
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

        # WHEN
        settings = Settings()

        # THEN
        assert settings.environment is Environment.PROD

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

        # WHEN / THEN
        with pytest.raises(ValidationError):
            Settings()


class TestLoggingSettings:
    """Tests for logging-related settings."""

    def test_log_level_defaults_to_info(self):
        """
        GIVEN Settings without an explicit log level
        WHEN constructed
        THEN log_level defaults to INFO
        """
        # GIVEN / WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.log_level == "INFO"

    def test_log_file_defaults_to_none(self):
        """
        GIVEN Settings without an explicit log file
        WHEN constructed
        THEN log_file defaults to None
        """
        # GIVEN / WHEN
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
        # GIVEN / WHEN / THEN
        with pytest.raises(ValidationError):
            Settings(secret_key="test-secret-key", log_level="VERBOSE")

    def test_sentry_dsn_defaults_to_none(self):
        """
        GIVEN Settings without an explicit Sentry DSN
        WHEN constructed
        THEN sentry_dsn defaults to None
        """
        # GIVEN / WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.sentry_dsn is None

    def test_betterstack_fields_default_to_none(self):
        """
        GIVEN Settings without Better Stack variables
        WHEN constructed
        THEN both Better Stack fields default to None
        """
        # GIVEN / WHEN
        settings = Settings(secret_key="test-secret-key")

        # THEN
        assert settings.betterstack_source_token is None
        assert settings.betterstack_ingesting_host is None
