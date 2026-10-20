"""Unit tests for the HTTP handlers of the assistant's chat errors."""

import json
import logging
from unittest.mock import MagicMock

import pytest

from api.assistant.errors import (
    AssistantBusyError,
    AssistantRateLimitedError,
    AssistantUnavailableError,
    AssistantUpstreamError,
)
from api.assistant.exception_handlers import (
    assistant_busy_handler,
    assistant_rate_limited_handler,
    assistant_unavailable_handler,
    assistant_upstream_handler,
)

_PRIVATE_TEXT = "what is the compromise value of my private project"


def _request() -> MagicMock:
    """Build a request stand-in carrying only what the handlers read."""
    request = MagicMock()
    request.state.request_id = "req-1"
    request.url.path = "/api/v1/assistant/chat"
    return request


class TestAssistantExceptionHandlers:
    """Each chat error answers with its own status and a fixed public body."""

    @pytest.mark.parametrize(
        ("handler", "exc", "status_code", "detail", "event"),
        [
            (
                assistant_rate_limited_handler,
                AssistantRateLimitedError(_PRIVATE_TEXT, retry_after=90),
                429,
                "Too many assistant messages. Please try again later.",
                "assistant_rate_limited",
            ),
            (
                assistant_busy_handler,
                AssistantBusyError(_PRIVATE_TEXT, retry_after=5),
                503,
                "The assistant is temporarily unavailable",
                "assistant_busy",
            ),
            (
                assistant_unavailable_handler,
                AssistantUnavailableError(_PRIVATE_TEXT),
                503,
                "The assistant is temporarily unavailable",
                "assistant_unavailable",
            ),
            (
                assistant_upstream_handler,
                AssistantUpstreamError(_PRIVATE_TEXT),
                503,
                "The assistant is temporarily unavailable",
                "assistant_upstream_error",
            ),
        ],
        ids=["rate_limited", "busy", "unavailable", "upstream"],
    )
    def test_answers_with_the_status_and_detail_body(
        self, caplog, handler, exc, status_code, detail, event
    ):
        """
        GIVEN a chat error whose message holds text that must not be echoed
        WHEN its handler runs
        THEN the response has the mapped status and the app's {"detail": ...} body,
             and the log record names an event without the error's own text
        """
        # GIVEN
        caplog.set_level(logging.DEBUG, logger="api.assistant")

        # WHEN
        response = handler(_request(), exc)

        # THEN
        assert response.status_code == status_code
        assert json.loads(bytes(response.body)) == {"detail": detail}
        records = [r for r in caplog.records if getattr(r, "event", None) == event]
        assert len(records) == 1
        assert records[0].request_id == "req-1"
        assert _PRIVATE_TEXT not in records[0].getMessage()

    def test_the_rate_limited_answer_carries_retry_after(self):
        """
        GIVEN a rate-limited error holding 1234 seconds
        WHEN its handler runs
        THEN the 429 has a Retry-After header of that many whole seconds
        """
        # GIVEN
        exc = AssistantRateLimitedError(_PRIVATE_TEXT, retry_after=1234)

        # WHEN
        response = assistant_rate_limited_handler(_request(), exc)

        # THEN
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "1234"

    def test_the_busy_answer_carries_retry_after_and_is_logged_at_warning(self, caplog):
        """
        GIVEN a busy error holding 1234 seconds
        WHEN its handler runs
        THEN the 503 has a Retry-After header of that many seconds, and the record is a
             WARNING, since a full assistant is load and not a fault
        """
        # GIVEN
        caplog.set_level(logging.DEBUG, logger="api.assistant")
        exc = AssistantBusyError(_PRIVATE_TEXT, retry_after=1234)

        # WHEN
        response = assistant_busy_handler(_request(), exc)

        # THEN
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "1234"
        assert [r.levelno for r in caplog.records] == [logging.WARNING]

    def test_the_upstream_failure_is_logged_at_error(self, caplog):
        """
        GIVEN an AssistantUpstreamError
        WHEN its handler runs
        THEN the record is ERROR, since it marks a fault on the model side
        """
        # GIVEN
        caplog.set_level(logging.DEBUG, logger="api.assistant")

        # WHEN
        assistant_upstream_handler(_request(), AssistantUpstreamError("bad body"))

        # THEN
        assert [r.levelno for r in caplog.records] == [logging.ERROR]
