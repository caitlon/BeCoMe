"""Tests for the request-scoped logging context and ContextFilter."""

import contextvars
import logging

from api.logging_context import (
    ContextFilter,
    get_request_id,
    get_user_id,
    reset_request_id,
    set_request_id,
    set_user_id,
)


def _record() -> logging.LogRecord:
    """Build a minimal log record for filter tests."""
    return logging.LogRecord(
        name="api.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )


class TestContextVars:
    """Round-trips for the context variables."""

    def test_request_id_round_trip(self):
        """
        GIVEN no bound request ID
        WHEN one is set and then reset
        THEN get reflects the value and returns to None afterwards
        """
        # GIVEN
        assert get_request_id() is None

        # WHEN
        token = set_request_id("req-1")

        # THEN
        assert get_request_id() == "req-1"
        reset_request_id(token)
        assert get_request_id() is None

    def test_user_id_stays_in_the_context_that_set_it(self):
        """
        GIVEN no bound user ID
        WHEN one is set inside a copied context, as each request runs in its own
        THEN get reflects the value there and the outer context stays unset
        """
        # GIVEN
        assert get_user_id() is None

        def bind_and_read() -> str | None:
            set_user_id("user-1")
            return get_user_id()

        # WHEN
        seen = contextvars.copy_context().run(bind_and_read)

        # THEN
        assert seen == "user-1"
        assert get_user_id() is None


class TestContextFilter:
    """ContextFilter enriches records from the active context."""

    def test_adds_bound_context_to_record(self):
        """
        GIVEN request and user IDs bound in a copied context
        WHEN the filter processes a record there
        THEN the record gains both attributes and is kept
        """
        # GIVEN
        record = _record()

        def filter_with_bound_context() -> bool:
            set_request_id("req-9")
            set_user_id("user-9")
            return ContextFilter().filter(record)

        # WHEN
        kept = contextvars.copy_context().run(filter_with_bound_context)

        # THEN
        assert kept is True
        assert record.request_id == "req-9"
        assert record.user_id == "user-9"

    def test_does_not_override_explicit_extra(self):
        """
        GIVEN a record already carrying a request_id from extra
        WHEN the filter runs with a different bound request ID
        THEN the explicit value is preserved
        """
        # GIVEN
        token = set_request_id("ctx-id")
        record = _record()
        record.request_id = "explicit-id"

        # WHEN
        try:
            ContextFilter().filter(record)
        finally:
            reset_request_id(token)

        # THEN
        assert record.request_id == "explicit-id"

    def test_omits_unset_context(self):
        """
        GIVEN no bound context
        WHEN the filter processes a record
        THEN no context attributes are attached
        """
        # GIVEN
        record = _record()

        # WHEN
        ContextFilter().filter(record)

        # THEN
        assert not hasattr(record, "request_id")
        assert not hasattr(record, "user_id")
