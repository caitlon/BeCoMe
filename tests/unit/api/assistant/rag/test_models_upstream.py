"""A model server that answers 200 with a body that is no answer.

The clients here are real ones with a fake HTTP transport: nothing reaches a network. What
each must do is raise ``MalformedModelResponseError`` for such a body, tag every failure
with the role of the server it came from, and leave a bug of our own as it is.
"""

from collections.abc import Callable
from typing import Any

import httpx
import openai
import pytest
from langchain_core.tools import tool

from api.assistant.rag.models import (
    MalformedModelResponseError,
    make_answer_model,
    make_chat_model,
)
from api.assistant.roles import tagged_role
from api.config import Settings

_HTML = httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>oops</html>")
_MALFORMED_BODIES = {
    "html": _HTML,
    "error object": httpx.Response(200, json={"error": {"message": "boom"}}),
    "no choices": httpx.Response(200, json={"id": "c", "model": "m"}),
    "null choices": httpx.Response(200, json={"id": "c", "choices": None}),
    "choice without message": httpx.Response(200, json={"id": "c", "choices": [{"index": 0}]}),
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
