"""Unit tests for the HTTP handlers of the assistant's chat errors."""

import json
import logging
from unittest.mock import MagicMock

import pytest

from api.assistant.errors import (
    AssistantRateLimitedError,
    AssistantUnavailableError,
    AssistantUpstreamError,
)
from api.assistant.exception_handlers import (
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
                AssistantRateLimitedError(_PRIVATE_TEXT),
                429,
                "Too many assistant messages. Please try again later.",
                "assistant_rate_limited",
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
        ids=["rate_limited", "unavailable", "upstream"],
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
