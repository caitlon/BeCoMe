"""Tests for the request data that reaches the error tracker."""

import hashlib
import json
from collections.abc import Iterator
from typing import Any

import fakeredis
import pytest
import sentry_sdk
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from api.auth.login_throttle import LOGIN_KEY_PREFIX, RedisLoginThrottle
from api.dependencies import get_email_address_policy, get_registration_service
from api.sentry_filter import ALLOWED_REQUEST_HEADERS, scrub_request_data

# Not a credential: the host is unroutable and the key is a literal placeholder.
_FAKE_DSN = "https://public@o0.ingest.sentry.io/0"
_ORIGIN = "https://app.example.com"
# A placeholder for the origin-verify value that makes the app trust ``CF-Connecting-IP``.
_FAKE_ORIGIN_VERIFY = "fake-origin-verify-value-0123456789abcdef"  # pragma: allowlist secret
_CLIENT_ADDRESS = "203.0.113.77"

# Obviously fake values for headers outside the allowlist, a cookie and a request body.
_SENTINEL_HEADERS = {
    "X-Origin-Verify": "sentinel-origin-value",
    "CF-Connecting-IP": "203.0.113.77",
    "X-CSRF-Token": "sentinel-csrf-value",
    "Authorization": "Bearer sentinel-bearer-value",
    "X-Custom": "sentinel-custom-value",
}
_SENTINEL_COOKIE = "sentinel-cookie-value"
_SENTINEL_QUERY = "sentinel-query-value"
_SENTINEL_BODY_EMAIL = "sentinel-body@example.com"
_SENTINEL_BODY_NAME = "SentinelBodyName"
_SENTINELS = (
    *_SENTINEL_HEADERS.values(),
    "203.0.113.77",
    _SENTINEL_COOKIE,
    _SENTINEL_QUERY,
    _SENTINEL_BODY_EMAIL,
    _SENTINEL_BODY_NAME,
)


class _KeepEnvelopes(Transport):
    """A transport that keeps every envelope instead of sending it."""

    def __init__(self) -> None:
        super().__init__()
        self.envelopes: list[Any] = []

    def capture_envelope(self, envelope: Any) -> None:
        self.envelopes.append(envelope)

    def items(self, item_type: str) -> list[dict[str, Any]]:
        """Return the payloads of every envelope item of one type."""
        return [
            item.payload.json
            for envelope in self.envelopes
            for item in envelope.items
            if item.type == item_type
        ]

    def serialized(self) -> str:
        """Return every envelope payload as one string."""
        return json.dumps(
            [item.payload.json for envelope in self.envelopes for item in envelope.items],
            default=str,
        )


class _FailingRegistration:
    """A registration service that fails the way an unexpected fault would."""

    def register(self, **_: object) -> None:
        raise RuntimeError("registration failed")


@pytest.fixture
def transport() -> Iterator[_KeepEnvelopes]:
    """The capturing transport; the SDK client is reset afterwards."""
    keep = _KeepEnvelopes()
    try:
        yield keep
    finally:
        sentry_sdk.get_global_scope().set_client(None)


def _build_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    keep: _KeepEnvelopes,
    traces: float,
    origin_verify: str = "",
) -> TestClient:
    """Build the real app with Sentry on, sending to ``keep`` and sampling at ``traces``.

    A non-empty ``origin_verify`` is configured as the origin secret, so a request that
    carries it is trusted to have a real client address.
    """
    from api.config import get_settings
    from api.main import create_app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("SECRET_KEY", "a-sufficiently-strong-secret-value")
    monkeypatch.setenv("CORS_ORIGINS", f'["{_ORIGIN}"]')
    monkeypatch.setenv("SENTRY_DSN", _FAKE_DSN)
    if origin_verify:
        monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", origin_verify)
    get_settings.cache_clear()
    real_init = sentry_sdk.init

    def init_with_transport(**kwargs: Any) -> None:
        kwargs["transport"] = keep
        kwargs["traces_sample_rate"] = traces
        real_init(**kwargs)

    monkeypatch.setattr("api.main.sentry_sdk.init", init_with_transport)
    app = create_app()
    app.dependency_overrides[get_registration_service] = _FailingRegistration
    app.dependency_overrides[get_email_address_policy] = _AcceptingPolicy
    return TestClient(app, raise_server_exceptions=False)


