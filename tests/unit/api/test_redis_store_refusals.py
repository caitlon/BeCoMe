"""A store that refuses a write leaves no key in what is logged or sent to the error tracker.

redis-py puts the text of a failed pipeline command, key included, into the message of the
error it raises. The throttles and the revocation store log that error with its traceback, and
the error tracker turns every ERROR record into an event. These tests run the real stores
against a loopback stub that answers like a read-only replica, so the error is the one
redis-py really raises, and read everything a record and an event say.
"""

import asyncio
import logging
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest
import redis
import sentry_sdk

from api.assistant import deps
from api.assistant import rate_limit as assistant_rate_limit
from api.assistant.errors import AssistantUnavailableError
from api.assistant.rate_limit import (
    GLOBAL_KEY,
    KEY_PREFIX,
    Charge,
    RedisAssistantThrottle,
    address_key,
)
from api.auth import login_throttle
from api.auth.email_throttle import RESET_KEY_PREFIX, RedisEmailSendThrottle
from api.auth.login_throttle import LOGIN_KEY_PREFIX, RedisLoginThrottle
from api.auth.revocation_store import RedisRevocationStore, RevocationStoreError
from api.config import get_settings
from api.main import _init_sentry
from api.middleware.exception_handlers import revocation_store_unavailable_handler
from tests.shared.helpers import captured_log_records
from tests.shared.resp_stub import (
    EXECABORT_REPLY,
    OK_REPLY,
    RespStub,
    resp_stub,
)
from tests.shared.sentry_capture import KeepEnvelopes, capturing_transport

_FAKE_DSN = "https://public@o0.ingest.sentry.io/0"
_LOGGERS = ("api.security", "api.exception", "api.assistant.deps")
_READ_ONLY = "read only replica"
_QUEUED = b"+QUEUED\r\n"
# A transaction that ran: SET answered OK, then the counter reached 6 (the budget is 5).
_OVER_BUDGET = b"*2\r\n+OK\r\n:6\r\n"
# A transaction of two reads: no value, no expiry set.
_TWO_READS = b"*2\r\n_\r\n:-2\r\n"
_ERR_BOOM = b"-ERR boom\r\n"
_USER_ID = UUID("7d1e2f60-3a4b-4c5d-8e9f-0a1b2c3d4e5f")
_ADDRESS = "203.0.113.57"
_IDENTIFIER = "sentinel.person@example.com"
_SESSION_ID = "sentinel-session-id-5c1f"
_NEW_JTI = "sentinel-new-jti-8b2e"
_OLD_JTI = "sentinel-old-jti-3d9a"


@pytest.fixture
def stub() -> Iterator[RespStub]:
    """A loopback server that answers like a read-only replica."""
    with resp_stub() as running:
        yield running


@pytest.fixture
def client(stub: RespStub) -> Iterator[redis.Redis]:
    """A client built the way the application builds it, pointed at the stub."""
    built = redis.from_url(stub.url, socket_connect_timeout=2, socket_timeout=2)
    try:
        yield built
    finally:
        built.close()


@pytest.fixture
def records() -> Iterator[Callable[[], list[logging.LogRecord]]]:
    """Collect the records of the loggers the stores and their handlers write to."""
    with ExitStack() as stack:
        groups = [stack.enter_context(captured_log_records(name)) for name in _LOGGERS]
        yield lambda: [record for group in groups for record in group]


def _everything_a_record_says(record: logging.LogRecord) -> str:
    """Render a record as every handler could: message, arguments, attributes and tracebacks.

    The traceback is formatted again from ``exc_info``, so the messages of the exception and of
    its chained causes are in it.
    """
    parts = [
        logging.Formatter("%(name)s %(levelname)s %(message)s").format(record),
        repr(record.args),
        repr(record.__dict__),
        record.exc_text or "",
        record.stack_info or "",
    ]
    if record.exc_info and record.exc_info[0] is not None:
        parts.append(logging.Formatter().formatException(record.exc_info))
    return "\n".join(parts)


def _event_of(record: logging.LogRecord) -> str | None:
    """Return the ``event`` field of a record, or None."""
    return getattr(record, "event", None)


