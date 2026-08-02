"""Tests that refusals, external calls, and reads emit the log records they promise.

Grouped by the layer that emits them rather than by module, because the point of each
record is the question it answers for whoever reads the drain -- "was the request
refused, and why" -- not which file happens to raise it.

Several of these assert on what is *absent*: a CSRF record must not carry the token it
just compared, a throttle record must not carry the account it throttled. Those are the
assertions worth keeping when the code around them changes.
"""

import logging
from time import perf_counter
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest
import redis
from starlette.requests import Request

from api.auth import cookies, email_throttle, login_throttle, revocation_store
from api.auth import jwt as jwt_module
from api.middleware.body_size import RequestBodyTooLarge, body_too_large_handler
from api.middleware.csrf import CSRFMiddleware
from api.routes import invitations as invitations_route
from api.routes import users as users_route
from api.services import project_query_service, registration_service
from api.services.email import resend_email_sender


def _request(method: str = "POST", path: str = "/api/v1/projects") -> Request:
    """Build a minimal request the middleware helpers can read."""
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("203.0.113.5", 51234),
            "headers": [],
        }
    )


def _extras(mock_call) -> dict:
    """Return the ``extra`` dict of a mocked logger call."""
    return mock_call[1]["extra"]


class TestCsrfRejectionLogging:
    """A refused CSRF check is logged, without the token it compared."""

    @pytest.mark.parametrize("reason", ["missing_header", "token_mismatch"])
    def test_rejection_logs_event_and_reason(self, reason):
        """
        GIVEN a request the CSRF check refuses
        WHEN the refusal is built
        THEN a csrf_rejected warning names the reason, method, and path
        """
        # GIVEN
        request = _request(method="DELETE", path="/api/v1/projects/abc")

        # WHEN
        with patch("api.middleware.csrf.logger") as mock_logger:
            response = CSRFMiddleware._reject(reason, request)

        # THEN
        extra = _extras(mock_logger.warning.call_args)
        assert extra["event"] == "csrf_rejected"
        assert extra["reason"] == reason
        assert extra["method"] == "DELETE"
        assert extra["path"] == "/api/v1/projects/abc"
        assert response.status_code == 403

    def test_rejection_does_not_log_the_token(self):
        """
        GIVEN a CSRF refusal
        WHEN the record is built
        THEN no field carries a token value

        The cookie and header are the secret being compared: a record carrying either
        hands a log reader what they need to forge the request that was just blocked.
        """
        # GIVEN / WHEN
        with patch("api.middleware.csrf.logger") as mock_logger:
            CSRFMiddleware._reject("token_mismatch", _request())

        # THEN
        assert set(_extras(mock_logger.warning.call_args)) == {
            "event",
            "reason",
            "method",
            "path",
            "ip",
        }


class TestBodySizeRejectionLogging:
    """An over-large body is logged whichever way it was caught."""

    def test_streamed_overflow_logs_event(self):
        """
        GIVEN a body that streamed past the cap
        WHEN the handler answers 413
        THEN a request_body_rejected warning names the streamed_overflow reason
        """
        # GIVEN
        request = _request(method="POST", path="/api/v1/calculate")

        # WHEN
        with patch("api.middleware.body_size.logger") as mock_logger:
            response = body_too_large_handler(request, RequestBodyTooLarge())

        # THEN
        extra = _extras(mock_logger.warning.call_args)
        assert extra["event"] == "request_body_rejected"
        assert extra["reason"] == "streamed_overflow"
        assert extra["path"] == "/api/v1/calculate"
        assert response.status_code == 413


