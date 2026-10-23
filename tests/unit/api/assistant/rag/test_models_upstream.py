"""A model, embedding or rerank server that answers 200 with a body that is no answer.

The clients here are real ones with a fake HTTP transport: nothing reaches a network. What
each must do is raise ``MalformedModelResponseError`` for such a body, tag every failure
with the role of the server it came from, and leave a bug of our own as it is.
"""

import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import openai
import pytest
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import tool
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import ChatOpenAI

from api.assistant.agent.context import AssistantContext, SourceRegistry
from api.assistant.agent.service import AssistantService
from api.assistant.client import UserApiClient
from api.assistant.errors import AssistantUnavailableError
from api.assistant.rag.models import (
    LlamaServerReranker,
    MalformedModelResponseError,
    make_answer_model,
    make_chat_model,
    make_embeddings,
)
from api.assistant.rag.retrieval import DocsRetriever, RetrievalConfig
from api.assistant.roles import tagged_role
from api.config import Settings
from api.schemas.assistant import AssistantChatRequest
from tests.shared.assistant_fakes import ScriptedToolCallingModel
from tests.shared.helpers import captured_log_records


def _json_bytes(content: bytes) -> httpx.Response:
    """A 200 that says it is JSON and holds these bytes, whatever they are."""
    return httpx.Response(200, headers={"content-type": "application/json"}, content=content)


_HTML = httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>oops</html>")
_MALFORMED_BODIES = {
    "html": _HTML,
    "error object": httpx.Response(200, json={"error": {"message": "boom"}}),
    "no choices": httpx.Response(200, json={"id": "c", "model": "m"}),
    "null choices": httpx.Response(200, json={"id": "c", "choices": None}),
    "empty choices": httpx.Response(200, json={"id": "c", "choices": []}),
    "choice without message": httpx.Response(200, json={"id": "c", "choices": [{"index": 0}]}),
    "empty json body": _json_bytes(b""),
    "html in a json reply": _json_bytes(b"<html>bad gateway</html>"),
    "truncated json": _json_bytes(b'{"id":"c","choices":[{"index":0,"mess'),
    "json cut inside a character": _json_bytes(
        '{"choices":[{"message":{"content":"Př'.encode()[:-1]
    ),
}

_CHUNK = (
    'data: {"id":"c","object":"chat.completion.chunk","created":0,"model":"m",'
    '"choices":[{"index":0,"delta":{"role":"assistant","content":"One "}}]}\n\n'
)
_BAD_STREAMS = {
    "html": "data: <html>bad gateway</html>\n\n",
    "choices that is a string": 'data: {"choices":"x"}\n\n',
    "a delta that is a string": 'data: {"choices":[{"index":0,"delta":"x"}]}\n\n',
    "a content that is a number": ('data: {"choices":[{"index":0,"delta":{"content":5}}]}\n\n'),
    "choices that is an object": 'data: {"choices":{"a":1}}\n\n',
    "a lone choice without a delta, skipped, so no chunk at all": 'data: {"choices":[{}]}\n\n',
    "a good chunk, then html": _CHUNK + "data: <html>\n\n",
    "a good chunk, then a string choices": _CHUNK + 'data: {"choices":"x"}\n\n',
    "a chunk cut inside a character": (
        'data: {"choices":[{"index":0,"delta":{"content":"Př'.encode()[:-1] + b"\n\n"
    ),
}


def _settings() -> Settings:
    return Settings(
        secret_key="test-secret-key",  # pragma: allowlist secret
        assistant_answer_provider="local",
        assistant_llm_provider="local",
        assistant_embedding_provider="local",
        assistant_api_key_ovh=None,
    )


def _transport(response: httpx.Response | Exception) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(response, Exception):
            raise response
        # A fresh response each time: one cannot be read by a sync and an async client.
        return httpx.Response(
            response.status_code, headers=response.headers, content=response.content
        )

    return httpx.MockTransport(handler)


def _wire(model, response: httpx.Response | Exception):
    """Point a chat model's clients, sync and async, at a transport that answers `response`."""
    transport = _transport(response)
    client = openai.AsyncOpenAI(
        api_key="unused",  # pragma: allowlist secret
        base_url="http://model.test/v1",
        http_client=httpx.AsyncClient(transport=transport),
        max_retries=0,
    )
    model.root_async_client = client
    model.async_client = client.chat.completions
    sync_client = openai.OpenAI(
        api_key="unused",  # pragma: allowlist secret
        base_url="http://model.test/v1",
        http_client=httpx.Client(transport=transport),
        max_retries=0,
    )
    model.root_client = sync_client
    model.client = sync_client.chat.completions
    return model