def _assert_no_record_holds(
    records: list[logging.LogRecord], needles: list[str], stub: RespStub
) -> None:
    """Fail when a record says one of the needles, or when the stub never saw the first one.

    The second check keeps the first honest: a key the stub never received could not have
    been in an error, so the test would pass on any code.
    """
    assert stub.received(needles[0]), "the stub never received the key"
    assert records, "no record was written"
    for record in records:
        text = _everything_a_record_says(record)
        for needle in needles:
            assert needle not in text, f"{record.name} logged {needle!r}: {record.getMessage()}"


def _the_record(records: list[logging.LogRecord], event: str) -> logging.LogRecord:
    """Return the one record of an event."""
    found = [record for record in records if _event_of(record) == event]
    assert len(found) == 1, [_event_of(record) for record in records]
    return found[0]


def _assistant_keys() -> dict[str, tuple[str, list[str]]]:
    """Return the three kinds of key the assistant throttle counts under.

    :return: Per kind, the key passed to the throttle and the texts that must stay out of a
        record: the Redis key and the part of it that identifies the user or the address.
    """
    user = assistant_rate_limit._digest(_USER_ID)
    address = address_key(_ADDRESS)
    return {
        "a user": (user, [f"{KEY_PREFIX}:{user}", user]),
        "an address": (address, [f"{KEY_PREFIX}:{address}", address.removeprefix("addr:")]),
        "everyone": (GLOBAL_KEY, [f"{KEY_PREFIX}:{GLOBAL_KEY}"]),
    }


_ASSISTANT_KEYS = _assistant_keys()


class TestAssistantThrottleRefusal:
    """A store that refuses the assistant throttle's count leaves no key in a record."""

    @pytest.mark.parametrize("kind", list(_ASSISTANT_KEYS), ids=list(_ASSISTANT_KEYS))
    def test_the_record_names_the_reason_and_holds_no_key(self, stub, client, records, kind):
        """
        GIVEN a store that refuses writes and a throttle counting under one kind of key
        WHEN a message is counted
        THEN the turn is refused as before, the record names the Redis error class and the
            server's reason, and no record holds the key or what identifies its owner
        """
        # GIVEN
        key, needles = _ASSISTANT_KEYS[kind]
        throttle = RedisAssistantThrottle(client, max_per_hour=5)

        # WHEN
        with pytest.raises(AssistantUnavailableError) as raised:
            throttle.charge_key(key)

        # THEN
        text = _everything_a_record_says(_the_record(records(), "assistant_throttle_unavailable"))
        assert "ReadOnlyError" in text
        assert _READ_ONLY in text
        assert isinstance(raised.value.__cause__, redis.ReadOnlyError)
        for needle in needles:
            assert needle not in str(raised.value.__cause__)
        _assert_no_record_holds(records(), needles, stub)

    def test_a_user_charge_leaves_no_key_in_a_record(self, stub, client, records):
        """
        GIVEN a store that refuses writes
        WHEN a message is counted for a user id
        THEN the turn is refused, the record names the Redis error class, and no record holds
            the user's digest
        """
        # GIVEN
        throttle = RedisAssistantThrottle(client, max_per_hour=5)
        digest = assistant_rate_limit._digest(_USER_ID)

        # WHEN
        with pytest.raises(AssistantUnavailableError):
            throttle.charge(_USER_ID)

        # THEN
        text = _everything_a_record_says(_the_record(records(), "assistant_throttle_unavailable"))
        assert "ReadOnlyError" in text
        _assert_no_record_holds(records(), [f"{KEY_PREFIX}:{digest}", digest], stub)


