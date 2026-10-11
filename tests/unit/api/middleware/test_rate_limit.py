"""Tests for rate limiting middleware."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse

from api.middleware.rate_limit import build_limiter, rate_limit_handler


class TestRateLimitHandler:
    """Tests for the logging rate-limit handler wrapper."""

    def test_logs_violation_as_warning(self):
        """
        GIVEN a rate-limit violation
        WHEN rate_limit_handler runs
        THEN it logs a WARNING carrying the path and client IP
        """
        # GIVEN
        request = MagicMock()
        request.url.path = "/auth/login"
        request.state.request_id = "rid-9"
        exc = MagicMock()

        # WHEN
        with (
            patch("api.middleware.rate_limit.logger") as mock_logger,
            patch("api.middleware.rate_limit._rate_limit_exceeded_handler"),
            patch("api.middleware.rate_limit.get_client_ip", return_value="203.0.113.7"),
        ):
            rate_limit_handler(request, exc)

        # THEN
        mock_logger.warning.assert_called_once()
        extra = mock_logger.warning.call_args[1]["extra"]
        assert extra["path"] == "/auth/login"
        assert extra["ip"] == "203.0.113.7"

    def test_delegates_to_slowapi_handler(self):
        """
        GIVEN a rate-limit violation
        WHEN rate_limit_handler runs
        THEN it returns the response from the slowapi handler
        """
        # GIVEN
        request = MagicMock()
        exc = MagicMock()
        sentinel = MagicMock()

        # WHEN
        with (
            patch("api.middleware.rate_limit.logger"),
            patch(
                "api.middleware.rate_limit._rate_limit_exceeded_handler",
                return_value=sentinel,
            ) as mock_delegate,
        ):
            result = rate_limit_handler(request, exc)

        # THEN
        assert result is sentinel
        mock_delegate.assert_called_once_with(request, exc)


class TestRetryAfterHeader:
    """The 429 tells the client how long to wait, which slowapi leaves out by default."""

    @staticmethod
    def _request(*, view_rate_limit, reset: float | Exception = 0.0) -> MagicMock:
        """Build a request whose limiter reports ``reset`` as the window's close time."""
        request = MagicMock()
        request.state.view_rate_limit = view_rate_limit
        stats = request.app.state.limiter.limiter.get_window_stats
        if isinstance(reset, Exception):
            stats.side_effect = reset
        else:
            stats.return_value = (reset, 0)
        return request

    @staticmethod
    def _exc(window_seconds: int = 60) -> MagicMock:
        """Build a RateLimitExceeded stand-in whose limit lasts ``window_seconds``."""
        exc = MagicMock()
        exc.limit.limit.get_expiry.return_value = window_seconds
        return exc

    def _handle(self, request: MagicMock, exc: MagicMock, response=None) -> JSONResponse:
        """Run the handler with slowapi's own response stubbed."""
        response = response or JSONResponse({"error": "x"}, status_code=429)
        with (
            patch("api.middleware.rate_limit.get_client_ip", return_value="203.0.113.7"),
            patch("api.middleware.rate_limit._rate_limit_exceeded_handler", return_value=response),
            patch("api.middleware.rate_limit.time.time", return_value=1000.0),
        ):
            return rate_limit_handler(request, exc)

    def test_uses_the_window_reset_time_from_the_limiter(self):
        """
        GIVEN a limit whose window closes 12.2 seconds from now
        WHEN rate_limit_handler runs
        THEN Retry-After is that wait rounded up to 13 whole seconds
        """
        limit = MagicMock()
        request = self._request(view_rate_limit=(limit, ["1.2.3.4"]), reset=1012.2)

        response = self._handle(request, self._exc())

        assert response.headers["Retry-After"] == "13"
        request.app.state.limiter.limiter.get_window_stats.assert_called_once_with(limit, "1.2.3.4")

    def test_waits_at_least_one_second(self):
        """
        GIVEN a window that has already closed by the time the handler reads it
        WHEN rate_limit_handler runs
        THEN Retry-After is 1, never zero or negative
        """
        request = self._request(view_rate_limit=(MagicMock(), ["k"]), reset=990.0)

        response = self._handle(request, self._exc())

        assert response.headers["Retry-After"] == "1"

    def test_falls_back_to_the_limit_window_without_a_recorded_limit(self):
        """
        GIVEN no view_rate_limit on the request
        WHEN rate_limit_handler runs
        THEN Retry-After is the full length of the limit's window
        """
        request = self._request(view_rate_limit=None)

        response = self._handle(request, self._exc(window_seconds=60))

        assert response.headers["Retry-After"] == "60"
        request.app.state.limiter.limiter.get_window_stats.assert_not_called()

    def test_falls_back_to_the_limit_window_when_the_stats_call_fails(self):
        """
        GIVEN a store that raises when asked for the window stats
        WHEN rate_limit_handler runs
        THEN Retry-After is the full length of the limit's window
        """
        request = self._request(
            view_rate_limit=(MagicMock(), ["k"]), reset=RuntimeError("store down")
        )

        response = self._handle(request, self._exc(window_seconds=3600))

        assert response.headers["Retry-After"] == "3600"

    def test_logs_when_the_stats_call_fails(self, caplog):
        """
        GIVEN a store that raises when asked for the window stats
        WHEN rate_limit_handler runs
        THEN a WARNING names the event, without the key or the error text in the message
        """
        request = self._request(
            view_rate_limit=(MagicMock(), ["k"]), reset=RuntimeError("store down")
        )

        with caplog.at_level(logging.WARNING, logger="api.ratelimit"):
            self._handle(request, self._exc())

        records = [
            r for r in caplog.records if getattr(r, "event", None) == "rate_limit_window_unreadable"
        ]
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING

    def test_answers_one_second_when_the_exception_has_no_limit(self):
        """
        GIVEN no recorded limit and an exception that carries no limit either
        WHEN rate_limit_handler runs
        THEN Retry-After is 1, the floor, rather than an error
        """
        request = self._request(view_rate_limit=None)
        exc = MagicMock()
        exc.limit = None

        response = self._handle(request, exc)

        assert response.headers["Retry-After"] == "1"

    def test_a_real_limiter_answers_the_third_request_with_a_wait(self):
        """
        GIVEN a real in-memory limiter allowing 2 requests per 10 seconds
        WHEN a client sends three requests through SlowAPIMiddleware
        THEN the third is 429 with an integer Retry-After between 1 and 10
        """

        # GIVEN
        def key(request: Request) -> str:
            return "test-client"

        app = FastAPI()
        app.state.limiter = Limiter(key_func=key, default_limits=["2/10 seconds"], enabled=True)
        app.add_exception_handler(RateLimitExceeded, rate_limit_handler)  # type: ignore[arg-type]
        app.add_middleware(SlowAPIMiddleware)

        @app.get("/ping")
        def ping() -> dict[str, str]:
            return {}

        client = TestClient(app)

        # WHEN
        statuses = [client.get("/ping").status_code for _ in range(2)]
        third = client.get("/ping")

        # THEN
        assert statuses == [200, 200]
        assert third.status_code == 429
        assert 1 <= int(third.headers["Retry-After"]) <= 10

    def test_keeps_a_retry_after_slowapi_already_set(self):
        """
        GIVEN a slowapi response that already carries Retry-After
        WHEN rate_limit_handler runs
        THEN that value is left alone
        """
        existing = JSONResponse({"error": "x"}, status_code=429, headers={"Retry-After": "7"})
        request = self._request(view_rate_limit=(MagicMock(), ["k"]), reset=1500.0)

        response = self._handle(request, self._exc(), existing)

        assert response.headers["Retry-After"] == "7"
        request.app.state.limiter.limiter.get_window_stats.assert_not_called()


