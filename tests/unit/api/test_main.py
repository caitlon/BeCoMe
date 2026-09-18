"""Tests for application factory wiring in api.main."""

import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.shared.helpers import captured_log_records

# Not a credential: the host is unroutable and the key is a literal placeholder.
_FAKE_DSN = "https://placeholder@localhost/0"

# Repository root, used to give a subprocess a PYTHONPATH so it can import api.main
# regardless of its own cwd.
_REPO_ROOT = Path(__file__).resolve().parents[3]


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
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "a-turnstile-secret")
    monkeypatch.setenv("TURNSTILE_HOSTNAMES", '["app.example.com"]')


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


class TestCorsAllowedHeaders:
    """The browser is allowed to send the Turnstile token on a cross-origin request."""

    def test_turnstile_token_header_survives_preflight(self, monkeypatch, tmp_path):
        """A preflight asking for X-Turnstile-Token is answered with it allowed.

        The SPA and the API sit on separate hosts, so every guarded sign-up and sign-in
        is a cross-origin request with a custom header, which the browser will not send
        until the preflight says it may. Without the header on allow_origins' sibling
        list the request never leaves the page, and the bot check would look broken from
        the outside while never having been reached.
        """
        from fastapi.testclient import TestClient

        from api.config import get_settings
        from api.main import create_app

        # chdir out of the repository first, as the sibling test above does: the real
        # .env would otherwise decide which origins are allowed.
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')
        get_settings.cache_clear()
        try:
            client = TestClient(create_app())
            response = client.options(
                "/api/v1/auth/register",
                headers={
                    "Origin": "https://app.example.com",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "X-Turnstile-Token",
                },
            )
        finally:
            get_settings.cache_clear()

        assert response.status_code == 200
        assert "x-turnstile-token" in response.headers["access-control-allow-headers"].lower()


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


class TestBotCheckStartupRecord:
    """A deploy running with the bot check switched off says so at startup.

    ``TURNSTILE_ENABLED`` is a kill switch, so a deployed service is allowed to start
    with the check off (see ``Settings._validate_deploy_invariants``). What it is not
    allowed to do is start quietly: the four unauthenticated auth endpoints are then
    open to a script, and nothing downstream can tell that state from a laptop's. The
    record goes out at ERROR because that is what Sentry turns into an event and what a
    Better Stack alert keys on.
    """

    @staticmethod
    def _create_app_capturing_records(monkeypatch, tmp_path, *, bot_check: str):
        """Build the app in a deployed profile and return what api.main logged.

        :param monkeypatch: pytest monkeypatch fixture.
        :param tmp_path: Directory to run in, away from the repository .env.
        :param bot_check: Value for TURNSTILE_ENABLED.
        :return: The records api.main emitted while the app was built.
        """
        from api.config import get_settings
        from api.main import create_app

        _prod_env(monkeypatch, tmp_path)
        monkeypatch.setenv("TURNSTILE_ENABLED", bot_check)
        get_settings.cache_clear()
        try:
            with captured_log_records("api.main") as records:
                create_app()
        finally:
            get_settings.cache_clear()
        return records

    def test_records_an_error_when_a_deploy_starts_with_the_check_off(self, monkeypatch, tmp_path):
        """
        GIVEN a production profile with TURNSTILE_ENABLED false
        WHEN the application is built
        THEN one ERROR names the disabled bot check and the profile it runs in
        """
        # GIVEN/WHEN
        records = self._create_app_capturing_records(monkeypatch, tmp_path, bot_check="false")

        # THEN
        errors = [record for record in records if record.levelno == logging.ERROR]
        assert [getattr(record, "event", None) for record in errors] == ["turnstile_disabled"]
        assert getattr(errors[0], "environment", None) == "prod"

    def test_stays_quiet_when_the_deploy_runs_the_check(self, monkeypatch, tmp_path):
        """
        GIVEN a production profile with the bot check switched on
        WHEN the application is built
        THEN nothing is recorded at ERROR, so the alert means what it says
        """
        # GIVEN/WHEN
        records = self._create_app_capturing_records(monkeypatch, tmp_path, bot_check="true")

        # THEN
        assert [record for record in records if record.levelno >= logging.ERROR] == []


class TestAssistantRouterGating:
    """The assistant router exists only when the local-only flag is on."""

    def test_config_endpoint_is_absent_by_default(self, monkeypatch, tmp_path):
        """
        GIVEN the default settings (assistant disabled, no .env file in reach)
        WHEN the app is built and its config endpoint is requested
        THEN the whole assistant prefix is unrouted, so the response is 404
        """
        from fastapi.testclient import TestClient

        from api.config import get_settings
        from api.main import create_app

        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.delenv("ASSISTANT_ENABLED", raising=False)
        monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
        get_settings.cache_clear()
        try:
            client = TestClient(create_app())

            # WHEN
            response = client.get("/api/v1/assistant/config")
        finally:
            get_settings.cache_clear()

        # THEN
        assert response.status_code == 404

    def test_config_endpoint_serves_the_active_configuration_when_enabled(
        self, monkeypatch, tmp_path
    ):
        """
        GIVEN the dev profile with the assistant switched on
        WHEN the app is built and its config endpoint is requested
        THEN it answers 200 with the active model, mode, and collection
        """
        from fastapi.testclient import TestClient

        from api.config import get_settings
        from api.main import create_app

        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("ASSISTANT_ENABLED", "true")
        monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
        get_settings.cache_clear()
        try:
            client = TestClient(create_app())

            # WHEN
            response = client.get("/api/v1/assistant/config")
        finally:
            get_settings.cache_clear()

        # THEN
        assert response.status_code == 200
        assert response.json() == {
            "enabled": True,
            "model": "Qwen/Qwen3-4B-Instruct-2507",
            "mode": "hybrid",
            "collection": "docs_default",
        }

    @pytest.mark.parametrize(
        ("assistant_enabled", "expect_loaded"),
        [
            ("false", False),
            ("true", True),
        ],
    )
    def test_assistant_module_is_imported_only_when_the_switch_is_on(
        self, tmp_path, assistant_enabled, expect_loaded
    ):
        """
        GIVEN a fresh interpreter with ASSISTANT_ENABLED set to the given value
        WHEN it imports api.main, which builds the app and its routers at import
        THEN api.routes.assistant is in sys.modules only when the switch was on

        Parametrized over both directions on purpose: a router registered
        unconditionally would still pass the "loaded when on" case, so only the
        "not loaded when off" case can catch that mistake.
        """
        # GIVEN
        env = {
            **os.environ,
            "APP_ENV": "dev",
            "SECRET_KEY": "a-sufficiently-strong-secret-value",
            "ASSISTANT_ENABLED": assistant_enabled,
            "PYTHONPATH": str(_REPO_ROOT),
        }
        env.pop("RAILWAY_ENVIRONMENT_NAME", None)
        snippet = (
            "import sys\n"
            "import api.main\n"
            "print('assistant_loaded=' + str('api.routes.assistant' in sys.modules))\n"
        )

        # WHEN
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell; sys.executable is trusted
            [sys.executable, "-c", snippet],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

        # THEN
        marker_lines = [
            line for line in result.stdout.splitlines() if line.startswith("assistant_loaded=")
        ]
        assert marker_lines, f"no marker line in stdout: {result.stdout!r}"
        assert marker_lines[-1] == f"assistant_loaded={expect_loaded}"