class TestLoginThrottleRefusal:
    """A store that refuses the login throttle's pipelines leaves no digest in a record."""

    def _needles(self) -> list[str]:
        return [login_throttle._digest(_IDENTIFIER), f"{LOGIN_KEY_PREFIX}:fail:"]

    def test_reserve_fails_open_and_the_record_holds_no_key(self, stub, client, records):
        """
        GIVEN a store that refuses writes
        WHEN an attempt is reserved
        THEN the attempt is let through, the record names the error class and the reason, and
            no record holds the key or the digest of the identifier
        """
        # GIVEN
        throttle = RedisLoginThrottle(client, key_prefix=LOGIN_KEY_PREFIX)

        # WHEN
        allowed = throttle.reserve(_IDENTIFIER)

        # THEN
        assert allowed is True
        text = _everything_a_record_says(_the_record(records(), "throttle_store_unavailable"))
        assert "ReadOnlyError" in text
        assert _READ_ONLY in text
        _assert_no_record_holds(records(), self._needles(), stub)

    def test_record_failure_fails_open_and_the_record_holds_no_key(self, stub, client, records):
        """
        GIVEN a store that refuses writes
        WHEN a failure is recorded
        THEN the call returns and no record holds the key or the digest of the identifier
        """
        # GIVEN
        throttle = RedisLoginThrottle(client, key_prefix=LOGIN_KEY_PREFIX)

        # WHEN
        throttle.record_failure(_IDENTIFIER)

        # THEN
        _the_record(records(), "throttle_store_unavailable")
        _assert_no_record_holds(records(), self._needles(), stub)

    def test_a_refused_give_back_fails_open_and_the_record_holds_no_key(
        self, stub, client, records
    ):
        """
        GIVEN a throttle with no budget, whose counting transaction runs, and a store that then
            refuses the pipeline that restores a counter gone negative
        WHEN an attempt is reserved
        THEN the attempt is let through and no record holds the key or the digest
        """
        # GIVEN
        throttle = RedisLoginThrottle(client, key_prefix=LOGIN_KEY_PREFIX, max_failures=0)
        stub.reply_to(
            "INCRBY", _QUEUED, b"-READONLY You can't write against a read only replica.\r\n"
        )
        stub.reply_to("EXEC", b"*2\r\n:1\r\n:60\r\n", EXECABORT_REPLY)
        stub.reply_to("DECRBY", b":-1\r\n")

        # WHEN
        allowed = throttle.reserve(_IDENTIFIER)

        # THEN
        assert allowed is True
        assert [words[0] for words in stub.commands() if words[0] == "EXEC"] == ["EXEC", "EXEC"]
        _assert_no_record_holds(records(), self._needles(), stub)

    def test_a_refused_release_fails_open_and_the_record_holds_no_key(self, stub, client, records):
        """
        GIVEN a store whose counter has gone negative and that refuses the pipeline that
            restores it
        WHEN a reserved attempt is released
        THEN the call returns, the record names the error class, and no record holds the key
            or the digest of the identifier
        """
        # GIVEN
        throttle = RedisLoginThrottle(client, key_prefix=LOGIN_KEY_PREFIX)
        stub.reply_to("DECRBY", b":-1\r\n")
        stub.reply_to("INCRBY", b"-READONLY You can't write against a read only replica.\r\n")
        stub.reply_to("EXEC", EXECABORT_REPLY)

        # WHEN
        throttle.release(_IDENTIFIER)

        # THEN
        text = _everything_a_record_says(_the_record(records(), "throttle_store_unavailable"))
        assert "ReadOnlyError" in text
        assert [words[0] for words in stub.commands() if words[0] == "EXEC"] == ["EXEC"]
        _assert_no_record_holds(records(), self._needles(), stub)