class TestRateLimitWiring:
    """Tests that the app factory wires the logging rate-limit handler."""

    def test_app_registers_logging_rate_limit_handler(self):
        """
        GIVEN the full application
        WHEN it is created
        THEN RateLimitExceeded is handled by rate_limit_handler
        """
        # GIVEN
        from slowapi.errors import RateLimitExceeded

        from api.main import create_app

        # WHEN
        app = create_app()

        # THEN
        assert app.exception_handlers[RateLimitExceeded] is rate_limit_handler

    def test_app_registers_slowapi_middleware(self):
        """
        GIVEN the full application
        WHEN it is created
        THEN SlowAPIMiddleware is installed so default_limits apply to every route
        """
        # GIVEN
        from slowapi.middleware import SlowAPIMiddleware

        from api.main import create_app

        # WHEN
        app = create_app()

        # THEN
        assert any(middleware.cls is SlowAPIMiddleware for middleware in app.user_middleware)


class TestBuildLimiter:
    """Tests that build_limiter wires the storage backend and fail-open flag."""

    def test_uses_redis_storage_when_configured(self):
        """
        GIVEN settings with a redis_url
        WHEN build_limiter runs
        THEN the limiter uses that storage URI and swallows storage errors (fail-open)
        """
        settings = SimpleNamespace(testing=False, redis_url="redis://localhost:6379/0")
        limiter = build_limiter(settings)
        assert limiter._storage_uri == "redis://localhost:6379/0"
        assert limiter._swallow_errors is True

    def test_no_storage_uri_without_redis(self):
        """
        GIVEN settings without a redis_url
        WHEN build_limiter runs
        THEN no storage URI is set (slowapi defaults to in-memory) and it still fails open
        """
        settings = SimpleNamespace(testing=True, redis_url="")
        limiter = build_limiter(settings)
        assert limiter._storage_uri is None
        assert limiter._swallow_errors is True

    def test_applies_a_global_default_limit(self):
        """
        GIVEN any settings
        WHEN build_limiter runs
        THEN a non-empty default limit is configured so no route is left unthrottled
        """
        settings = SimpleNamespace(testing=False, redis_url="redis://localhost:6379/0")
        limiter = build_limiter(settings)
        assert limiter._default_limits

    def test_enables_in_memory_fallback(self):
        """
        GIVEN settings with a redis_url
        WHEN build_limiter runs
        THEN in-memory fallback is enabled so a Redis outage still enforces a limit
        rather than letting every request through unthrottled
        """
        settings = SimpleNamespace(testing=False, redis_url="redis://localhost:6379/0")
        limiter = build_limiter(settings)
        assert limiter._in_memory_fallback_enabled is True