class TestTokenRejectionLogging:
    """Token refusals split by level: routine traffic at DEBUG, signal at WARNING."""

    @pytest.mark.parametrize("reason", ["invalid_or_expired", "invalid_user_id"])
    def test_routine_refusals_are_debug(self, reason):
        """
        GIVEN an expired or malformed token
        WHEN it is refused
        THEN the record is DEBUG

        Every active session hits this every 15 minutes and every stale browser tab
        hits it too; at WARNING it would bury the refusals that mean something.
        """
        # GIVEN / WHEN
        with patch("api.auth.jwt.logger") as mock_logger:
            error = jwt_module._reject(reason, "nope", expected_type="access")

        # THEN
        assert mock_logger.log.call_args[0][0] == logging.DEBUG
        assert isinstance(error, jwt_module.TokenError)

    @pytest.mark.parametrize(
        "reason",
        ["jti_revoked", "session_revoked", "store_unavailable", "issued_before_valid_after"],
    )
    def test_meaningful_refusals_are_warning(self, reason):
        """
        GIVEN a revoked token or an unreachable store
        WHEN it is refused
        THEN the record is WARNING
        """
        # GIVEN / WHEN
        with patch("api.auth.jwt.logger") as mock_logger:
            jwt_module._reject(reason, "nope", jti="abc123")

        # THEN
        assert mock_logger.log.call_args[0][0] == logging.WARNING
        assert _extras(mock_logger.log.call_args)["event"] == "token_rejected"

    def test_refusal_carries_no_token_string(self):
        """
        GIVEN a refused token
        WHEN the record is built
        THEN only the reason and opaque identifiers are logged
        """
        # GIVEN / WHEN
        with patch("api.auth.jwt.logger") as mock_logger:
            jwt_module._reject("jti_revoked", "nope", jti="abc123")

        # THEN
        assert set(_extras(mock_logger.log.call_args)) == {"event", "reason", "jti"}


class TestCsrfHeaderSuppressionLogging:
    """Refusing to echo a client-chosen CSRF value leaves a trace."""

    def test_non_printable_token_is_logged(self):
        """
        GIVEN a CSRF token carrying a newline
        WHEN set_csrf_header refuses to echo it
        THEN a csrf_header_suppressed warning records the refusal

        That guard blocks a response-splitting primitive and previously left no trace
        whatsoever, so an attempt was indistinguishable from nothing happening.
        """
        # GIVEN
        response = MagicMock()
        response.headers = {}

        # WHEN
        with patch("api.auth.cookies.logger") as mock_logger:
            cookies.set_csrf_header(response, "\nX-Injected: 1")

        # THEN
        extra = _extras(mock_logger.warning.call_args)
        assert extra == {"event": "csrf_header_suppressed", "reason": "non_printable"}
        assert response.headers == {}

    def test_a_clean_token_is_echoed_without_a_warning(self):
        """
        GIVEN a well-formed token
        WHEN set_csrf_header runs
        THEN the header is set and nothing is logged
        """
        # GIVEN
        response = MagicMock()
        response.headers = {}

        # WHEN
        with patch("api.auth.cookies.logger") as mock_logger:
            cookies.set_csrf_header(response, "a-normal-url-safe-token")

        # THEN
        assert response.headers[cookies.CSRF_HEADER] == "a-normal-url-safe-token"
        mock_logger.warning.assert_not_called()


class TestRevocationStoreLogging:
    """A fail-closed store that cannot be reached says so."""

    def test_store_error_logs_the_operation(self):
        """
        GIVEN Redis raising on a revocation lookup
        WHEN the error is built
        THEN a revocation_store_unavailable warning names the operation

        Callers turn this into a plain 401, so without the record a Redis outage is
        indistinguishable from a wave of bad tokens.
        """
        # GIVEN
        exc = redis.RedisError("connection refused")

        # WHEN
        with patch("api.auth.revocation_store.logger") as mock_logger:
            error = revocation_store._store_error("is_jti_revoked", exc)

        # THEN
        extra = _extras(mock_logger.warning.call_args)
        assert extra == {"event": "revocation_store_unavailable", "op": "is_jti_revoked"}
        assert mock_logger.warning.call_args[1]["exc_info"] is exc
        assert isinstance(error, revocation_store.RevocationStoreError)

    def test_backend_selection_is_logged_once(self):
        """
        GIVEN no Redis configured
        WHEN the store is selected
        THEN a revocation_store_selected record names the memory backend
        """
        # GIVEN
        revocation_store.get_revocation_store.cache_clear()

        # WHEN
        with patch("api.auth.revocation_store.logger") as mock_logger:
            store = revocation_store.get_revocation_store()

        # THEN
        extra = _extras(mock_logger.info.call_args)
        assert extra == {"event": "revocation_store_selected", "backend": "memory"}
        assert isinstance(store, revocation_store.InMemoryRevocationStore)
        revocation_store.get_revocation_store.cache_clear()

    def test_call_trace_carries_timing(self):
        """
        GIVEN a completed store round trip
        WHEN it is traced
        THEN the DEBUG record carries the operation and its duration
        """
        # GIVEN / WHEN
        with patch("api.auth.revocation_store.logger") as mock_logger:
            revocation_store._log_call("revoke_session", perf_counter(), sid="s1")

        # THEN
        extra = _extras(mock_logger.debug.call_args)
        assert extra["event"] == "revocation_store_call"
        assert extra["op"] == "revoke_session"
        assert extra["duration_ms"] >= 0