_ROLES: list[tuple[str, Callable[[Settings], Any], str]] = [
    ("answer", make_answer_model, "answer"),
    ("query", make_chat_model, "query"),
]


@pytest.fixture(params=_ROLES, ids=[name for name, _, _ in _ROLES])
def role_model(request):
    """A factory for the answer and the query model, and the role each must report."""
    _, make, role = request.param
    return make, role


@pytest.mark.parametrize("response", _MALFORMED_BODIES.values(), ids=_MALFORMED_BODIES.keys())
class TestChatModelMalformedBody:
    """A 200 whose body is not a chat completion is the server's fault, in either call style."""

    @pytest.mark.asyncio
    async def test_an_async_call_raises_the_dedicated_error_tagged_with_the_role(
        self, role_model, response
    ):
        """
        GIVEN a chat model whose server answers 200 with a body that is no chat completion
        WHEN it is invoked
        THEN MalformedModelResponseError is raised, tagged with the model's role
        """
        make, role = role_model
        model = _wire(make(_settings()), response)

        with pytest.raises(MalformedModelResponseError) as raised:
            await model.ainvoke("hi")

        assert tagged_role(raised.value) == role

    def test_a_sync_call_raises_the_same_error(self, role_model, response):
        """
        GIVEN the same model
        WHEN it is invoked synchronously
        THEN MalformedModelResponseError is raised, tagged with the role
        """
        make, role = role_model
        model = _wire(make(_settings()), response)

        with pytest.raises(MalformedModelResponseError) as raised:
            model.invoke("hi")

        assert tagged_role(raised.value) == role

    @pytest.mark.asyncio
    async def test_a_model_bound_to_tools_or_options_keeps_the_behaviour(
        self, role_model, response
    ):
        """
        GIVEN a model bound to a tool, as the agent loop binds it, and bound to an option,
            as query translation binds it
        WHEN either is invoked
        THEN each raises MalformedModelResponseError, tagged with the model's role
        """

        @tool
        def lookup(query: str) -> str:
            """Look something up."""
            return query

        make, role = role_model
        model = _wire(make(_settings()), response)

        for bound in (model.bind_tools([lookup]), model.bind(temperature=0)):
            with pytest.raises(MalformedModelResponseError) as raised:
                await bound.ainvoke("hi")
            assert tagged_role(raised.value) == role


