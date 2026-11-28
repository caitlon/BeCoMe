"""Tests for the request data that reaches the error tracker."""

import hashlib
import io
import json
import logging
import sys
from collections.abc import Callable, Iterator
from typing import Any

import fakeredis
import pytest
import sentry_sdk
from fastapi.testclient import TestClient
from sentry_sdk.utils import event_from_exception

from api.auth.login_throttle import LOGIN_KEY_PREFIX, RedisLoginThrottle
from api.db.error_text import exception_chain
from api.dependencies import get_email_address_policy, get_registration_service
from api.sentry_filter import ALLOWED_REQUEST_HEADERS, scrub_request_data
from tests.shared.database_errors import (
    CONNECT_NAMES,
    SENTINEL,
    bind_processor_error,
    psycopg2_connection_refused,
    psycopg2_invalid_uuid,
    psycopg2_pg_hba_rejection,
    psycopg2_unique_violation,
    psycopg3_unique_violation,
    raised,
)
from tests.shared.sentry_capture import KeepEnvelopes, capturing_transport

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
    "User-Agent": "sentinel-user-agent-value",
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


class _FailingRegistration:
    """A registration service that fails the way an unexpected fault would."""

    def register(self, **_: object) -> None:
        raise RuntimeError("registration failed")


@pytest.fixture
def transport() -> Iterator[KeepEnvelopes]:
    """The capturing transport, with the SDK set up as in a fresh process."""
    with capturing_transport() as keep:
        yield keep


def _build_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    keep: KeepEnvelopes,
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


class _RaisingDatabaseError:
    """A registration service whose database call fails the way the engine reports it."""

    def __init__(self, build: Callable[[], tuple[Any, BaseException]]) -> None:
        self._build = build

    def register(self, **_: object) -> None:
        wrapped, orig = self._build()
        try:
            raise orig
        except BaseException as cause:
            raise wrapped from cause


def _capture_api_log(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Point the app's own stream handlers at a buffer, so the output of its formatters is read."""
    buffer = io.StringIO()
    for handler in logging.getLogger("api").handlers:
        if isinstance(handler, logging.StreamHandler):
            monkeypatch.setattr(handler, "stream", buffer)
    return buffer


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


class TestDatabaseErrorText:
    """PostgreSQL's own error text stays out of the envelopes and the log output."""

    @staticmethod
    def _register_failing(client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "person@example.com",
                "password": "Sentinel-Passw0rd-123",  # pragma: allowlist secret
                "first_name": "Given",
                "last_name": "Person",
            },
            headers={"Origin": _ORIGIN, "Content-Type": "application/json"},
        )
        sentry_sdk.flush()
        assert response.status_code == 500

    @pytest.mark.parametrize(
        ("build", "wrapper", "driver", "first_line"),
        [
            (
                psycopg2_unique_violation,
                "IntegrityError",
                "UniqueViolation",
                "duplicate key value violates unique constraint",
            ),
            (
                psycopg2_invalid_uuid,
                "DataError",
                "InvalidTextRepresentation",
                "invalid input syntax for type uuid",
            ),
        ],
        ids=["unique-violation", "invalid-uuid"],
    )
    def test_event_and_log_carry_no_quoted_row_value(
        self, monkeypatch, tmp_path, transport, build, wrapper, driver, first_line
    ):
        """
        GIVEN the real app with Sentry on and a route whose database call fails with an error
            whose text quotes a value
        WHEN the request reaches it
        THEN the event still names both exception types and modules and keeps the first line
        AND the value, the DETAIL line and the statement appear in no envelope
        AND the log output of the app's handlers holds none of them either
        """
        client = _build_client(monkeypatch, tmp_path, transport, traces=0.0)
        client.app.dependency_overrides[get_registration_service] = lambda: _RaisingDatabaseError(
            build
        )
        log = _capture_api_log(monkeypatch)

        self._register_failing(client)

        events = transport.items("event")
        assert events
        values = [value for event in events for value in event["exception"]["values"]]
        seen = {(value["module"], value["type"]) for value in values}
        assert {("psycopg2.errors", driver), ("sqlalchemy.exc", wrapper)} <= seen
        assert any(first_line in value["value"] for value in values)
        serialized = transport.serialized()
        output = log.getvalue()
        assert "Unhandled exception" in output
        assert driver in output
        for text in (serialized, output):
            assert SENTINEL not in text
            assert "DETAIL" not in text
            assert "INSERT INTO" not in text

    @pytest.mark.parametrize(
        ("build", "label"),
        [(psycopg2_connection_refused, "refused"), (psycopg2_pg_hba_rejection, "authentication")],
        ids=["refused", "pg-hba-rejection"],
    )
    def test_failed_connection_keeps_its_reason_and_no_name(
        self, monkeypatch, tmp_path, transport, build, label
    ):
        """
        GIVEN the real app with Sentry on and a route whose database call fails to connect,
            the message naming a host, an address, a port, a user and a database
        WHEN the request reaches it
        THEN the event carries the reason label in its text and in the ``db.connection_failure`` tag
        AND no envelope and no log output holds the host, address, port, user or database name
        """
        client = _build_client(monkeypatch, tmp_path, transport, traces=0.0)
        client.app.dependency_overrides[get_registration_service] = lambda: _RaisingDatabaseError(
            build
        )
        log = _capture_api_log(monkeypatch)

        self._register_failing(client)

        events = transport.items("event")
        assert [event["tags"]["db.connection_failure"] for event in events] == [label]
        values = [value["value"] for event in events for value in event["exception"]["values"]]
        assert any(value.endswith(f"(connection failure: {label})") for value in values)
        output = log.getvalue()
        assert f"(connection failure: {label})" in output
        for text in (transport.serialized(), output):
            for name in CONNECT_NAMES:
                assert name not in text


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
        WHEN a login throttle works against Redis inside a transaction that captures a message
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

    def test_allowlist_is_exactly_the_four_reviewed_headers(self):
        """
        GIVEN the set of request headers the tracker may receive
        WHEN it is compared with the reviewed list
        THEN the two are equal, so widening the set means changing this test
        """
        reviewed = frozenset({"host", "accept", "content-type", "content-length"})

        assert reviewed == ALLOWED_REQUEST_HEADERS

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

        result: Any = scrub_request_data(event, {})

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


