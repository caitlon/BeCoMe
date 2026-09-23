"""Unit tests for the chat/embeddings model factories (fakes only, no network)."""

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from api.assistant.rag.models import make_chat_model, make_embeddings
from api.config import Settings


class TestMakeChatModel:
    """make_chat_model points a ChatOpenAI client at the local chat llama-server."""

    def test_builds_a_chat_client_from_settings(self):
        """
        GIVEN default Settings
        WHEN make_chat_model builds a client
        THEN it targets the configured base URL, model, and timeout
        """
        # GIVEN
        settings = Settings(secret_key="test-secret-key")

        # WHEN
        model = make_chat_model(settings)

        # THEN
        assert isinstance(model, ChatOpenAI)
        assert model.openai_api_base == settings.assistant_llm_base_url
        assert model.model_name == settings.assistant_llm_model
        assert model.request_timeout == settings.assistant_llm_timeout_seconds


class TestMakeEmbeddings:
    """make_embeddings points an OpenAIEmbeddings client at the local embedding role."""

    def test_builds_an_embeddings_client_with_ctx_length_check_disabled(self):
        """
        GIVEN default Settings
        WHEN make_embeddings builds a client
        THEN it targets the configured base URL and model, with
             check_embedding_ctx_length disabled (required for llama-server)
        """
        # GIVEN
        settings = Settings(secret_key="test-secret-key")

        # WHEN
        embeddings = make_embeddings(settings)

        # THEN
        assert isinstance(embeddings, OpenAIEmbeddings)
        assert embeddings.openai_api_base == settings.assistant_embedding_base_url
        assert embeddings.model == settings.assistant_embedding_model
        assert embeddings.check_embedding_ctx_length is False