class _AcceptingPolicy:
    """An address policy that accepts every address, so no DNS lookup happens."""

    async def check(self, email: str) -> None:
        return None


def _request_headers() -> dict[str, str]:
    return {
        "Origin": _ORIGIN,
        "Content-Type": "application/json",
        "Cookie": f"session={_SENTINEL_COOKIE}",
        **_SENTINEL_HEADERS,
    }


def _assert_only_allowed(headers: dict[str, str]) -> None:
    assert headers
    assert {name.lower() for name in headers} <= ALLOWED_REQUEST_HEADERS


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    from api.config import get_settings

    yield
    get_settings.cache_clear()


class TestErrorEventRequestData:
    """An error event carries only the allowlisted request data."""

    def test_unhandled_error_event_carries_no_body_cookies_or_extra_headers(
        self, monkeypatch, tmp_path, transport
    ):
        """
        GIVEN the real app with Sentry on and a route that takes a JSON body and fails
        WHEN a request with extra headers, a cookie and a query string reaches it
        THEN the event has no body, cookies, environment or query string
        AND its headers are within the allowlist
        AND no sentinel value appears anywhere in the envelopes
        """
        client = _build_client(monkeypatch, tmp_path, transport, traces=0.0)
        body = {
            "email": _SENTINEL_BODY_EMAIL,
            "password": "Sentinel-Passw0rd-123",  # pragma: allowlist secret
            "first_name": _SENTINEL_BODY_NAME,
            "last_name": "Person",
        }

        response = client.post(
            f"/api/v1/auth/register?probe={_SENTINEL_QUERY}",
            json=body,
            headers=_request_headers(),
        )
        sentry_sdk.flush()

        assert response.status_code == 500
        events = transport.items("event")
        assert len(events) == 1
        request = events[0]["request"]
        assert not {"data", "cookies", "env", "query_string"} & request.keys()
        _assert_only_allowed(request["headers"])
        serialized = transport.serialized()
        for sentinel in (*_SENTINELS, "Sentinel-Passw0rd-123"):
            assert sentinel not in serialized


class TestLogRecordFields:
    """The client address a log record carries stays out of breadcrumbs and extras."""

    def test_trusted_client_address_is_absent_from_the_envelopes(
        self, monkeypatch, tmp_path, transport
    ):
        """
        GIVEN the real app with Sentry on and an origin secret configured
        WHEN a request that carries the secret and a client address fails unhandled
        THEN the request log record reaches the event as a breadcrumb without the address
        AND the address appears nowhere in the envelopes
        """
        client = _build_client(
            monkeypatch, tmp_path, transport, traces=0.0, origin_verify=_FAKE_ORIGIN_VERIFY
        )
        headers = {
            "Origin": _ORIGIN,
            "Content-Type": "application/json",
            "X-Origin-Verify": _FAKE_ORIGIN_VERIFY,
            "CF-Connecting-IP": _CLIENT_ADDRESS,
        }

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "person@example.com",
                "password": "Sentinel-Passw0rd-123",  # pragma: allowlist secret
                "first_name": "Given",
                "last_name": "Person",
            },
            headers=headers,
        )
        sentry_sdk.flush()

        assert response.status_code == 500
        events = transport.items("event")
        assert len(events) == 1
        crumbs = events[0]["breadcrumbs"]["values"]
        assert any(crumb.get("data", {}).get("event") == "request_received" for crumb in crumbs)
        assert _CLIENT_ADDRESS not in transport.serialized()


