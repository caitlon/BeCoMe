"""Unit tests for the chat, embeddings, and reranker model clients (fakes only, no network)."""

import json

import httpx
import pytest
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from api.assistant.rag.models import (
    LlamaServerReranker,
    has_unclosed_think_block,
    make_answer_model,
    make_chat_model,
    make_embeddings,
    strip_think_block,
)
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


class TestMakeAnswerModel:
    """make_answer_model points a ChatOpenAI client at the local answer llama-server."""

    def test_builds_an_answer_client_from_settings(self):
        """
        GIVEN default Settings
        WHEN make_answer_model builds a client
        THEN it targets the answer model's base URL and name, is deterministic, caps the
             reply at the configured tokens, never retries a failed request, and asks
             for the usage on the last streamed chunk
        """
        # GIVEN
        settings = _settings()

        # WHEN
        model = make_answer_model(settings)

        # THEN
        assert isinstance(model, ChatOpenAI)
        assert model.openai_api_base == settings.assistant_answer_llm_base_url
        assert model.model_name == settings.assistant_answer_llm_model
        assert model.temperature == 0
        assert model.max_tokens == settings.assistant_answer_max_tokens
        assert model.max_retries == 0
        assert model.stream_usage is True
        assert model.request_timeout == settings.assistant_llm_timeout_seconds

    def test_follows_the_answer_settings_not_the_query_model_ones(self):
        """
        GIVEN Settings with a distinct answer model and token cap
        WHEN make_answer_model and make_chat_model build clients
        THEN the answer client uses the answer settings and the chat client keeps the
             query-transform ones
        """
        # GIVEN
        settings = _settings(
            assistant_answer_llm_base_url="http://127.0.0.1:9999/v1",
            assistant_answer_llm_model="answer-model",
            assistant_answer_max_tokens=123,
        )

        # WHEN
        answer = make_answer_model(settings)
        chat = make_chat_model(settings)

        # THEN
        assert answer.openai_api_base == "http://127.0.0.1:9999/v1"
        assert answer.model_name == "answer-model"
        assert answer.max_tokens == 123
        assert chat.openai_api_base == settings.assistant_llm_base_url
        assert chat.model_name == settings.assistant_llm_model
        assert chat.max_tokens is None


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

    def test_bounds_the_client_by_the_chat_model_timeout(self):
        """
        GIVEN default Settings
        WHEN make_embeddings builds a client
        THEN its request timeout is settings.assistant_llm_timeout_seconds - there is
             no separate embedding timeout setting, so the chat one bounds it too
        """
        # GIVEN
        settings = Settings(secret_key="test-secret-key")

        # WHEN
        embeddings = make_embeddings(settings)

        # THEN
        assert embeddings.request_timeout == settings.assistant_llm_timeout_seconds

    def test_sends_at_most_64_texts_per_request(self):
        """
        GIVEN default Settings
        WHEN make_embeddings builds a client
        THEN its chunk_size is 64, so llama-server answers one small batch instead
             of the whole corpus, keeping each request's timeout bound small
        """
        # GIVEN
        settings = Settings(secret_key="test-secret-key")

        # WHEN
        embeddings = make_embeddings(settings)

        # THEN
        assert embeddings.chunk_size == 64


_API_KEY = "ovh-test-key"  # pragma: allowlist secret
_REMOTE_URL = "https://models.example.test/v1"
_BASE_URL_SETTINGS = (
    "assistant_answer_llm_base_url",
    "assistant_llm_base_url",
    "assistant_embedding_base_url",
)


def _settings(**overrides) -> Settings:
    """Settings with every role local at its default URL, unless an override says otherwise.

    Init arguments beat the environment and .env, so a developer who points a role at a
    hosted provider in their own .env does not change what these tests build.
    """
    isolated = {
        "assistant_answer_provider": "local",
        "assistant_llm_provider": "local",
        "assistant_embedding_provider": "local",
        "assistant_api_key_ovh": None,
        "assistant_api_reasoning_effort": "none",
        **{name: Settings.model_fields[name].default for name in _BASE_URL_SETTINGS},
    }
    return Settings(
        secret_key="test-secret-key",  # pragma: allowlist secret
        **{**isolated, **overrides},
    )


