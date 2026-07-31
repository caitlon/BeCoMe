"""Tests for application factory wiring in api.main."""

from unittest.mock import patch

# Not a credential: the host is unroutable and the key is a literal placeholder.
_FAKE_DSN = "https://placeholder@localhost/0"


def _prod_env(monkeypatch, tmp_path) -> None:
    """Configure a valid production environment for Settings."""
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


class TestDocsExposure:
    """Interactive docs and the OpenAPI schema are gated by environment."""

    def test_docs_are_served_in_development(self):
        """In the default (dev) profile the docs and schema are available."""
        from api.main import create_app

        app = create_app()
        assert app.openapi_url == "/openapi.json"
        assert app.docs_url == "/docs"

    def test_docs_are_disabled_in_production(self, monkeypatch, tmp_path):
        """In production the docs and OpenAPI schema are not served."""
        from api.config import get_settings
        from api.main import create_app

        _prod_env(monkeypatch, tmp_path)
        get_settings.cache_clear()
        try:
            app = create_app()
            assert app.openapi_url is None
            assert app.docs_url is None
            assert app.redoc_url is None
        finally:
            get_settings.cache_clear()


class TestCorsExposedHeaders:
    """The browser is allowed to read the CSRF token header off a cross-origin reply."""

    def test_csrf_token_header_is_readable_cross_origin(self, monkeypatch, tmp_path):
        """A cross-origin response names X-CSRF-Token in Access-Control-Expose-Headers.

        The SPA and the API sit on separate hosts in every deployed environment, and a
        response header stays invisible to cross-origin JavaScript unless CORS says
        otherwise. Listing the header under allow_headers covers only the request
        direction, so without this the SPA gets the token handed to it and cannot see it.
        """
        from fastapi.testclient import TestClient

        from api.config import get_settings
        from api.main import create_app

        # chdir out of the repository first: the real .env would otherwise decide which
        # origins are allowed, and this test picks its own.
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')
        get_settings.cache_clear()
        try:
            client = TestClient(create_app())
            response = client.get("/api/v1/health", headers={"Origin": "https://app.example.com"})
        finally:
            get_settings.cache_clear()

        assert response.status_code == 200
        assert "X-CSRF-Token" in response.headers["access-control-expose-headers"]


class TestSentryInit:
    """Sentry is initialised so no credential can ride along on an event."""

    def test_is_a_no_op_without_a_dsn(self):
        """
        GIVEN no Sentry DSN is configured
        WHEN _init_sentry runs
        THEN no client is created, keeping development and tests offline
        """
        # GIVEN
        from api.config import Settings
        from api.main import _init_sentry

        settings = Settings(sentry_dsn="")

        # WHEN
        with patch("api.main.sentry_sdk.init") as mock_init:
            _init_sentry(settings)

        # THEN
        mock_init.assert_not_called()

    def test_disables_frame_locals_and_pii(self):
        """
        GIVEN a configured Sentry DSN
        WHEN _init_sentry runs
        THEN frame locals are off as well as default PII

        include_local_variables is a separate switch that send_default_pii does not
        govern, and it defaults to on. The auth handlers bind the parsed request body
        to a local, so with locals enabled any fault under register / change-password /
        reset-password would ship plaintext passwords and reset tokens to the tracker.
        """
        # GIVEN
        from api.config import Settings
        from api.main import _init_sentry

        settings = Settings(sentry_dsn=_FAKE_DSN)

        # WHEN
        with patch("api.main.sentry_sdk.init") as mock_init:
            _init_sentry(settings)

        # THEN
        kwargs = mock_init.call_args.kwargs
        assert kwargs["include_local_variables"] is False
        assert kwargs["send_default_pii"] is False