class TestTransactionRequestData:
    """A sampled transaction carries only the allowlisted request data."""

    def test_sampled_transaction_headers_are_within_the_allowlist(
        self, monkeypatch, tmp_path, transport
    ):
        """
        GIVEN the real app with Sentry on and every request sampled
        WHEN an ordinary request carries extra headers, a cookie and a query string
        THEN the transaction's headers are within the allowlist
        AND no sentinel value appears anywhere in the envelopes
        """
        client = _build_client(monkeypatch, tmp_path, transport, traces=1.0)

        response = client.get(f"/api/v1/health?probe={_SENTINEL_QUERY}", headers=_request_headers())
        sentry_sdk.flush()

        assert response.status_code == 200
        transactions = transport.items("transaction")
        assert len(transactions) == 1
        request = transactions[0]["request"]
        assert not {"data", "cookies", "env", "query_string"} & request.keys()
        _assert_only_allowed(request["headers"])
        serialized = transport.serialized()
        for sentinel in _SENTINELS:
            assert sentinel not in serialized


class TestRedisCommands:
    """Redis commands, and the keys in them, stay out of breadcrumbs and spans."""

    def test_a_throttle_call_leaves_no_key_in_the_envelopes(self, monkeypatch, tmp_path, transport):
        """
        GIVEN the real app with Sentry on and every request sampled
        WHEN a login throttle works against Redis inside a transaction that then errors
        THEN no envelope holds the throttle's key prefix or the digest of the identifier
        """
        _build_client(monkeypatch, tmp_path, transport, traces=1.0)
        throttle = RedisLoginThrottle(
            fakeredis.FakeStrictRedis(), key_prefix=LOGIN_KEY_PREFIX, max_failures=3
        )
        digest = hashlib.sha256(b"person@example.com").hexdigest()

        with sentry_sdk.start_transaction(name="redis-probe"):
            throttle.reserve("person@example.com")
            throttle.confirm_failure("person@example.com")
            sentry_sdk.capture_message("probe")
        sentry_sdk.flush()

        assert transport.items("event")
        assert transport.items("transaction")
        serialized = transport.serialized()
        assert f"{LOGIN_KEY_PREFIX}:fail:" not in serialized
        assert digest not in serialized


class TestScrubRequestData:
    """The filter function itself."""

    def test_keeps_allowlisted_headers_whatever_their_case(self):
        """
        GIVEN an event whose headers mix allowed and other names in several cases
        WHEN the filter runs
        THEN only the allowed names remain, with their values
        """
        event: Any = {
            "request": {
                "headers": {
                    "Host": "api.example.com",
                    "ACCEPT": "application/json",
                    "content-type": "application/json",
                    "Content-Length": "12",
                    "X-Custom": "value",
                    "Authorization": "value",
                }
            }
        }

        result = scrub_request_data(event, {})

        assert result["request"]["headers"] == {
            "Host": "api.example.com",
            "ACCEPT": "application/json",
            "content-type": "application/json",
            "Content-Length": "12",
        }

    def test_removes_body_cookies_environment_and_query_string(self):
        """
        GIVEN an event with a request that has all four fields
        WHEN the filter runs
        THEN they are gone and the rest of the request stays
        """
        event: Any = {
            "request": {
                "url": "https://api.example.com/path",
                "method": "POST",
                "headers": {},
                "cookies": {"a": "b"},
                "data": {"a": "b"},
                "env": {"REMOTE_ADDR": "203.0.113.77"},
                "query_string": "a=b",
            }
        }

        result = scrub_request_data(event, {})

        assert result["request"] == {
            "url": "https://api.example.com/path",
            "method": "POST",
            "headers": {},
        }

    def test_removes_the_client_address_and_keeps_the_rest_of_the_user(self):
        """
        GIVEN an event whose user has an address and an id
        WHEN the filter runs
        THEN the user keeps the id only
        """
        event: Any = {"user": {"id": "user-1", "ip_address": "203.0.113.77"}}

        result = scrub_request_data(event, {})

        assert result["user"] == {"id": "user-1"}

    def test_passes_an_event_without_a_request_unchanged(self):
        """
        GIVEN an event with no request and no user
        WHEN the filter runs
        THEN it is returned as it was
        """
        event: Any = {"message": "hello"}

        assert scrub_request_data(event, {}) == {"message": "hello"}

    @pytest.mark.parametrize(
        "event",
        [
            {"request": None, "user": None},
            {"request": "text", "user": ["a"]},
            {"request": {"headers": None}},
            {"request": {"headers": [("x-custom", "value")]}},
            {"request": {"headers": {1: "value", None: "value"}}},
        ],
        ids=["none", "text-and-list", "headers-none", "headers-list", "headers-odd-keys"],
    )
    def test_never_raises_on_unexpected_types(self, event):
        """
        GIVEN an event whose request, user or headers have unexpected types
        WHEN the filter runs
        THEN it returns the event without raising
        AND no header of an unreadable shape is kept
        """
        result = scrub_request_data(event, {})

        assert result is event
        request = result.get("request")
        if isinstance(request, dict):
            assert not request.get("headers")


