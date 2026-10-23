"""Unit tests for the assistant's exception hierarchy."""

from api.assistant.errors import (
    AssistantBusyError,
    AssistantError,
    AssistantNotFoundError,
    AssistantRateLimitedError,
    AssistantUnavailableError,
    AssistantUpstreamError,
)
from api.exceptions import BeCoMeAPIError


class TestAssistantErrorHierarchy:
    """Every assistant exception is a BeCoMeAPIError, so the central handler covers it."""

    def test_assistant_error_is_a_becomeapierror(self):
        """
        GIVEN AssistantError
        WHEN its bases are inspected
        THEN it is a BeCoMeAPIError
        """
        assert issubclass(AssistantError, BeCoMeAPIError)

    def test_not_found_is_an_assistant_error(self):
        """
        GIVEN AssistantNotFoundError
        WHEN its bases are inspected
        THEN it is an AssistantError
        """
        assert issubclass(AssistantNotFoundError, AssistantError)

    def test_upstream_is_an_assistant_error(self):
        """
        GIVEN AssistantUpstreamError
        WHEN its bases are inspected
        THEN it is an AssistantError
        """
        assert issubclass(AssistantUpstreamError, AssistantError)

    def test_not_found_and_upstream_are_distinguishable(self):
        """
        GIVEN AssistantNotFoundError and AssistantUpstreamError
        WHEN checked against each other
        THEN neither is a subclass of the other
        """
        assert not issubclass(AssistantNotFoundError, AssistantUpstreamError)
        assert not issubclass(AssistantUpstreamError, AssistantNotFoundError)


class TestChatErrorHierarchy:
    """The chat-specific errors are assistant errors, distinct from each other."""

    def test_unavailable_is_an_assistant_error(self):
        """
        GIVEN AssistantUnavailableError
        WHEN its bases are inspected
        THEN it is an AssistantError
        """
        assert issubclass(AssistantUnavailableError, AssistantError)

    def test_rate_limited_is_an_assistant_error(self):
        """
        GIVEN AssistantRateLimitedError
        WHEN its bases are inspected
        THEN it is an AssistantError
        """
        assert issubclass(AssistantRateLimitedError, AssistantError)

    def test_busy_is_an_assistant_error_and_carries_retry_after(self):
        """
        GIVEN AssistantBusyError built with a wait of 5 seconds and the process limit
        WHEN its bases and attributes are inspected
        THEN it is an AssistantError, apart from the unavailable error, and holds the wait and
             the limit that refused
        """
        # GIVEN
        error = AssistantBusyError("the assistant is full", retry_after=5, reason="process")

        # THEN
        assert issubclass(AssistantBusyError, AssistantError)
        assert not issubclass(AssistantBusyError, AssistantUnavailableError)
        assert error.retry_after == 5
        assert error.reason == "process"
        assert str(error) == "the assistant is full"

    def test_unavailable_and_upstream_are_distinguishable(self):
        """
        GIVEN AssistantUnavailableError and AssistantUpstreamError
        WHEN checked against each other
        THEN neither is a subclass of the other, so a handler can tell them apart
        """
        assert not issubclass(AssistantUnavailableError, AssistantUpstreamError)
        assert not issubclass(AssistantUpstreamError, AssistantUnavailableError)