class TestEmailThrottleRefusal:
    """A store that refuses the email throttle's pipelines leaves no digest in a record."""

    def _needles(self) -> list[str]:
        digest = login_throttle._digest(_IDENTIFIER)
        return [digest, f"{RESET_KEY_PREFIX}:daily:", f"{RESET_KEY_PREFIX}:cooldown:"]

    def test_allow_fails_open_when_the_count_is_refused(self, stub, client, records):
        """
        GIVEN a store that takes the cooldown key and the read of the counter but refuses the
            transaction that counts the send
        WHEN a send is asked for
        THEN the send is allowed and no record holds a key or the address digest
        """
        # GIVEN
        throttle = RedisEmailSendThrottle(client, key_prefix=RESET_KEY_PREFIX)
        stub.reply_to(
            "SET", OK_REPLY, b"-READONLY You can't write against a read only replica.\r\n"
        )
        stub.reply_to("EXEC", _TWO_READS, EXECABORT_REPLY)

        # WHEN
        allowed = throttle.allow(_IDENTIFIER)

        # THEN
        assert allowed is True
        text = _everything_a_record_says(_the_record(records(), "throttle_store_unavailable"))
        assert "ReadOnlyError" in text
        assert _READ_ONLY in text
        _assert_no_record_holds(records(), self._needles(), stub)

    def test_allow_fails_open_when_the_read_of_the_counter_is_refused(self, stub, client, records):
        """
        GIVEN a store that takes the cooldown key but answers the read of the counter, queued
            in a transaction, with an error
        WHEN a send is asked for
        THEN the send is allowed and no record holds a key or the address digest
        """
        # GIVEN
        throttle = RedisEmailSendThrottle(client, key_prefix=RESET_KEY_PREFIX)
        stub.reply_to("SET", OK_REPLY)
        stub.reply_to("GET", _ERR_BOOM)
        stub.reply_to("EXEC", EXECABORT_REPLY)

        # WHEN
        allowed = throttle.allow(_IDENTIFIER)

        # THEN
        assert allowed is True
        text = _everything_a_record_says(_the_record(records(), "throttle_store_unavailable"))
        assert "boom" in text
        _assert_no_record_holds(records(), self._needles(), stub)

    def test_record_fails_open_when_the_count_is_refused(self, stub, client, records):
        """
        GIVEN a store that takes the cooldown key but refuses the transaction that counts
        WHEN a send is recorded
        THEN the call returns and no record holds a key or the address digest
        """
        # GIVEN
        throttle = RedisEmailSendThrottle(client, key_prefix=RESET_KEY_PREFIX)
        stub.reply_to(
            "SET", OK_REPLY, b"-READONLY You can't write against a read only replica.\r\n"
        )

        # WHEN
        throttle.record(_IDENTIFIER)

        # THEN
        _the_record(records(), "throttle_store_unavailable")
        _assert_no_record_holds(records(), self._needles(), stub)


class TestRevocationStoreRefusal:
    """A store that refuses a session write leaves no session id in a record or a message."""

    def _handler_record(self, error: Exception) -> logging.LogRecord:
        """Run the 503 handler on an error and return the record it wrote."""
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="request-1"),
            url=SimpleNamespace(path="/api/v1/auth/logout"),
        )
        with captured_log_records("api.exception") as written:
            response = revocation_store_unavailable_handler(request, error)  # type: ignore[arg-type]
        assert response.status_code == 503
        return _the_record(written, "revocation_store_request_failed")

    def _assert_clean(
        self,
        stub: RespStub,
        records: Callable[[], list[logging.LogRecord]],
        error: Exception,
        needles: list[str],
    ) -> None:
        """Check the error, the store's warning and the 503 handler's record against the needles."""
        assert isinstance(error.__cause__, redis.ReadOnlyError)
        for needle in needles:
            assert needle not in str(error)
        text = _everything_a_record_says(_the_record(records(), "revocation_store_unavailable"))
        assert "ReadOnlyError" in text
        assert _READ_ONLY in text
        _assert_no_record_holds(records(), needles, stub)
        handler_text = _everything_a_record_says(self._handler_record(error))
        for needle in needles:
            assert needle not in handler_text

    def test_revoke_session_raises_an_error_that_holds_no_session_id(self, stub, client, records):
        """
        GIVEN a store that refuses the transaction that revokes a session
        WHEN the session is revoked
        THEN the store's error, the warning and the 503 handler's record hold no session id
            and no key
        """
        # GIVEN
        store = RedisRevocationStore(client)

        # WHEN
        with pytest.raises(RevocationStoreError) as raised:
            store.revoke_session(_SESSION_ID, 60)

        # THEN
        self._assert_clean(
            stub, records, raised.value, [_SESSION_ID, f"session:revoked:{_SESSION_ID}"]
        )

    def test_rotate_session_raises_an_error_that_holds_no_session_id_or_token_id(
        self, stub, client, records
    ):
        """
        GIVEN a store whose session holds the expected token id and that refuses the
            transaction that replaces it
        WHEN the session is rotated
        THEN the store's error, the warning and the 503 handler's record hold no session id,
            token id or key
        """
        # GIVEN
        store = RedisRevocationStore(client)
        stub.reply_to("GET", f"${len(_OLD_JTI)}\r\n{_OLD_JTI}\r\n".encode())

        # WHEN
        with pytest.raises(RevocationStoreError) as raised:
            store.rotate_session(_SESSION_ID, _OLD_JTI, _NEW_JTI, 60)

        # THEN
        self._assert_clean(
            stub,
            records,
            raised.value,
            [_NEW_JTI, f"session:current:{_SESSION_ID}", _SESSION_ID],
        )