class TestChatModelOtherFailures:
    """What is not a malformed body keeps its type, and a bug of ours is not turned into one."""

    @pytest.mark.asyncio
    async def test_a_connection_failure_keeps_its_type_and_carries_the_role(self, role_model):
        """
        GIVEN a chat model whose server cannot be reached
        WHEN it is invoked
        THEN openai.APIConnectionError is raised, tagged with the model's role
        """
        make, role = role_model
        model = _wire(make(_settings()), httpx.ConnectError("refused"))

        with pytest.raises(openai.APIConnectionError) as raised:
            await model.ainvoke("hi")

        assert tagged_role(raised.value) == role

    @pytest.mark.asyncio
    async def test_a_value_error_of_our_own_is_not_turned_into_the_dedicated_error(
        self, monkeypatch
    ):
        """
        GIVEN a model that fails with a ValueError while it builds the request, which is
            our side of the call and not the server's answer
        WHEN it is invoked
        THEN the ValueError reaches the caller as it is
        """
        model = _wire(make_answer_model(_settings()), _HTML)

        def broken(*args, **kwargs):
            raise ValueError("bug")

        monkeypatch.setattr(type(model), "_get_request_payload", broken)

        with pytest.raises(ValueError, match="bug") as raised:
            await model.ainvoke("hi")

        assert not isinstance(raised.value, MalformedModelResponseError)

    @pytest.mark.asyncio
    async def test_an_error_that_is_not_a_body_shape_error_passes_through_untouched(
        self, monkeypatch
    ):
        """
        GIVEN a model whose reading of the body fails with a RuntimeError, which no server
            body can cause
        WHEN it is invoked
        THEN the RuntimeError reaches the caller as it is, not as the dedicated error
        """
        model = _wire(make_answer_model(_settings()), _HTML)

        def broken(*args, **kwargs):
            raise RuntimeError("bug")

        monkeypatch.setattr(ChatOpenAI, "_create_chat_result", broken)

        with pytest.raises(RuntimeError, match="bug"):
            await model.ainvoke("hi")

    def test_the_runs_keep_the_name_of_the_library_class(self, role_model):
        """
        GIVEN a chat model built by either factory
        WHEN its runnable name is read, which is the name of its runs in a trace
        THEN it is ChatOpenAI, not the name of the subclass
        """
        make, _ = role_model

        assert make(_settings()).get_name() == "ChatOpenAI"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("stream", _BAD_STREAMS.values(), ids=_BAD_STREAMS.keys())
    async def test_a_stream_with_a_bad_chunk_is_malformed(self, role_model, stream):
        """
        GIVEN a chat model whose streaming server sends a chunk that is not a completion
            chunk, first or after a good one
        WHEN it is streamed
        THEN MalformedModelResponseError is raised, tagged with the role, whether the
            chunk is not JSON or is JSON of the wrong shape
        """
        make, role = role_model
        reply = httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=stream if isinstance(stream, bytes) else stream.encode(),
        )
        model = _wire(make(_settings()), reply)

        with pytest.raises(MalformedModelResponseError) as raised:
            [piece async for piece in model.astream("hi")]

        assert tagged_role(raised.value) == role

    @pytest.mark.asyncio
    async def test_a_value_error_of_our_own_in_a_stream_is_not_turned_into_the_dedicated_error(
        self, monkeypatch
    ):
        """
        GIVEN a model that fails with a ValueError while it builds a streamed request
        WHEN it is streamed
        THEN the ValueError reaches the caller as it is
        """
        model = _wire(make_answer_model(_settings()), _HTML)

        def broken(*args, **kwargs):
            raise ValueError("bug")

        monkeypatch.setattr(type(model), "_get_request_payload", broken)

        with pytest.raises(ValueError, match="bug") as raised:
            [piece async for piece in model.astream("hi")]

        assert not isinstance(raised.value, MalformedModelResponseError)

    @pytest.mark.asyncio
    async def test_a_message_the_library_cannot_send_is_not_a_malformed_reply(self, role_model):
        """
        GIVEN a streamed call whose input holds a message of a type the library cannot turn
            into a request, so that it fails with a TypeError before any request is sent
        WHEN it is streamed
        THEN the TypeError reaches the caller as it is
        """
        make, _ = role_model
        model = _wire(make(_settings()), _json_bytes(b"{}"))
        odd = BaseMessage(content="hi", type="odd")

        with pytest.raises(TypeError) as raised:
            [piece async for piece in model.astream([odd])]

        assert not isinstance(raised.value, MalformedModelResponseError)

    @pytest.mark.asyncio
    async def test_an_attribute_error_while_the_request_is_built_is_not_a_malformed_reply(
        self, monkeypatch
    ):
        """
        GIVEN a streamed call whose request building fails with an AttributeError, which is
            also what a chunk that is not an object makes the library raise
        WHEN it is streamed
        THEN the AttributeError reaches the caller as it is
        """
        model = _wire(make_answer_model(_settings()), _json_bytes(b"{}"))

        def broken(*args, **kwargs):
            raise AttributeError("a bug")

        monkeypatch.setattr(type(model), "_get_request_payload", broken)

        with pytest.raises(AttributeError, match="a bug"):
            [piece async for piece in model.astream("hi")]

    @pytest.mark.asyncio
    async def test_a_callback_that_raises_is_not_a_malformed_reply(self, role_model):
        """
        GIVEN a streamed call, with a good reply, whose callback raises an AttributeError
            when it is handed a token
        WHEN it is streamed
        THEN the AttributeError reaches the caller as it is
        """

        class Failing(AsyncCallbackHandler):
            raise_error = True

            async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
                raise AttributeError("a bug in the callback")

        make, _ = role_model
        good = httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=_CHUNK.encode()
        )
        model = _wire(make(_settings()), good)

        with pytest.raises(AttributeError, match="a bug in the callback"):
            [piece async for piece in model.astream("hi", config={"callbacks": [Failing()]})]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "stream", ["data: [1]\n\n", _CHUNK + "data: [1]\n\n"], ids=["first", "after a good one"]
    )
    async def test_a_chunk_that_is_json_but_not_an_object_is_not_caught(self, role_model, stream):
        """
        GIVEN a streaming server that sends a chunk that is valid JSON but not an object
        WHEN it is streamed
        THEN the library's own AttributeError reaches the caller: this shape is not caught
        """
        make, _ = role_model
        reply = httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=stream.encode()
        )
        model = _wire(make(_settings()), reply)

        with pytest.raises(AttributeError):
            [piece async for piece in model.astream("hi")]

    @pytest.mark.asyncio
    async def test_a_stream_that_is_html_is_malformed(self, role_model):
        """
        GIVEN a chat model whose streaming server answers 200 with an HTML page, so that
            the stream holds no chunk
        WHEN it is streamed
        THEN MalformedModelResponseError is raised, tagged with the role, and not the bare
            ValueError LangChain raises for a stream with no chunks
        """
        make, role = role_model
        model = _wire(make(_settings()), _HTML)

        with pytest.raises(MalformedModelResponseError) as raised:
            [piece async for piece in model.astream("hi")]

        assert tagged_role(raised.value) == role

    @pytest.mark.asyncio
    async def test_a_failing_stream_is_tagged_with_the_role(self, role_model):
        """
        GIVEN a chat model whose streaming server cannot be reached
        WHEN it is streamed
        THEN openai.APIConnectionError is raised, tagged with the model's role
        """
        make, role = role_model
        model = _wire(make(_settings()), httpx.ConnectError("refused"))

        with pytest.raises(openai.APIConnectionError) as raised:
            [piece async for piece in model.astream("hi")]

        assert tagged_role(raised.value) == role