def _api_settings(**overrides) -> Settings:
    """Settings with every role on the hosted API, at a remote URL, with a key."""
    return _settings(
        assistant_api_key_ovh=_API_KEY,
        assistant_answer_provider="api",
        assistant_llm_provider="api",
        assistant_embedding_provider="api",
        assistant_answer_llm_base_url=_REMOTE_URL,
        assistant_llm_base_url=_REMOTE_URL,
        assistant_embedding_base_url=_REMOTE_URL,
        **overrides,
    )


class TestApiProvider:
    """A role on the hosted API sends the key and, for chat models, switches reasoning off."""

    @pytest.mark.parametrize("make", [make_chat_model, make_answer_model])
    def test_a_chat_client_carries_the_key_and_the_reasoning_switch(self, make):
        """
        GIVEN settings with the answer and query roles on the hosted API
        WHEN a chat client is built
        THEN it holds the configured key instead of the local placeholder and sends
             reasoning_effort none in the request body
        """
        # GIVEN
        settings = _api_settings()

        # WHEN
        model = make(settings)

        # THEN
        assert model.openai_api_key is not None
        assert model.openai_api_key.get_secret_value() == _API_KEY
        assert model.extra_body == {"reasoning_effort": "none"}

    @pytest.mark.parametrize("make", [make_chat_model, make_answer_model])
    @pytest.mark.parametrize(
        ("effort", "expected"),
        [("low", {"reasoning_effort": "low"}), (None, None)],
    )
    def test_the_reasoning_switch_follows_the_setting(self, make, effort, expected):
        """
        GIVEN settings with the hosted API and a reasoning effort of low, or none at all
        WHEN a chat client is built
        THEN it sends that effort, or no extra body when the setting is None
        """
        # GIVEN
        settings = _api_settings(assistant_api_reasoning_effort=effort)

        # WHEN
        model = make(settings)

        # THEN
        assert model.extra_body == expected

    def test_the_embeddings_client_carries_the_key(self):
        """
        GIVEN settings with the embedding role on the hosted API
        WHEN make_embeddings builds a client
        THEN it holds the configured key
        """
        # GIVEN
        settings = _api_settings()

        # WHEN
        embeddings = make_embeddings(settings)

        # THEN
        assert embeddings.openai_api_key is not None
        assert embeddings.openai_api_key.get_secret_value() == _API_KEY

    def test_the_answer_client_keeps_its_other_settings_in_api_mode(self):
        """
        GIVEN settings with the answer role on the hosted API
        WHEN make_answer_model builds a client
        THEN it is still deterministic, capped, asks for the usage on the last chunk, and
             retries twice because the hosted API fails now and then
        """
        # GIVEN
        settings = _api_settings()

        # WHEN
        model = make_answer_model(settings)

        # THEN
        assert model.openai_api_base == _REMOTE_URL
        assert model.temperature == 0
        assert model.max_tokens == settings.assistant_answer_max_tokens
        assert model.stream_usage is True
        assert model.max_retries == 2

    def test_each_role_follows_its_own_provider(self):
        """
        GIVEN only the answer role on the hosted API
        WHEN the three clients are built
        THEN the other two keep the local placeholder key and send no reasoning switch
        """
        # GIVEN
        settings = _settings(
            assistant_api_key_ovh=_API_KEY,
            assistant_answer_provider="api",
            assistant_answer_llm_base_url=_REMOTE_URL,
        )

        # WHEN
        answer = make_answer_model(settings)
        chat = make_chat_model(settings)
        embeddings = make_embeddings(settings)

        # THEN
        assert answer.openai_api_key.get_secret_value() == _API_KEY
        assert chat.openai_api_key.get_secret_value() == "not-needed"
        assert chat.extra_body is None
        assert embeddings.openai_api_key.get_secret_value() == "not-needed"

    @pytest.mark.parametrize("make", [make_chat_model, make_answer_model])
    def test_a_call_carries_a_bearer_header_and_the_reasoning_switch(self, make):
        """
        GIVEN an api-mode chat client whose HTTP transport is a recording fake
        WHEN it is invoked
        THEN the request carries Authorization: Bearer with the key, and a body that holds
             reasoning_effort none
        """
        # GIVEN
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(
                200,
                json={
                    "id": "c",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "m",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "ok"},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )

        model = make(_api_settings())
        model.root_client._client = httpx.Client(transport=httpx.MockTransport(handler))

        # WHEN
        reply = model.invoke("hello")

        # THEN
        assert reply.content == "ok"
        assert seen[0].headers["authorization"] == f"Bearer {_API_KEY}"
        assert json.loads(seen[0].content)["reasoning_effort"] == "none"

    def test_an_embeddings_call_carries_a_bearer_header(self):
        """
        GIVEN an api-mode embeddings client whose HTTP transport is a recording fake
        WHEN it embeds a query
        THEN the request carries Authorization: Bearer with the key
        """
        # GIVEN
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "model": "m",
                    "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
                    "usage": {"prompt_tokens": 1, "total_tokens": 1},
                },
            )

        embeddings = make_embeddings(_api_settings())
        embeddings.client._client._client = httpx.Client(transport=httpx.MockTransport(handler))

        # WHEN
        vector = embeddings.embed_query("hello")

        # THEN
        assert vector == [0.1, 0.2]
        assert seen[0].headers["authorization"] == f"Bearer {_API_KEY}"


