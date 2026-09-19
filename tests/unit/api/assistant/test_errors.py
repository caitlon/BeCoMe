"""Unit tests for the assistant's exception hierarchy."""

from api.assistant.errors import AssistantError, AssistantNotFoundError, AssistantUpstreamError
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
