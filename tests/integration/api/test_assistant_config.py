"""The shared test application mounts the assistant only when the feature flag is on."""

import pytest

from api.config import Settings, get_settings
from tests.integration.api.conftest import create_test_app


@pytest.fixture(autouse=True)
def _local_providers(monkeypatch):
    """Keep a developer's own shell and .env out of the provider and base URL settings.

    An environment variable beats .env, so pinning the providers and the three base URLs
    (to the code defaults) here covers both.
    """
    monkeypatch.delenv("ASSISTANT_API_KEY_OVH", raising=False)
    for name in ("ANSWER", "LLM", "EMBEDDING"):
        monkeypatch.setenv(f"ASSISTANT_{name}_PROVIDER", "local")
    for field in (
        "assistant_answer_llm_base_url",
        "assistant_llm_base_url",
        "assistant_embedding_base_url",
    ):
        monkeypatch.setenv(field.upper(), Settings.model_fields[field].default)


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

    def test_config_endpoint_reports_every_role_as_local_by_default(
        self, assistant_settings, client
    ):
        """
        GIVEN the test app with the flag on and no provider switched
        WHEN the config endpoint is requested
        THEN the answer, query and embedding providers are all local
        """
        # WHEN
        body = client.get("/api/v1/assistant/config").json()

        # THEN
        assert body["answer_provider"] == "local"
        assert body["query_provider"] == "local"
        assert body["embedding_provider"] == "local"

    def test_config_endpoint_reports_a_role_on_the_api_without_a_key_or_a_url(
        self, assistant_settings, client, monkeypatch
    ):
        """
        GIVEN settings with the answer role on the hosted API, a key and a remote URL
        WHEN the config endpoint is requested
        THEN the answer provider reads api, the others stay local, and neither the key nor
             the URL appears anywhere in the body
        """
        # GIVEN
        key = "ovh-test-key"  # pragma: allowlist secret
        url = "https://models.example.test/v1"
        monkeypatch.setenv("ASSISTANT_API_KEY_OVH", key)
        monkeypatch.setenv("ASSISTANT_ANSWER_PROVIDER", "api")
        monkeypatch.setenv("ASSISTANT_ANSWER_LLM_BASE_URL", url)
        get_settings.cache_clear()

        # WHEN
        response = client.get("/api/v1/assistant/config")

        # THEN
        body = response.json()
        assert (body["answer_provider"], body["query_provider"], body["embedding_provider"]) == (
            "api",
            "local",
            "local",
        )
        assert key not in response.text
        assert url not in response.text


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