# The options of the app's Sentry client that the event builder reads; frame locals are off there
# (``include_local_variables=False``), so a test event carries none either.
_EVENT_OPTIONS = {
    "include_local_variables": False,
    "include_source_context": True,
    "max_value_length": 1024,
}


def _event_from(exc_info: Any) -> tuple[Any, Any]:
    return event_from_exception(exc_info, client_options=_EVENT_OPTIONS)


class TestScrubDatabaseErrors:
    """The filter reduces the text of database errors in an event's exception chain."""

    @staticmethod
    def _scrubbed_event(build) -> dict[str, Any]:
        wrapped, orig = build()
        exc_info = raised(wrapped, orig)
        event, hint = _event_from(exc_info)
        assert SENTINEL in json.dumps(event, default=str)
        return scrub_request_data(event, hint)  # type: ignore[return-value]

    def test_psycopg3_unique_violation_keeps_type_sqlstate_and_first_line(self):
        """
        GIVEN an event from a psycopg 3 unique violation wrapped by SQLAlchemy
        WHEN the filter runs
        THEN no value, DETAIL line or statement is left
        AND the entries keep their type, module and stack trace
        AND the SQLSTATE is reported on the driver entry
        """
        event = self._scrubbed_event(psycopg3_unique_violation)

        values = event["exception"]["values"]
        assert [(v["module"], v["type"]) for v in values] == [
            ("psycopg.errors", "UniqueViolation"),
            ("sqlalchemy.exc", "IntegrityError"),
        ]
        assert all(v["stacktrace"]["frames"] for v in values)
        assert SENTINEL not in json.dumps(event, default=str)
        assert "DETAIL" not in json.dumps(event, default=str)
        assert values[0]["value"].endswith("(SQLSTATE 23505)")
        assert values[1]["value"].startswith("(psycopg.errors.UniqueViolation)")

    def test_builtin_error_inside_a_statement_error_is_reduced(self):
        """
        GIVEN an event from a statement error raised from the TypeError of a bind processor
        WHEN the filter runs
        THEN the quoted value is gone from both entries
        """
        event = self._scrubbed_event(bind_processor_error)

        assert SENTINEL not in json.dumps(event, default=str)
        assert event["exception"]["values"][0]["value"] == "Not a boolean value: '***"

    def test_entry_without_a_matching_exception_is_cut_by_its_module(self):
        """
        GIVEN an event with a driver error entry and a hint that names no exception
        WHEN the filter runs
        THEN the entry keeps its first line cut at the first quote mark
        AND an entry of another module is left alone
        """
        event: Any = {
            "exception": {
                "values": [
                    {
                        "type": "UniqueViolation",
                        "module": "psycopg2.errors",
                        "value": f'clash "{SENTINEL}"\nDETAIL: Key (email)=({SENTINEL})',
                    },
                    {"type": "ValueError", "module": "builtins", "value": f'kept "{SENTINEL}"'},
                ]
            }
        }

        result = scrub_request_data(event, {})

        assert result["exception"]["values"][0]["value"] == 'clash "***'
        assert result["exception"]["values"][1]["value"] == f'kept "{SENTINEL}"'

    def test_application_error_raised_from_a_database_error_keeps_its_text(self):
        """
        GIVEN an event from an application error whose cause is a database error
        WHEN the filter runs
        THEN the application error keeps its message and the database errors are reduced
        """
        wrapped, orig = psycopg2_unique_violation()
        database_error = raised(wrapped, orig)[1]
        assert database_error is not None
        event, hint = _event_from(raised(ValueError("signup failed"), database_error))

        result: Any = scrub_request_data(event, hint)

        values = {v["type"]: v["value"] for v in result["exception"]["values"]}
        assert values["ValueError"] == "signup failed"
        assert SENTINEL not in json.dumps(result, default=str)

    def test_database_error_inside_an_exception_group_is_reduced(self):
        """
        GIVEN an event from an exception group whose member is a statement error raised from
            the TypeError of a bind processor
        WHEN the filter runs
        THEN the quoted value is gone from every entry
        AND the chain of the group reaches the member and the TypeError
        """
        wrapped, orig = bind_processor_error()
        member = raised(wrapped, orig)[1]
        assert member is not None
        group = ExceptionGroup("g", [member])
        try:
            raise group
        except ExceptionGroup:
            event, hint = _event_from(sys.exc_info())
        assert SENTINEL in json.dumps(event, default=str)

        result: Any = scrub_request_data(event, hint)

        assert SENTINEL not in json.dumps(result, default=str)
        chain = exception_chain(group)
        assert member in chain
        assert orig in chain

    @pytest.mark.parametrize(
        ("tags", "expected"),
        [
            (None, {"db.connection_failure": "refused"}),
            ({"release": "1"}, {"release": "1", "db.connection_failure": "refused"}),
            ([("release", "1")], [("release", "1")]),
            ("text", "text"),
        ],
        ids=["no-tags", "other-tags", "list", "text"],
    )
    def test_failed_connection_sets_the_tag_unless_the_tags_are_no_dict(self, tags, expected):
        """
        GIVEN an event for a refused connection, whose tags are missing, a dict or another type
        WHEN the filter runs
        THEN the tag ``db.connection_failure`` is set next to the other tags of a dict
        AND tags of another type are not touched
        AND the host of the connection is gone in every case
        """
        event, hint = _event_from(raised(*psycopg2_connection_refused()))
        if tags is not None:
            event["tags"] = tags

        result: Any = scrub_request_data(event, hint)

        assert result["tags"] == expected
        assert CONNECT_NAMES[0] not in json.dumps(result, default=str)

    def test_other_database_errors_and_unpaired_entries_set_no_tag(self):
        """
        GIVEN an event for a unique violation, and one for a refused connection with no hint
        WHEN the filter runs
        THEN neither gets a ``db.connection_failure`` tag
        """
        violation = self._scrubbed_event(psycopg2_unique_violation)
        unpaired, _ = _event_from(raised(*psycopg2_connection_refused()))

        result: Any = scrub_request_data(unpaired, {})

        assert "tags" not in violation
        assert "tags" not in result
        assert CONNECT_NAMES[0] not in json.dumps(result, default=str)

    @pytest.mark.parametrize(
        "event",
        [
            {"exception": None},
            {"exception": "text"},
            {"exception": {"values": None}},
            {"exception": {"values": "text"}},
            {"exception": {"values": [None, "text", 3, {"module": "psycopg2.errors"}]}},
            {"exception": {"values": [{"module": "psycopg2.errors", "value": None}]}},
        ],
        ids=["none", "text", "values-none", "values-text", "odd-items", "value-none"],
    )
    @pytest.mark.parametrize("hint", [{}, {"exc_info": None}, {"exc_info": "text"}, None])
    def test_never_raises_on_unexpected_shapes(self, event, hint):
        """
        GIVEN an event whose exception data, or a hint, has an unexpected shape
        WHEN the filter runs
        THEN it returns the event without raising
        """
        assert scrub_request_data(event, hint) is event