def _embeddings_for(response: httpx.Response | Exception):
    embeddings = make_embeddings(_settings())
    transport = _transport(response)
    embeddings.client = openai.OpenAI(
        api_key="unused",  # pragma: allowlist secret
        base_url="http://embed.test/v1",
        http_client=httpx.Client(transport=transport),
        max_retries=0,
    ).embeddings
    embeddings.async_client = openai.AsyncOpenAI(
        api_key="unused",  # pragma: allowlist secret
        base_url="http://embed.test/v1",
        http_client=httpx.AsyncClient(transport=transport),
        max_retries=0,
    ).embeddings
    return embeddings


_EMBEDDING_BODIES = {
    "html": _HTML,
    "error object": httpx.Response(200, json={"error": {"message": "boom"}}),
    "no data": httpx.Response(200, json={"object": "list"}),
    "not json": httpx.Response(200, content=b"not json"),
}


@pytest.mark.parametrize("response", _EMBEDDING_BODIES.values(), ids=_EMBEDDING_BODIES.keys())
class TestEmbeddingsMalformedBody:
    """A 200 from the embedding server that holds no vectors is the server's fault."""

    def test_embedding_a_query_raises_the_dedicated_error(self, response):
        """
        GIVEN an embeddings client whose server answers 200 with no vectors
        WHEN a query and documents are embedded
        THEN MalformedModelResponseError is raised for each, tagged embedding
        """
        embeddings = _embeddings_for(response)

        for call in (
            lambda: embeddings.embed_query("hi"),
            lambda: embeddings.embed_documents(["a"]),
        ):
            with pytest.raises(MalformedModelResponseError) as raised:
                call()
            assert tagged_role(raised.value) == "embedding"

    @pytest.mark.asyncio
    async def test_embedding_asynchronously_raises_the_dedicated_error(self, response):
        """
        GIVEN the same client
        WHEN a query and documents are embedded asynchronously
        THEN MalformedModelResponseError is raised for each, tagged embedding
        """
        embeddings = _embeddings_for(response)

        for call in (
            lambda: embeddings.aembed_query("hi"),
            lambda: embeddings.aembed_documents(["a"]),
        ):
            with pytest.raises(MalformedModelResponseError) as raised:
                await call()
            assert tagged_role(raised.value) == "embedding"


