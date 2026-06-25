"""Tests for request/response logging middleware."""

import logging
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.logging_context import get_request_id
from api.middleware.request_logging import RequestLoggingMiddleware


@pytest.fixture
def app() -> FastAPI:
    """Minimal app wired with the request logging middleware."""
    application = FastAPI()
    application.add_middleware(RequestLoggingMiddleware)

    @application.get("/ping")
    def ping():
        return {"ok": True}

    @application.get("/whoami")
    def whoami(request: Request):
        return {"request_id": request.state.request_id}

    @application.get("/ctx")
    def ctx():
        return {"request_id": get_request_id()}

    @application.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Test client for the middleware app."""
    return TestClient(app)


class TestRequestId:
    """Tests for request ID generation and propagation."""

    def test_adds_request_id_response_header(self, client: TestClient):
        """
        GIVEN a request without a request ID
        WHEN it is handled
        THEN the response carries a non-empty X-Request-ID header
        """
        # WHEN
        response = client.get("/ping")

        # THEN
        assert response.headers.get("X-Request-ID")

    def test_preserves_client_supplied_request_id(self, client: TestClient):
        """
        GIVEN a request carrying an X-Request-ID header
        WHEN it is handled
        THEN the same ID is echoed back
        """
        # WHEN
        response = client.get("/ping", headers={"X-Request-ID": "client-123"})

        # THEN
        assert response.headers["X-Request-ID"] == "client-123"

    def test_exposes_request_id_on_request_state(self, client: TestClient):
        """
        GIVEN a request
        WHEN the endpoint reads request.state.request_id
        THEN it matches the response header
        """
        # WHEN
        response = client.get("/whoami")

        # THEN
        assert response.json()["request_id"] == response.headers["X-Request-ID"]

    def test_binds_request_id_to_logging_context(self, client: TestClient):
        """
        GIVEN a request handled through the middleware
        WHEN the endpoint reads the request ID from the logging context
        THEN it matches the response header, proving the contextvar propagates
        """
        # WHEN
        response = client.get("/ctx")

        # THEN
        assert response.json()["request_id"] == response.headers["X-Request-ID"]


class TestRequestLogging:
    """Tests for request/response log emission."""

    def test_logs_incoming_request_with_context(self, client: TestClient):
        """
        GIVEN a request to a normal endpoint
        WHEN it is handled
        THEN an INFO log carries request_id, method and path
        """
        # WHEN
        with patch("api.middleware.request_logging.logger") as mock_logger:
            client.get("/ping")

        # THEN
        mock_logger.info.assert_called_once()
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["method"] == "GET"
        assert extra["path"] == "/ping"
        assert extra["request_id"]

    def test_logs_response_with_status_and_duration(self, client: TestClient):
        """
        GIVEN a completed request
        WHEN the response is returned
        THEN a log carries the status code and duration
        """
        # WHEN
        with patch("api.middleware.request_logging.logger") as mock_logger:
            client.get("/ping")

        # THEN
        extra = mock_logger.log.call_args[1]["extra"]
        assert extra["status_code"] == 200
        assert "duration_ms" in extra

    def test_skips_health_endpoint(self, client: TestClient):
        """
        GIVEN a request to the health endpoint
        WHEN it is handled
        THEN no request/response logs are emitted
        """
        # WHEN
        with patch("api.middleware.request_logging.logger") as mock_logger:
            client.get("/api/v1/health")

        # THEN
        mock_logger.info.assert_not_called()
        mock_logger.log.assert_not_called()

    def test_warns_on_slow_request(self, client: TestClient):
        """
        GIVEN a request slower than the slow-request threshold
        WHEN the response is logged
        THEN the response log is emitted at WARNING level
        """
        # WHEN
        with (
            patch(
                "api.middleware.request_logging.perf_counter",
                side_effect=[0.0, 2.0],
            ),
            patch("api.middleware.request_logging.logger") as mock_logger,
        ):
            client.get("/ping")

        # THEN
        assert mock_logger.log.call_args[0][0] == logging.WARNING

    def test_does_not_log_authorization_header(self, client: TestClient):
        """
        GIVEN a request with an Authorization header
        WHEN it is logged
        THEN the header value never appears in the log context
        """
        # WHEN
        with patch("api.middleware.request_logging.logger") as mock_logger:
            client.get("/ping", headers={"Authorization": "Bearer super-secret-token"})

        # THEN
        serialized = str(mock_logger.info.call_args) + str(mock_logger.log.call_args)
        assert "super-secret-token" not in serialized