class TestSingleCommandRefusals:
    """A refused single command is never annotated, so its record holds no key either."""

    def test_the_give_back_of_a_refused_message_holds_no_key(self, stub, client, records):
        """
        GIVEN a store that counts a message over the budget and then refuses the script that
            gives it back
        WHEN the message is counted
        THEN it is refused without an error and no record holds the key
        """
        # GIVEN
        throttle = RedisAssistantThrottle(client, max_per_hour=5)
        digest = assistant_rate_limit._digest(_USER_ID)
        stub.reply_to("SET", _QUEUED)
        stub.reply_to("INCRBY", _QUEUED)
        stub.reply_to("EXEC", _OVER_BUDGET)

        # WHEN
        charge = throttle.charge_key(digest)

        # THEN
        assert charge.allowed is False
        text = _everything_a_record_says(
            _the_record(records(), "assistant_throttle_giveback_unavailable")
        )
        assert "ReadOnlyError" in text
        _assert_no_record_holds(records(), [f"{KEY_PREFIX}:{digest}", digest], stub)

    def test_the_refund_of_a_message_holds_no_key(self, stub, client, records):
        """
        GIVEN a store that refuses the script that gives a message back
        WHEN a counted message is refunded
        THEN the call returns and no record holds the key
        """
        # GIVEN
        throttle = RedisAssistantThrottle(client, max_per_hour=5)
        digest = assistant_rate_limit._digest(_USER_ID)

        # WHEN
        throttle.refund(Charge(digest, allowed=True, in_store=True))

        # THEN
        _the_record(records(), "assistant_throttle_refund_unavailable")
        _assert_no_record_holds(records(), [f"{KEY_PREFIX}:{digest}", digest], stub)

    def test_a_failed_read_of_the_wait_holds_no_key(self, stub, client, records):
        """
        GIVEN a store that answers the read of a key's remaining time with an error
        WHEN the wait is asked for
        THEN the whole window is returned and no record holds the key
        """
        # GIVEN
        throttle = RedisAssistantThrottle(client, max_per_hour=5, window_seconds=3600)
        digest = assistant_rate_limit._digest(_USER_ID)
        stub.reply_to("TTL", _ERR_BOOM)

        # WHEN
        wait = throttle.retry_after_key(digest)

        # THEN
        assert wait == 3600
        _the_record(records(), "assistant_throttle_retry_unavailable")
        _assert_no_record_holds(records(), [f"{KEY_PREFIX}:{digest}", digest], stub)

    def test_the_route_helper_that_gives_a_charge_back_writes_no_record_of_its_own(
        self, stub, client, records
    ):
        """
        GIVEN a store that refuses the script that gives a message back
        WHEN the route's helper refunds a charge
        THEN the throttle's own record is the only one, the helper's failure record is not
            written, and no record holds the key
        """
        # GIVEN
        throttle = RedisAssistantThrottle(client, max_per_hour=5)
        digest = assistant_rate_limit._digest(_USER_ID)

        # WHEN
        asyncio.run(deps._give_back(throttle, Charge(digest, allowed=True, in_store=True)))

        # THEN
        events = [_event_of(record) for record in records()]
        assert events == ["assistant_throttle_refund_unavailable"]
        _assert_no_record_holds(records(), [f"{KEY_PREFIX}:{digest}", digest], stub)


@pytest.fixture
def sentry_events() -> Iterator[Callable[[], KeepEnvelopes]]:
    """Start Sentry with the app's own initialisation, sending to a transport that keeps envelopes.

    The client is left unset afterwards, as ``capturing_transport`` leaves it.
    """
    real_init = sentry_sdk.init
    settings = get_settings().model_copy(update={"sentry_dsn": _FAKE_DSN})
    with capturing_transport() as keep:

        def init_with_transport(**kwargs: Any) -> None:
            real_init(**kwargs, transport=keep)

        with patch("api.main.sentry_sdk.init", init_with_transport):
            _init_sentry(settings)
        yield lambda: keep