class TestEmbeddingsOtherFailures:
    """An embedding server that cannot be reached keeps its error type and says which it was."""

    def test_a_connection_failure_carries_the_role(self):
        """
        GIVEN an embeddings client whose server cannot be reached
        WHEN a query is embedded
        THEN openai.APIConnectionError is raised, tagged embedding
        """
        embeddings = _embeddings_for(httpx.ConnectError("refused"))

        with pytest.raises(openai.APIConnectionError) as raised:
            embeddings.embed_query("hi")

        assert tagged_role(raised.value) == "embedding"


def _reranker(monkeypatch, response: httpx.Response | Exception) -> LlamaServerReranker:
    """A reranker whose HTTP client answers `response`, whatever its constructor arguments."""
    real = httpx.AsyncClient

    def client(**kwargs: Any) -> httpx.AsyncClient:
        return real(transport=_transport(response), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    return LlamaServerReranker(base_url="http://rerank.test/v1", model="m", timeout=5.0)


class TestRerankerMalformedBody:
    """A 200 from the rerank server that holds no results is the server's fault."""

    @pytest.mark.parametrize(
        "response",
        [
            _HTML,
            httpx.Response(200, json={"error": "boom"}),
            httpx.Response(200, json=["not", "an", "object"]),
            httpx.Response(200, json={"results": None}),
        ],
        ids=["html", "no results", "a list", "null results"],
    )
    def test_the_dedicated_error_is_raised_and_tagged_rerank(self, monkeypatch, response):
        """
        GIVEN a reranker whose server answers 200 with a body that holds no results
        WHEN texts are scored
        THEN MalformedModelResponseError is raised, tagged rerank
        """
        reranker = _reranker(monkeypatch, response)

        with pytest.raises(MalformedModelResponseError) as raised:
            asyncio.run(reranker.rerank("q", ["a", "b"]))

        assert tagged_role(raised.value) == "rerank"

    def test_an_unreachable_server_keeps_its_error_and_carries_the_role(self, monkeypatch):
        """
        GIVEN a reranker whose server cannot be reached
        WHEN texts are scored
        THEN httpx.ConnectError is raised as it is, tagged rerank
        """
        reranker = _reranker(monkeypatch, httpx.ConnectError("refused"))

        with pytest.raises(httpx.ConnectError) as raised:
            asyncio.run(reranker.rerank("q", ["a"]))

        assert tagged_role(raised.value) == "rerank"


class _Store(InMemoryVectorStore):
    """An in-memory store with the identity relevance function a dense search needs."""

    def _select_relevance_score_fn(self):
        return lambda similarity: similarity


@pytest.mark.asyncio
class TestMalformedRepliesAreAnOutage:
    """A turn whose embedding or rerank server answers 200 with a page is a 503, by role."""

    @pytest.mark.parametrize("role", ["embedding", "rerank"])
    async def test_the_turn_is_unavailable_and_the_record_names_the_server(self, monkeypatch, role):
        """
        GIVEN a retriever built on the real embeddings client, or on the real reranker,
            whose server answers 200 with an HTML page
        WHEN a turn is answered
        THEN AssistantUnavailableError is raised and one warning carries the dedicated error
            as the reason and the failing server as the role
        """
        if role == "embedding":
            store = _Store(_embeddings_for(_HTML))
            reranker = None
        else:
            store = _Store(DeterministicFakeEmbedding(size=8))
            await store.aadd_texts(["a passage"])
            reranker = _reranker(monkeypatch, _HTML)
        config = RetrievalConfig(mode="dense", k=1, rerank=role == "rerank", query_transform="none")
        ctx = AssistantContext(
            client=UserApiClient.__new__(UserApiClient),
            retriever=DocsRetriever(store=store, config=config, reranker=reranker, llm=None),
            sources=SourceRegistry(),
            tool_outputs=[],
            current_project_id=None,
            locale="en",
        )
        settings = Settings(
            secret_key="test-secret-key",  # pragma: allowlist secret
            assistant_mode="workflow",
        )
        service = AssistantService(
            settings, ScriptedToolCallingModel(responses=[AIMessage(content="never used")])
        )

        with (
            captured_log_records("api.assistant.agent.service") as records,
            pytest.raises(AssistantUnavailableError),
        ):
            await service.answer(AssistantChatRequest(message="hi", history=[]), ctx)

        assert [(r.event, r.reason, r.role) for r in records] == [
            ("assistant_dependency_unavailable", "MalformedModelResponseError", role)
        ]
