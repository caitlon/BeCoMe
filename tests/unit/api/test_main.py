"""Tests for application factory wiring in api.main."""

import asyncio
import logging
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

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
    """The browser is allowed to read the CSRF token and Retry-After headers cross-origin."""

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

    def test_retry_after_header_is_readable_cross_origin(self, monkeypatch, tmp_path):
        """A cross-origin response names Retry-After in Access-Control-Expose-Headers.

        The 429 answers carry the wait in that header, and the SPA's retry timer reads it;
        a cross-origin script sees it only when CORS exposes it.
        """
        from fastapi.testclient import TestClient

        from api.config import get_settings
        from api.main import create_app

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

        assert "Retry-After" in response.headers["access-control-expose-headers"]


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


class TestCorsOnRefusals:
    """A refusal from a guard middleware still reaches the SPA as a readable response.

    The SPA and the API sit on different hosts, so the browser hides any response that
    lacks Access-Control-Allow-Origin and the SPA sees a bare network error instead of
    the status and the reason. Every middleware that answers on its own therefore has to
    sit inside CORS.
    """

    _ORIGIN = "https://app.example.com"

    @pytest.fixture
    def client(self, monkeypatch, tmp_path) -> Iterator[TestClient]:
        """An app whose only allowed origin is _ORIGIN, built outside the repository's .env."""
        from api.config import get_settings
        from api.main import create_app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("CORS_ORIGINS", f'["{self._ORIGIN}"]')
        get_settings.cache_clear()
        try:
            yield TestClient(create_app())
        finally:
            get_settings.cache_clear()

    def _assert_readable_cross_origin(self, response) -> None:
        assert response.headers.get("access-control-allow-origin") == self._ORIGIN
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_csrf_refusal_carries_cors_headers(self, client):
        """
        GIVEN a cookie-authenticated mutation from the allowed origin without a CSRF token
        WHEN the CSRF check refuses it
        THEN the 403 carries the CORS headers, so the SPA can read why
        """
        from uuid import uuid4

        from api.auth.cookies import ACCESS_COOKIE
        from api.auth.jwt import create_access_token

        # The cookie goes in as a raw header: the client's jar keeps __Host- cookies
        # for https only, and this client talks plain http.
        token = create_access_token(uuid4(), sid="session-1")
        response = client.post(
            "/api/v1/projects",
            json={},
            headers={"Origin": self._ORIGIN, "Cookie": f"{ACCESS_COOKIE}={token}"},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "CSRF token missing or invalid"
        self._assert_readable_cross_origin(response)

    def test_body_size_refusal_carries_cors_headers(self, client):
        """
        GIVEN a request from the allowed origin declaring a body above the limit
        WHEN the body-size guard refuses it
        THEN the 413 carries the CORS headers
        """
        from api.middleware.body_size import DEFAULT_MAX_BODY_BYTES

        response = client.post(
            "/api/v1/calculate",
            content=b"x" * (DEFAULT_MAX_BODY_BYTES + 1),
            headers={"Origin": self._ORIGIN, "Content-Type": "application/json"},
        )

        assert response.status_code == 413
        self._assert_readable_cross_origin(response)


class TestUnhandledErrorResponse:
    """An exception no handler catches still answers a 500 the SPA can read.

    Starlette sends the 500 for an unhandled exception from ServerErrorMiddleware, which
    sits outside every user middleware, CORS included, so that answer had no CORS headers
    and the browser turned it into a network error.
    """

    _ORIGIN = "https://app.example.com"
    _PATH = "/api/v1/test-unhandled-error"

    @pytest.fixture
    def client(self, monkeypatch, tmp_path) -> Iterator[TestClient]:
        """An app with one route that raises, built outside the repository's .env."""
        from api.config import get_settings
        from api.main import create_app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("CORS_ORIGINS", f'["{self._ORIGIN}"]')
        get_settings.cache_clear()
        app = create_app()

        @app.get(self._PATH)
        def _boom() -> None:
            # Stands in for a parsed request body held in a local, such as a password.
            plaintext_secret = "local-value-that-must-not-reach-sentry"  # noqa: F841
            raise RuntimeError("boom")

        try:
            yield TestClient(app, raise_server_exceptions=False)
        finally:
            get_settings.cache_clear()

    def _get(self, client: TestClient):
        return client.get(self._PATH, headers={"Origin": self._ORIGIN, "X-Request-ID": "req-500"})

    def test_carries_cors_headers(self, client):
        """
        GIVEN a route that raises an exception no handler maps
        WHEN the allowed origin calls it
        THEN the opaque 500 carries the CORS and security headers, so the SPA can read it
        """
        response = self._get(client)

        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
        assert response.headers.get("access-control-allow-origin") == self._ORIGIN
        assert response.headers.get("access-control-allow-credentials") == "true"
        assert response.headers.get("x-request-id") == "req-500"
        assert response.headers.get("x-content-type-options") == "nosniff"

    def test_logs_the_exception_with_the_request_id(self, client):
        """
        GIVEN a route that raises an exception no handler maps
        WHEN it is called with a correlation ID
        THEN one ERROR record carries the traceback and that request id
        """
        with captured_log_records("api.exception") as records:
            self._get(client)

        assert len(records) == 1
        record = records[0]
        assert record.levelno == logging.ERROR
        assert record.exc_info is not None
        assert isinstance(record.exc_info[1], RuntimeError)
        assert record.request_id == "req-500"  # type: ignore[attr-defined]

    def test_reports_the_exception_to_sentry(self, client):
        """
        GIVEN Sentry initialised with a transport that keeps every envelope
        WHEN a route raises an exception no handler maps
        THEN exactly one error event reaches Sentry, carrying that exception as unhandled
        AND no frame local of the failing route
        """
        import sentry_sdk
        from sentry_sdk.transport import Transport

        class _KeepEnvelopes(Transport):
            def __init__(self) -> None:
                super().__init__()
                self.envelopes: list = []

            def capture_envelope(self, envelope) -> None:
                self.envelopes.append(envelope)

        transport = _KeepEnvelopes()
        previous = sentry_sdk.get_client()
        sentry_sdk.init(dsn=_FAKE_DSN, transport=transport, include_local_variables=False)
        try:
            self._get(client)
            sentry_sdk.flush()
        finally:
            sentry_sdk.get_global_scope().set_client(previous)

        events = [
            item.payload.json
            for envelope in transport.envelopes
            for item in envelope.items
            if item.type == "event"
        ]
        assert len(events) == 1
        reported = events[0]["exception"]["values"][-1]
        assert reported["type"] == "RuntimeError"
        # Unhandled, as the Starlette integration reported it before: Sentry ranks issue
        # priority, and with it the high-priority alert, on that flag.
        assert reported["mechanism"]["handled"] is False
        # The report is built by hand, so check it still honours the client's switch
        # that keeps frame locals out of the event.
        frames = [
            frame
            for value in events[0]["exception"]["values"]
            for frame in value.get("stacktrace", {}).get("frames", [])
        ]
        assert frames
        assert all("vars" not in frame for frame in frames)


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
    """The assistant router exists only when the ASSISTANT_ENABLED flag is on."""

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
        GIVEN the dev profile with the assistant switched on and a signed-in user
        WHEN the app is built and its config endpoint is requested
        THEN it answers 200 with the answer model, mode, and collection
        """
        from fastapi.testclient import TestClient

        from api.auth.dependencies import get_current_user
        from api.config import get_settings
        from api.db.models import User
        from api.main import create_app

        # GIVEN
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("ASSISTANT_ENABLED", "true")
        monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
        get_settings.cache_clear()
        try:
            app = create_app()
            app.dependency_overrides[get_current_user] = lambda: User(
                email="user@example.com", hashed_password="x", first_name="Test", last_name="User"
            )
            client = TestClient(app)

            # WHEN
            response = client.get("/api/v1/assistant/config")
        finally:
            get_settings.cache_clear()

        # THEN
        assert response.status_code == 200
        assert response.json() == {
            "enabled": True,
            "model": "Qwen/Qwen3.5-9B",
            "mode": "workflow",
            "collection": "docs_markdown_headers_500_o10_captions_bge_m3",
            "answer_provider": "local",
            "query_provider": "local",
            "embedding_provider": "local",
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
        THEN api.routes.assistant and the api.assistant package are in sys.modules only
             when the switch was on, so no deploy-loaded module imports the package

        Parametrized over both directions on purpose: a router registered
        unconditionally would still pass the "loaded when on" case, so only the
        "not loaded when off" case can catch that mistake.
        """
        # GIVEN
        env = {
            **os.environ,
            "APP_ENV": "dev",
            "SECRET_KEY": "a-sufficiently-strong-secret-value",  # pragma: allowlist secret
            "ASSISTANT_ENABLED": assistant_enabled,
            "PYTHONPATH": str(_REPO_ROOT),
        }
        env.pop("RAILWAY_ENVIRONMENT_NAME", None)
        snippet = (
            "import sys\n"
            "import api.main\n"
            "print('assistant_loaded=' + str('api.routes.assistant' in sys.modules))\n"
            "print('package_loaded=' + str('api.assistant' in sys.modules))\n"
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
        package_lines = [
            line for line in result.stdout.splitlines() if line.startswith("package_loaded=")
        ]
        assert package_lines, f"no package marker line in stdout: {result.stdout!r}"
        assert package_lines[-1] == f"package_loaded={expect_loaded}"


class TestAssistantExceptionHandlerGating:
    """The assistant's error handlers exist only when the ASSISTANT_ENABLED flag is on."""

    @pytest.fixture(autouse=True)
    def _clear_settings_cache_after(self):
        """Drop any Settings cached during the test, so its switch settings cannot leak."""
        from api.config import get_settings

        yield
        get_settings.cache_clear()

    @staticmethod
    def _build_app(monkeypatch, tmp_path, *, enabled: bool):
        """Build the app with the assistant switch set as asked.

        :return: The application built by create_app.
        """
        from api.config import get_settings
        from api.main import create_app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("ASSISTANT_ENABLED", "true" if enabled else "false")
        monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
        get_settings.cache_clear()
        return create_app()

    def test_handlers_are_absent_by_default(self, monkeypatch, tmp_path):
        """
        GIVEN the default settings (assistant disabled)
        WHEN the app is built
        THEN no handler is registered for any assistant error class
        """
        # GIVEN/WHEN
        app = self._build_app(monkeypatch, tmp_path, enabled=False)

        # THEN
        registered = {exc.__name__ for exc in app.exception_handlers if isinstance(exc, type)}
        assert not registered & {
            "AssistantBusyError",
            "AssistantRateLimitedError",
            "AssistantUnavailableError",
            "AssistantUpstreamError",
        }

    @pytest.mark.parametrize(
        ("error_name", "status_code", "detail"),
        [
            (
                "AssistantRateLimitedError",
                429,
                "Too many assistant messages. Please try again later.",
            ),
            ("AssistantBusyError", 503, "The assistant is temporarily unavailable"),
            ("AssistantUnavailableError", 503, "The assistant is temporarily unavailable"),
            ("AssistantUpstreamError", 503, "The assistant is temporarily unavailable"),
        ],
    )
    def test_handlers_answer_when_enabled(
        self, monkeypatch, tmp_path, error_name, status_code, detail
    ):
        """
        GIVEN the assistant switched on
        WHEN a route raises one of its chat errors
        THEN the response carries the mapped status and the neutral public detail
        """
        from fastapi.testclient import TestClient

        from api.assistant import errors

        # GIVEN
        app = self._build_app(monkeypatch, tmp_path, enabled=True)
        error = getattr(errors, error_name)

        waits = error_name in {"AssistantRateLimitedError", "AssistantBusyError"}
        extra: dict[str, object] = {"retry_after": 5} if waits else {}
        if error_name == "AssistantBusyError":
            extra["reason"] = "process"

        def boom() -> None:
            raise error("internal detail that must not leak", **extra)

        app.add_api_route("/__raise", boom)
        client = TestClient(app, raise_server_exceptions=False)

        # WHEN
        response = client.get("/__raise")

        # THEN
        assert response.status_code == status_code
        assert "internal detail" not in response.text
        assert response.json() == {"detail": detail}
        assert response.headers.get("Retry-After") == ("5" if waits else None)


_ASSISTANT_LIBRARIES = (
    "langchain",
    "langchain_core",
    "langchain_openai",
    "langgraph",
    "langsmith",
    "openai",
)


class TestAssistantLibrariesStayOutOfDeployedProcesses:
    """A process with the assistant off never loads the assistant's libraries."""

    @staticmethod
    def _modules_loaded_by_importing_api_main(tmp_path, assistant_enabled: str) -> list[str]:
        """Import api.main in a fresh interpreter and list the assistant modules it loaded.

        :param tmp_path: A working directory with no .env file in it.
        :param assistant_enabled: The value of ASSISTANT_ENABLED for the interpreter.
        :return: The names of the loaded modules that belong to the assistant package or to
            one of its libraries.
        """
        env = {
            **os.environ,
            "APP_ENV": "dev",
            "SECRET_KEY": "a-sufficiently-strong-secret-value",  # pragma: allowlist secret
            "ASSISTANT_ENABLED": assistant_enabled,
            "PYTHONPATH": str(_REPO_ROOT),
        }
        env.pop("RAILWAY_ENVIRONMENT_NAME", None)
        snippet = (
            "import sys\n"
            "import api.main\n"
            f"libraries = {_ASSISTANT_LIBRARIES!r}\n"
            "print('loaded=' + ' '.join(sorted(\n"
            "    name for name in sys.modules\n"
            "    if name == 'api.assistant' or name.startswith('api.assistant.')\n"
            "    or name.split('.')[0] in libraries\n"
            ")))\n"
        )
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell; sys.executable is trusted
            [sys.executable, "-c", snippet],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        (line,) = [row for row in result.stdout.splitlines() if row.startswith("loaded=")]
        return line.removeprefix("loaded=").split()

    def test_nothing_of_the_assistant_or_its_libraries_is_loaded_when_the_switch_is_off(
        self, tmp_path
    ):
        """
        GIVEN a fresh interpreter with the assistant switched off
        WHEN it imports api.main, which builds the app, its middleware and its routers
        THEN neither the assistant package nor langchain, langgraph, langsmith or openai
             was imported, so a deployed image without the assistant extra still starts
        """
        # WHEN
        loaded = self._modules_loaded_by_importing_api_main(tmp_path, "false")

        # THEN
        assert loaded == []

    def test_the_same_probe_sees_them_when_the_switch_is_on(self, tmp_path):
        """
        GIVEN the same probe with the assistant switched on
        WHEN api.main is imported
        THEN the assistant package and langchain_core are reported, so the empty list above
             means "not imported" and not "not looked for"
        """
        # WHEN
        loaded = self._modules_loaded_by_importing_api_main(tmp_path, "true")

        # THEN
        assert "api.assistant.deps" in loaded
        assert "langchain_core" in loaded


class TestAssistantShutdown:
    """The application flushes the assistant's traces when it stops, and only when it is on."""

    @pytest.fixture(autouse=True)
    def _clear_settings_cache_after(self):
        """Drop any Settings cached during the test, so its switch settings cannot leak."""
        from api.config import get_settings

        yield
        get_settings.cache_clear()

    @staticmethod
    def _run_app(
        monkeypatch, tmp_path, *, enabled: bool, shutdown_error: Exception | None = None
    ) -> tuple[MagicMock, list[int]]:
        """Start and stop the app with the assistant switched as asked.

        :param shutdown_error: What the tracing shutdown raises, if anything.
        :return: The mock standing in for the tracing shutdown, and the number of times it
            had been called while the app was running.
        """
        from fastapi.testclient import TestClient

        from api.config import get_settings
        from api.main import create_app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("ASSISTANT_ENABLED", "true" if enabled else "false")
        monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
        get_settings.cache_clear()
        with (
            patch("api.main.create_db_and_tables"),
            patch("api.main.warm_up_connection_pool"),
            patch(
                "api.assistant.agent.tracing.shutdown_tracing", side_effect=shutdown_error
            ) as shutdown,
        ):
            app = create_app()
            with TestClient(app):
                calls_while_running = shutdown.call_count
        return shutdown, [calls_while_running]

    def test_traces_are_flushed_once_when_the_app_stops_with_the_assistant_on(
        self, monkeypatch, tmp_path
    ):
        """
        GIVEN the assistant switched on
        WHEN the app starts and then stops
        THEN the tracing shutdown ran exactly once, after the app had been running
        """
        # WHEN
        shutdown, calls_while_running = self._run_app(monkeypatch, tmp_path, enabled=True)

        # THEN
        assert calls_while_running == [0]
        shutdown.assert_called_once_with()

    def test_the_assistants_resources_are_closed_when_the_app_stops_with_it_on(
        self, monkeypatch, tmp_path
    ):
        """
        GIVEN the assistant switched on
        WHEN the app starts and then stops
        THEN its resources were closed once
        """
        # GIVEN
        with patch("api.assistant.deps.close_assistant_resources", new=AsyncMock()) as close:
            # WHEN
            self._run_app(monkeypatch, tmp_path, enabled=True)

        # THEN
        close.assert_awaited_once_with()

    def test_the_resources_are_closed_even_when_the_tracing_shutdown_fails(
        self, monkeypatch, tmp_path
    ):
        """
        GIVEN the assistant switched on and a tracing shutdown that raises
        WHEN the app starts and then stops
        THEN the error still reaches the caller, and the assistant's resources were closed
        """
        # WHEN
        with (
            patch("api.assistant.deps.close_assistant_resources", new=AsyncMock()) as close,
            pytest.raises(RuntimeError, match="flush failed"),
        ):
            self._run_app(
                monkeypatch, tmp_path, enabled=True, shutdown_error=RuntimeError("flush failed")
            )

        # THEN
        close.assert_awaited_once_with()

    def test_no_resources_are_closed_with_the_assistant_off(self, monkeypatch, tmp_path):
        """
        GIVEN the assistant switched off
        WHEN the app starts and then stops
        THEN nothing of the assistant was closed
        """
        # GIVEN
        with patch("api.assistant.deps.close_assistant_resources", new=AsyncMock()) as close:
            # WHEN
            self._run_app(monkeypatch, tmp_path, enabled=False)

        # THEN
        close.assert_not_awaited()

    def test_nothing_is_flushed_with_the_assistant_off(self, monkeypatch, tmp_path):
        """
        GIVEN the assistant switched off
        WHEN the app starts and then stops
        THEN the tracing shutdown never ran
        """
        # WHEN
        shutdown, _ = self._run_app(monkeypatch, tmp_path, enabled=False)

        # THEN
        shutdown.assert_not_called()


class TestStartupChecksWiring:
    """The lifespan runs the startup checks in the background, and never in a test run."""

    @pytest.fixture(autouse=True)
    def _clear_settings_cache_after(self):
        """Drop any Settings cached during the test, so its switch settings cannot leak."""
        from api.config import get_settings

        yield
        get_settings.cache_clear()

    @staticmethod
    @contextmanager
    def _running_app(monkeypatch, tmp_path, *, testing: bool, checks) -> Iterator[TestClient]:
        """Run the app under its lifespan with ``run_startup_checks`` replaced.

        :param testing: The value of ``TESTING`` for the app's settings.
        :param checks: The coroutine function standing in for ``run_startup_checks``.
        :return: The test client, inside the lifespan; the app stops when the block ends.
        """
        from api.config import get_settings
        from api.main import create_app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
        monkeypatch.setenv("ASSISTANT_ENABLED", "false")
        monkeypatch.setenv("TESTING", "1" if testing else "0")
        monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
        get_settings.cache_clear()
        with (
            patch("api.main.create_db_and_tables"),
            patch("api.main.warm_up_connection_pool"),
            patch("api.main.run_startup_checks", new=checks),
            TestClient(create_app()) as client,
        ):
            yield client

    def test_nothing_is_scheduled_in_a_test_run(self, monkeypatch, tmp_path):
        """
        GIVEN TESTING set
        WHEN the app starts and stops
        THEN the startup checks never ran, so the suite never reaches a network
        """
        # GIVEN
        checks = AsyncMock()

        # WHEN
        with self._running_app(monkeypatch, tmp_path, testing=True, checks=checks):
            pass

        # THEN
        checks.assert_not_called()

    def test_the_checks_run_in_the_background_once_the_app_has_started(self, monkeypatch, tmp_path):
        """
        GIVEN TESTING unset
        WHEN the app starts and stops
        THEN the checks ran once, with the app's settings, and the app answered while they
             were still running
        """
        # GIVEN
        started = threading.Event()
        release = threading.Event()
        seen = []

        async def checks(settings):
            seen.append(settings)
            started.set()
            while not release.is_set():
                await asyncio.sleep(0.01)

        # WHEN
        with self._running_app(monkeypatch, tmp_path, testing=False, checks=checks) as client:
            assert started.wait(timeout=5)
            response = client.get("/api/v1/health")
            release.set()

        # THEN
        assert response.status_code == 200
        assert len(seen) == 1
        assert seen[0].testing is False

    def test_a_check_still_running_is_cancelled_before_the_app_logs_its_stop(
        self, monkeypatch, tmp_path
    ):
        """
        GIVEN a startup check that never finishes
        WHEN the app stops
        THEN the check had been cancelled by the time the shutdown record was written. The
             test client cancels leftover tasks when its loop closes, which is after that
             record, so only the lifespan's own cancel can satisfy this.
        """
        # GIVEN
        started = threading.Event()
        cancelled = []
        cancelled_at_shutdown = []

        async def checks(settings):
            started.set()
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                cancelled.append(True)
                raise

        def record(message, *args, **kwargs):
            if kwargs.get("extra", {}).get("event") == "app_shutdown":
                cancelled_at_shutdown.append(list(cancelled))

        # WHEN
        with (
            patch("api.main.logger.info", side_effect=record),
            self._running_app(monkeypatch, tmp_path, testing=False, checks=checks),
        ):
            assert started.wait(timeout=5)

        # THEN
        assert cancelled_at_shutdown == [[True]]