class TestErrorTrackerEventsOfARefusedWrite:
    """The error tracker receives a refused write without the key in it."""

    def test_the_assistant_throttle_event_holds_no_key(self, stub, client, sentry_events):
        """
        GIVEN Sentry started by the app's own initialisation, and a store that refuses writes
        WHEN an assistant message is counted
        THEN an event names the Redis error class and no item sent holds the key or the digest
        """
        # GIVEN
        throttle = RedisAssistantThrottle(client, max_per_hour=5)
        digest = assistant_rate_limit._digest(_USER_ID)

        # WHEN
        with pytest.raises(AssistantUnavailableError):
            throttle.charge_key(digest)
        sentry_sdk.flush()

        # THEN
        kept = sentry_events()
        sent = kept.serialized()
        assert stub.received(digest)
        assert "ReadOnlyError" in sent
        assert kept.items("event")
        for needle in (f"{KEY_PREFIX}:{digest}", digest):
            assert needle not in sent

    def test_the_login_throttle_event_holds_no_digest(self, stub, client, sentry_events):
        """
        GIVEN Sentry started by the app's own initialisation, and a store that refuses writes
        WHEN a login attempt is reserved
        THEN an event names the Redis error class and no item sent holds the key or the digest
        """
        # GIVEN
        throttle = RedisLoginThrottle(client, key_prefix=LOGIN_KEY_PREFIX)
        digest = login_throttle._digest(_IDENTIFIER)

        # WHEN
        throttle.reserve(_IDENTIFIER)
        sentry_sdk.flush()

        # THEN
        kept = sentry_events()
        sent = kept.serialized()
        assert stub.received(digest)
        assert "ReadOnlyError" in sent
        assert kept.items("event")
        assert digest not in sent
        assert f"{LOGIN_KEY_PREFIX}:fail:" not in sent

    def test_the_email_throttle_event_holds_no_key_or_digest(self, stub, client, sentry_events):
        """
        GIVEN Sentry started by the app's own initialisation, and a store that takes the
            cooldown key but refuses the transaction that counts the send
        WHEN a send is asked for
        THEN an event names the Redis error class and no item sent holds a key or the digest
        """
        # GIVEN
        throttle = RedisEmailSendThrottle(client, key_prefix=RESET_KEY_PREFIX)
        digest = login_throttle._digest(_IDENTIFIER)
        stub.reply_to(
            "SET", OK_REPLY, b"-READONLY You can't write against a read only replica.\r\n"
        )
        stub.reply_to("EXEC", _TWO_READS, EXECABORT_REPLY)

        # WHEN
        allowed = throttle.allow(_IDENTIFIER)
        sentry_sdk.flush()

        # THEN
        assert allowed is True
        kept = sentry_events()
        sent = kept.serialized()
        assert stub.received(digest)
        assert kept.items("event")
        assert "ReadOnlyError" in sent
        for needle in (digest, f"{RESET_KEY_PREFIX}:daily:", f"{RESET_KEY_PREFIX}:cooldown:"):
            assert needle not in sent

    def test_the_revocation_store_event_holds_no_session_id(self, stub, client, sentry_events):
        """
        GIVEN Sentry started by the app's own initialisation, and a store that refuses the
            transaction that revokes a session
        WHEN the 503 handler answers the store's error
        THEN an event names the Redis error class and no item sent holds the session id value
            or its key
        """
        # GIVEN
        store = RedisRevocationStore(client)
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="request-1"),
            url=SimpleNamespace(path="/api/v1/auth/logout"),
        )

        # WHEN
        with pytest.raises(RevocationStoreError) as raised:
            store.revoke_session(_SESSION_ID, 60)
        response = revocation_store_unavailable_handler(request, raised.value)  # type: ignore[arg-type]
        sentry_sdk.flush()

        # THEN
        assert response.status_code == 503
        kept = sentry_events()
        sent = kept.serialized()
        assert stub.received(_SESSION_ID)
        assert kept.items("event")
        assert "ReadOnlyError" in sent
        for needle in (_SESSION_ID, f"session:revoked:{_SESSION_ID}"):
            assert needle not in sent