class TestLocalProviderIsUnchanged:
    """A role on the local server keeps the placeholder key and no extra body."""

    def test_local_clients_hold_the_placeholder_key_and_send_no_reasoning_switch(self):
        """
        GIVEN default settings, every role local
        WHEN the three clients are built
        THEN each holds the placeholder key, the chat clients send no extra body, and the
             answer client still never retries
        """
        # GIVEN
        settings = _settings()

        # WHEN
        answer = make_answer_model(settings)
        chat = make_chat_model(settings)
        embeddings = make_embeddings(settings)

        # THEN
        for client in (answer, chat, embeddings):
            assert client.openai_api_key.get_secret_value() == "not-needed"
        assert answer.extra_body is None
        assert chat.extra_body is None
        assert answer.max_retries == 0


class TestStripThinkBlock:
    """strip_think_block removes a reasoning-capable model's <think> preamble."""

    def test_removes_a_leading_think_block(self):
        """
        GIVEN a reply with a <think>...</think> block before the actual answer
        WHEN strip_think_block runs
        THEN only the text after the block remains, stripped of surrounding whitespace
        """
        # GIVEN
        reply = "<think>Reasoning about the answer.</think>\n\nThe actual answer."

        # WHEN
        result = strip_think_block(reply)

        # THEN
        assert result == "The actual answer."

    def test_leaves_a_reply_with_no_think_block_only_stripped(self):
        """
        GIVEN a reply with no <think> block at all
        WHEN strip_think_block runs
        THEN the reply comes back with only its surrounding whitespace removed
        """
        # GIVEN
        reply = "  The actual answer.  "

        # WHEN
        result = strip_think_block(reply)

        # THEN
        assert result == "The actual answer."

    def test_keeps_a_reply_whose_think_block_never_closes(self):
        """
        GIVEN a reply that opens a <think> block and never closes it
        WHEN strip_think_block runs
        THEN the reply is kept as it is, since only a complete block is removed
        """
        # GIVEN
        reply = "<think>Still reasoning about the answer"

        # WHEN
        result = strip_think_block(reply)

        # THEN
        assert result == "<think>Still reasoning about the answer"


class TestHasUnclosedThinkBlock:
    """has_unclosed_think_block says whether the last <think> block of a reply never closes."""

    @pytest.mark.parametrize(
        "reply",
        [
            "<think>Still reasoning",
            "Half an answer <think>and then",
            "<think>a</think>Text <think>b",
            "<think>a</think>One <think>b</think> two <think>c",
            "Text </think> then <think>c",
        ],
    )
    def test_true_when_the_last_block_never_closes(self, reply):
        """
        GIVEN a reply whose last <think> block has no closing tag after it
        WHEN the check runs
        THEN it reports an unclosed block
        """
        assert has_unclosed_think_block(reply) is True

    @pytest.mark.parametrize(
        "reply",
        [
            "",
            "Plain answer.",
            " Plain answer, </think> here. ",
            "<think>x</think>Answer.",
            "<think>a</think>Text <think>b</think> tail",
        ],
    )
    def test_false_when_every_block_closes_or_there_is_none(self, reply):
        """
        GIVEN a reply with no <think> block, or whose blocks all close
        WHEN the check runs
        THEN it reports no unclosed block, a stray closing tag included
        """
        assert has_unclosed_think_block(reply) is False


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