class TestThrottleLogging:
    """Both throttles fail open, so an outage has to be visible."""

    def test_login_throttle_outage_is_logged_without_the_account(self):
        """
        GIVEN Redis raising while the lockout counter is read
        WHEN the failure is recorded
        THEN a throttle_store_unavailable warning names the flow, not the account

        _digest() is an unkeyed SHA-256: logging it would let anyone holding the logs
        confirm an address by hashing a guess.
        """
        # GIVEN
        exc = redis.RedisError("down")

        # WHEN
        with patch("api.auth.login_throttle.logger") as mock_logger:
            login_throttle._log_store_unavailable("is_locked", exc, "login")

        # THEN
        extra = _extras(mock_logger.warning.call_args)
        assert extra == {
            "event": "throttle_store_unavailable",
            "op": "is_locked",
            "key_prefix": "login",
        }

    def test_email_throttle_outage_is_logged_without_the_address(self):
        """
        GIVEN Redis raising while the per-address cap is checked
        WHEN the failure is recorded
        THEN the record names the flow only
        """
        # GIVEN
        exc = redis.RedisError("down")

        # WHEN
        with patch("api.auth.email_throttle.logger") as mock_logger:
            email_throttle._log_store_unavailable("allow", exc, "reset")

        # THEN
        extra = _extras(mock_logger.warning.call_args)
        assert extra == {
            "event": "throttle_store_unavailable",
            "op": "allow",
            "key_prefix": "reset",
        }

    def test_in_memory_denial_logs_without_an_identifier(self):
        """
        GIVEN an address inside its cooldown
        WHEN the in-memory throttle refuses a second send
        THEN an email_throttle_denied record names the reason, not the address
        """
        # GIVEN
        throttle = email_throttle.InMemoryEmailSendThrottle()
        address = "victim@example.com"
        assert throttle.allow(address) is True

        # WHEN
        with patch("api.auth.email_throttle.logger") as mock_logger:
            allowed = throttle.allow(address)

        # THEN
        assert allowed is False
        extra = _extras(mock_logger.debug.call_args)
        assert extra["event"] == "email_throttle_denied"
        assert extra["reason"] == "cooldown"
        assert address not in str(mock_logger.debug.call_args)
        assert email_throttle._digest(address) not in str(mock_logger.debug.call_args)


class TestEmailSenderLogging:
    """The provider call is traced, and its failure stays below ERROR."""

    def test_success_logs_status_and_timing(self):
        """
        GIVEN a provider call that returned 200
        WHEN the outcome is recorded
        THEN an email_sent record carries the status, timing, and keyed address tag
        """
        # GIVEN / WHEN
        with patch("api.services.email.resend_email_sender.logger") as mock_logger:
            resend_email_sender._log_send_result(
                "password_reset", "abcdef0123456789", start=perf_counter(), status_code=200
            )

        # THEN
        extra = _extras(mock_logger.info.call_args)
        assert extra["event"] == "email_sent"
        assert extra["kind"] == "password_reset"
        assert extra["status_code"] == 200
        assert extra["email_hash"] == "abcdef0123456789"

    def test_failure_is_warning_not_error(self):
        """
        GIVEN a provider call that failed
        WHEN the outcome is recorded
        THEN it is a WARNING and never an ERROR

        api/routes/auth.py already logs the swallowed EmailSendError at ERROR so Sentry
        raises exactly one issue per outage; a second ERROR here would double them.
        """
        # GIVEN
        exc = httpx.ConnectError("no route to host")

        # WHEN
        with patch("api.services.email.resend_email_sender.logger") as mock_logger:
            resend_email_sender._log_send_result(
                "verification", "abcdef0123456789", start=perf_counter(), exc=exc
            )

        # THEN
        assert _extras(mock_logger.warning.call_args)["event"] == "email_send_failed"
        mock_logger.error.assert_not_called()

    def test_failure_records_the_provider_status_when_there_is_one(self):
        """
        GIVEN a provider that answered 422
        WHEN the failure is recorded
        THEN the status reaches the record
        """
        # GIVEN
        response = httpx.Response(422, request=httpx.Request("POST", "https://api.resend.com"))
        exc = httpx.HTTPStatusError("rejected", request=response.request, response=response)

        # WHEN
        with patch("api.services.email.resend_email_sender.logger") as mock_logger:
            resend_email_sender._log_send_result(
                "registration_notice", "abcdef0123456789", start=perf_counter(), exc=exc
            )

        # THEN
        assert _extras(mock_logger.warning.call_args)["status_code"] == 422