class TestScrubLogRecordFields:
    """The filter removes ``ip`` from breadcrumb data and event extras."""

    def test_removes_the_address_from_breadcrumb_data_in_the_sdk_shape(self):
        """
        GIVEN an event whose breadcrumbs are the SDK's ``{"values": [...]}`` mapping
        WHEN the filter runs
        THEN every breadcrumb keeps its other fields and loses ``ip``
        """
        event: Any = {
            "breadcrumbs": {
                "values": [
                    {"category": "api", "data": {"event": "request_received", "ip": "x"}},
                    {"category": "api", "data": {"ip": "y", "path": "/p"}},
                    {"category": "query", "message": "no data"},
                ]
            }
        }

        result = scrub_request_data(event, {})

        assert result["breadcrumbs"]["values"] == [
            {"category": "api", "data": {"event": "request_received"}},
            {"category": "api", "data": {"path": "/p"}},
            {"category": "query", "message": "no data"},
        ]

    def test_removes_the_address_from_a_bare_list_of_breadcrumbs(self):
        """
        GIVEN an event whose breadcrumbs are a plain list
        WHEN the filter runs
        THEN the address is removed from each breadcrumb's data
        """
        event: Any = {"breadcrumbs": [{"data": {"ip": "x", "event": "e"}}]}

        result = scrub_request_data(event, {})

        assert result["breadcrumbs"] == [{"data": {"event": "e"}}]

    def test_removes_the_address_from_event_extra(self):
        """
        GIVEN an event whose extra holds the fields of an error log record
        WHEN the filter runs
        THEN ``ip`` is gone and the other fields stay
        """
        event: Any = {"extra": {"ip": "x", "event": "unhandled_exception", "request_id": "r"}}

        result = scrub_request_data(event, {})

        assert result["extra"] == {"event": "unhandled_exception", "request_id": "r"}

    @pytest.mark.parametrize(
        "event",
        [
            {"breadcrumbs": None, "extra": None},
            {"breadcrumbs": "text", "extra": "text"},
            {"breadcrumbs": {"values": None}},
            {"breadcrumbs": {"values": "text"}},
            {"breadcrumbs": {"values": [None, "text", 3, {"data": None}, {"data": "text"}]}},
            {"breadcrumbs": [None, {"data": ["ip"]}], "extra": ["ip"]},
            {"breadcrumbs": {"other": [{"data": {"ip": "x"}}]}},
        ],
        ids=[
            "none",
            "text",
            "values-none",
            "values-text",
            "values-odd-items",
            "list-odd-items",
            "no-values-key",
        ],
    )
    def test_never_raises_on_unexpected_shapes(self, event):
        """
        GIVEN an event whose breadcrumbs or extra have unexpected shapes
        WHEN the filter runs
        THEN it returns the event without raising
        """
        assert scrub_request_data(event, {}) is event
