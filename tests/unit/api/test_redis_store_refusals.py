"""A store that refuses a write leaves no key in what is logged or sent to the error tracker.

redis-py puts the text of a failed pipeline command, key included, into the message of the
error it raises. The assistant throttle logs that error with its traceback, and the error
tracker turns every ERROR record into an event. These tests run the real throttle against a
loopback stub that answers like a read-only replica, so the error is the one redis-py really
raises, and read everything a record and an event say.
"""

import asyncio
import logging
import traceback
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from typing import Any, NamedTuple
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
from api.config import get_settings
from api.main import _init_sentry
from tests.shared.helpers import captured_log_records
from tests.shared.resp_stub import RespStub, resp_stub
from tests.shared.sentry_capture import KeepEnvelopes, capturing_transport

_FAKE_DSN = "https://public@o0.ingest.sentry.io/0"
_LOGGERS = ("api.security", "api.assistant.deps")
_READ_ONLY = "read only replica"
_QUEUED = b"+QUEUED\r\n"
# A transaction that ran: SET answered OK, then the counter reached 6 (the budget is 5).
_OVER_BUDGET = b"*2\r\n+OK\r\n:6\r\n"
_ERR_BOOM = b"-ERR boom\r\n"
_USER_ID = UUID("7d1e2f60-3a4b-4c5d-8e9f-0a1b2c3d4e5f")
_ADDRESS = "203.0.113.57"


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


class _Emitted(NamedTuple):
    """A record and everything it said at the moment it was emitted."""

    record: logging.LogRecord
    text: str


class _SayAtEmit(logging.Handler):
    """Render each record as it is emitted, before anything can change the error it holds.

    The text holds the formatted message and traceback, the arguments and the attributes, so
    what an application handler would write is read at the moment it would write it. A record
    formatted after the test has run would show an error the code had already cleaned up.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self.seen: list[_Emitted] = []
        self._formatter = logging.Formatter("%(name)s %(levelname)s %(message)s")

    def emit(self, record: logging.LogRecord) -> None:
        text = "\n".join(
            [
                self._formatter.format(record),
                repr(record.args),
                repr(record.__dict__),
                record.stack_info or "",
            ]
        )
        self.seen.append(_Emitted(record, text))


@pytest.fixture
def records() -> Iterator[Callable[[], list[_Emitted]]]:
    """Collect, with their text at emit time, the records of the loggers the stores write to."""
    handler = _SayAtEmit()
    with ExitStack() as stack:
        for name in _LOGGERS:
            stack.enter_context(captured_log_records(name))
            logging.getLogger(name).addHandler(handler)
            stack.callback(logging.getLogger(name).removeHandler, handler)
        yield lambda: list(handler.seen)


def _event_of(emitted: _Emitted) -> str | None:
    """Return the ``event`` field of a record, or None."""
    return getattr(emitted.record, "event", None)


def _assert_no_record_holds(records: list[_Emitted], needles: list[str], stub: RespStub) -> None:
    """Fail when a record says one of the needles, or when the stub never saw the first one.

    The second check keeps the first honest: a key the stub never received could not have
    been in an error, so the test would pass on any code.
    """
    assert stub.received(needles[0]), "the stub never received the key"
    assert records, "no record was written"
    for emitted in records:
        for needle in needles:
            assert needle not in emitted.text, (
                f"{emitted.record.name} logged {needle!r}: {emitted.record.getMessage()}"
            )


def _the_record(records: list[_Emitted], event: str) -> _Emitted:
    """Return the one record of an event, with its text at emit time."""
    found = [record for record in records if _event_of(record) == event]
    assert len(found) == 1, [_event_of(record) for record in records]
    return found[0]


_KINDS = ("a user", "an address", "everyone")


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


class TestAssistantThrottleRefusal:
    """A store that refuses the assistant throttle's count leaves no key in a record."""

    @pytest.mark.parametrize("kind", _KINDS)
    def test_the_record_names_the_reason_and_holds_no_key(self, stub, client, records, kind):
        """
        GIVEN a store that refuses writes and a throttle counting under one kind of key
        WHEN a message is counted
        THEN the turn is refused as before, the record names the Redis error class and the
            server's reason, and no record holds the key or what identifies its owner
        """
        # GIVEN
        key, needles = _assistant_keys()[kind]
        throttle = RedisAssistantThrottle(client, max_per_hour=5)

        # WHEN
        with pytest.raises(AssistantUnavailableError) as raised:
            throttle.charge_key(key)

        # THEN
        text = _the_record(records(), "assistant_throttle_unavailable").text
        assert "ReadOnlyError" in text
        assert _READ_ONLY in text
        assert isinstance(raised.value.__cause__, redis.ReadOnlyError)
        propagated = "".join(traceback.format_exception(raised.value))
        for needle in needles:
            assert needle not in propagated
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
        text = _the_record(records(), "assistant_throttle_unavailable").text
        assert "ReadOnlyError" in text
        _assert_no_record_holds(records(), [f"{KEY_PREFIX}:{digest}", digest], stub)


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
        text = _the_record(records(), "assistant_throttle_giveback_unavailable").text
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

    def test_a_connection_failure_keeps_the_host_and_port_of_the_store(self, records):
        """
        GIVEN a connection error that names the store's host and port
        WHEN the throttle records that the store is unavailable
        THEN the record still names them, because only a pipeline's command text is dropped
        """
        # GIVEN
        exc = redis.ConnectionError("Error 61 connecting to 127.0.0.1:6390. Connection refused.")

        # WHEN
        assistant_rate_limit._log_store_unavailable(exc)

        # THEN
        text = _the_record(records(), "assistant_throttle_unavailable").text
        assert "127.0.0.1:6390" in text
        assert "ConnectionError" in text

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

    @pytest.mark.parametrize("kind", ["a user", "an address"])
    def test_the_assistant_throttle_event_holds_no_key(self, stub, client, sentry_events, kind):
        """
        GIVEN Sentry started by the app's own initialisation, and a store that refuses writes
        WHEN an assistant message is counted under a user's or an address's key
        THEN an event names the Redis error class and no item sent holds the key or what
            identifies its owner
        """
        # GIVEN
        key, needles = _assistant_keys()[kind]
        throttle = RedisAssistantThrottle(client, max_per_hour=5)

        # WHEN
        with pytest.raises(AssistantUnavailableError):
            throttle.charge_key(key)
        sentry_sdk.flush()

        # THEN
        kept = sentry_events()
        sent = kept.serialized()
        assert stub.received(needles[0])
        assert "ReadOnlyError" in sent
        assert kept.items("event")
        for needle in needles:
            assert needle not in sent