class TestRegistrationLogging:
    """The registration branch is traced without making it joinable to an address."""

    @pytest.mark.parametrize("branch", ["created", "pending_unverified", "already_verified"])
    def test_branch_is_debug_and_anonymous(self, branch):
        """
        GIVEN a registration submission
        WHEN its branch is traced
        THEN the DEBUG record names the branch and nothing about the address
        """
        # GIVEN / WHEN
        with patch("api.services.registration_service.logger") as mock_logger:
            registration_service._log_branch(branch)

        # THEN
        assert _extras(mock_logger.debug.call_args) == {
            "event": "registration_branch",
            "branch": branch,
        }


class TestProjectQueryLogging:
    """Reads are traced by shape and timing, never by statement."""

    def test_query_trace_carries_shape_and_timing(self):
        """
        GIVEN a completed project query
        WHEN it is traced
        THEN the DEBUG record carries the variant, row count, and duration
        """
        # GIVEN
        user_id = uuid4()

        # WHEN
        with patch("api.services.project_query_service.logger") as mock_logger:
            project_query_service._log_query(
                "with_roles", user_id, 7, perf_counter(), limit=20, offset=0
            )

        # THEN
        extra = _extras(mock_logger.debug.call_args)
        assert extra["event"] == "user_projects_queried"
        assert extra["variant"] == "with_roles"
        assert extra["row_count"] == 7
        assert extra["user_id"] == str(user_id)
        assert extra["duration_ms"] >= 0


class TestRouteRefusalLogging:
    """Route-level refusals are raised as HTTPException, so they log here or nowhere."""

    def test_invitation_rejection_tags_the_address(self):
        """
        GIVEN an invitation for an address with no account
        WHEN the refusal is logged
        THEN the address is a keyed tag, never the address itself

        This endpoint is the application's email-enumeration surface, so a log of the
        addresses people probed for would be the registry the rate limit denies them.
        """
        # GIVEN
        project_id, inviter_id = uuid4(), uuid4()
        address = "stranger@example.com"

        # WHEN
        with patch("api.routes.invitations.logger") as mock_logger:
            invitations_route._log_invitation_rejected(
                "invitee_not_found", project_id, inviter_id, address
            )

        # THEN
        extra = _extras(mock_logger.warning.call_args)
        assert extra["event"] == "invitation_rejected"
        assert extra["reason"] == "invitee_not_found"
        assert extra["project_id"] == str(project_id)
        assert address not in str(mock_logger.warning.call_args)
        assert len(extra["email_hash"]) == 16

    @pytest.mark.parametrize(
        "reason", ["storage_unavailable", "content_type", "too_large", "content_mismatch"]
    )
    def test_photo_upload_rejections_are_logged(self, reason):
        """
        GIVEN a photo upload refused by one of the validation gates
        WHEN the refusal is logged
        THEN a photo_upload_rejected warning names which gate refused it
        """
        # GIVEN
        user_id = uuid4()

        # WHEN
        with patch("api.routes.users.logger") as mock_logger:
            users_route._photo_upload_rejected(reason, user_id)

        # THEN
        extra = _extras(mock_logger.warning.call_args)
        assert extra["event"] == "photo_upload_rejected"
        assert extra["reason"] == reason
        assert extra["user_id"] == str(user_id)

    def test_photo_not_found_is_debug(self):
        """
        GIVEN the public photo proxy answering 404
        WHEN the miss is logged
        THEN it is DEBUG

        The endpoint is public and fires on every avatar render, so a missing photo is
        ordinary traffic rather than a signal.
        """
        # GIVEN
        user_id = uuid4()

        # WHEN
        with patch("api.routes.users.logger") as mock_logger:
            users_route._photo_not_found("object_missing", user_id)

        # THEN
        extra = _extras(mock_logger.debug.call_args)
        assert extra["event"] == "photo_not_found"
        assert extra["reason"] == "object_missing"
