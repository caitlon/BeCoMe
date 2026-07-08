"""Tests for application factory wiring in api.main."""


def _prod_env(monkeypatch, tmp_path) -> None:
    """Configure a valid production environment for Settings."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", "an-origin-verify-secret")
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')


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
