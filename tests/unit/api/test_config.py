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
