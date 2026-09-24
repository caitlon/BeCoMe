"""Unit tests for the chat, embeddings, and reranker model clients (fakes only, no network)."""

import httpx
import pytest
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from api.assistant.rag.models import LlamaServerReranker, make_chat_model, make_embeddings
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


class _FakeResponse:
    """Stands in for httpx.Response: only raise_for_status() and json() are used."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient, recording the request and its own response."""

    last_request: dict | None = None

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False

    async def post(self, url: str, json: dict) -> _FakeResponse:
        _FakeAsyncClient.last_request = {"url": url, "json": json}
        return _FakeResponse(
            {
                "results": [
                    {"index": 1, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.2},
                ]
            }
        )


class _FakeAsyncClientOutOfRangeIndex:
    """Stands in for httpx.AsyncClient, returning a result index past the input texts."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeAsyncClientOutOfRangeIndex":
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False

    async def post(self, url: str, json: dict) -> _FakeResponse:
        return _FakeResponse({"results": [{"index": 5, "relevance_score": 0.9}]})


class _FakeAsyncClientMissingIndex:
    """Stands in for httpx.AsyncClient, returning fewer results than input texts."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeAsyncClientMissingIndex":
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False

    async def post(self, url: str, json: dict) -> _FakeResponse:
        return _FakeResponse({"results": [{"index": 0, "relevance_score": 0.9}]})


class _FakeAsyncClientDuplicateIndex:
    """Stands in for httpx.AsyncClient, scoring the same index twice."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeAsyncClientDuplicateIndex":
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False

    async def post(self, url: str, json: dict) -> _FakeResponse:
        return _FakeResponse(
            {
                "results": [
                    {"index": 0, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.2},
                ]
            }
        )


class TestLlamaServerReranker:
    """Async client for llama-server's /v1/rerank endpoint."""

    @pytest.mark.asyncio
    async def test_rerank_returns_scores_aligned_to_input_order(self, monkeypatch):
        """
        GIVEN a fake llama-server whose response lists results out of input order
        WHEN rerank() scores two texts
        THEN scores come back aligned to the INPUT order, not the response order,
             and the request body carries model/query/documents as llama-server expects
        """
        # GIVEN
        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
        reranker = LlamaServerReranker(
            base_url="http://127.0.0.1:8083/v1", model="BAAI/bge-reranker-v2-m3", timeout=5.0
        )

        # WHEN
        scores = await reranker.rerank("query", ["doc a", "doc b"])

        # THEN
        assert scores == [0.2, 0.9]
        assert _FakeAsyncClient.last_request == {
            "url": "http://127.0.0.1:8083/v1/rerank",
            "json": {
                "model": "BAAI/bge-reranker-v2-m3",
                "query": "query",
                "documents": ["doc a", "doc b"],
            },
        }

    @pytest.mark.asyncio
    async def test_rerank_rejects_a_result_index_outside_the_input_range(self, monkeypatch):
        """
        GIVEN a fake llama-server whose response names an index past the input texts
        WHEN rerank() scores the texts
        THEN it raises ValueError naming the bad index, not an IndexError
        """
        # GIVEN
        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClientOutOfRangeIndex)
        reranker = LlamaServerReranker(
            base_url="http://127.0.0.1:8083/v1", model="BAAI/bge-reranker-v2-m3", timeout=5.0
        )

        # WHEN / THEN
        with pytest.raises(ValueError, match="index 5"):
            await reranker.rerank("query", ["doc a", "doc b"])

    @pytest.mark.asyncio
    async def test_rerank_rejects_a_response_that_leaves_an_index_unscored(self, monkeypatch):
        """
        GIVEN a fake llama-server whose response holds fewer results than input texts
        WHEN rerank() scores three texts
        THEN it raises ValueError naming the unscored indices, instead of returning a
             fabricated 0.0 score for the texts the server never mentioned
        """
        # GIVEN
        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClientMissingIndex)
        reranker = LlamaServerReranker(
            base_url="http://127.0.0.1:8083/v1", model="BAAI/bge-reranker-v2-m3", timeout=5.0
        )

        # WHEN / THEN
        with pytest.raises(ValueError, match=r"\[1, 2\]"):
            await reranker.rerank("query", ["doc a", "doc b", "doc c"])

    @pytest.mark.asyncio
    async def test_rerank_rejects_a_duplicated_result_index(self, monkeypatch):
        """
        GIVEN a fake llama-server whose response scores the same index twice
        WHEN rerank() scores two texts
        THEN it raises ValueError naming the duplicated index, instead of silently
             overwriting the earlier score with the later one
        """
        # GIVEN
        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClientDuplicateIndex)
        reranker = LlamaServerReranker(
            base_url="http://127.0.0.1:8083/v1", model="BAAI/bge-reranker-v2-m3", timeout=5.0
        )

        # WHEN / THEN
        with pytest.raises(ValueError, match="index 0"):
            await reranker.rerank("query", ["doc a", "doc b"])
