"""The shared test application mounts the assistant only when the feature flag is on."""

import pytest

from tests.integration.api.conftest import create_test_app


class TestAssistantRouterGating:
    """The whole /assistant/* prefix follows assistant_enabled, like every other route."""

    def test_config_endpoint_404s_when_the_flag_is_off(self, client):
        """
        GIVEN the shared test app built with the flag off
        WHEN the config endpoint is requested
        THEN the prefix is unrouted, so the answer is 404
        """
        # WHEN
        response = client.get("/api/v1/assistant/config")

        # THEN
        assert response.status_code == 404

    def test_config_endpoint_answers_when_the_flag_is_on(self, assistant_settings, client):
        """
        GIVEN the shared test app built with the flag on
        WHEN the config endpoint is requested
        THEN it answers 200 and reports the assistant as enabled
        """
        # WHEN
        response = client.get("/api/v1/assistant/config")

        # THEN
        assert response.status_code == 200
        assert response.json()["enabled"] is True


class TestTestAppMirrorsTheMainApp:
    """With the flag on, the test app registers what api/main.py registers for the assistant."""

    def test_the_assistant_error_handlers_are_registered(self, assistant_settings):
        """
        GIVEN the flag on
        WHEN the test app is built
        THEN the rate-limited, unavailable and upstream errors each have their own handler
        """
        from api.assistant import exception_handlers
        from api.assistant.errors import (
            AssistantRateLimitedError,
            AssistantUnavailableError,
            AssistantUpstreamError,
        )

        # WHEN
        handlers = create_test_app().exception_handlers

        # THEN
        assert (
            handlers[AssistantRateLimitedError] is exception_handlers.assistant_rate_limited_handler
        )
        assert (
            handlers[AssistantUnavailableError] is exception_handlers.assistant_unavailable_handler
        )
        assert handlers[AssistantUpstreamError] is exception_handlers.assistant_upstream_handler

    def test_no_assistant_handler_is_registered_when_the_flag_is_off(self):
        """
        GIVEN the flag off
        WHEN the test app is built
        THEN no assistant error class has a handler of its own
        """
        from api.assistant.errors import AssistantError

        # WHEN
        handlers = create_test_app().exception_handlers

        # THEN
        assert [cls for cls in handlers if issubclass(cls, AssistantError)] == []

    @pytest.mark.asyncio
    async def test_the_retriever_is_replaced_by_a_static_one(self, assistant_settings):
        """
        GIVEN the flag on
        WHEN the test app's override for the documentation retriever is called
        THEN it returns a fixed, empty retriever, so no test reaches a real vector database
        """
        from api.assistant.deps import get_docs_retriever
        from tests.shared.assistant_fakes import StaticDocsRetriever

        # WHEN
        retriever = create_test_app().dependency_overrides[get_docs_retriever]()

        # THEN
        assert isinstance(retriever, StaticDocsRetriever)
        assert await retriever.search("anything") == []
