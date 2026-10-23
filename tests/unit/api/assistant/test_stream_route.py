"""Unit tests for the body of the streaming chat route, driven without the HTTP stack."""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from api.assistant.agent.context import AssistantContext, SourceRegistry
from api.assistant.agent.service import AssistantService
from api.assistant.client import UserApiClient
from api.assistant.deps import PreparedTurn
from api.assistant.rag.retrieval import DocsRetriever
from api.assistant.sse import KEEP_ALIVE
from api.config import Settings
from api.routes.assistant import chat_stream
from api.schemas.assistant import AssistantChatRequest
from tests.shared.assistant_fakes import ScriptedToolCallingModel


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch, tmp_path):
    """Keep Settings away from the repository's own .env file."""
    monkeypatch.chdir(tmp_path)


def _turn() -> PreparedTurn:
    retriever = AsyncMock(spec=DocsRetriever)
    retriever.search.return_value = []
    context = AssistantContext(
        client=AsyncMock(spec=UserApiClient),
        retriever=retriever,
        sources=SourceRegistry(),
        tool_outputs=[],
        current_project_id=None,
        locale="en",
    )
    return PreparedTurn(request=AssistantChatRequest(message="hi", history=[]), context=context)


class _QuietRequest:
    """Stands in for a request whose client stays: ``receive`` never answers."""

    async def receive(self) -> dict[str, str]:
        await asyncio.Event().wait()
        return {"type": "http.disconnect"}


@pytest.mark.asyncio
class TestEventsBody:
    """The body of the stream is closed with the response, and takes the model's call with it."""

    async def test_closing_the_body_after_a_keep_alive_cancels_the_model_stream_at_once(self):
        """
        GIVEN a stream whose model waits 30 s before its first piece, and a heartbeat of 50 ms
        WHEN the first block, a keep-alive, is read and the body is then closed
        THEN closing returns within a second and the model's stream was cut short, instead of
            waiting for the model to finish
        """
        # GIVEN
        settings = Settings(
            secret_key="test-secret-key",  # pragma: allowlist secret
            assistant_answer_llm_model="test-answer-model",
            assistant_stream_heartbeat_seconds=0.05,
        )
        model = ScriptedToolCallingModel(
            responses=[AIMessage(content="One two")], stream_delay_s=30
        )
        response = await chat_stream(
            _QuietRequest(),  # type: ignore[arg-type]
            _turn(),
            AssistantService(settings, model),
            settings,
        )
        body = response.body_iterator
        assert await anext(body) == KEEP_ALIVE

        # WHEN
        started = time.monotonic()
        await body.aclose()  # type: ignore[attr-defined]

        # THEN
        assert time.monotonic() - started < 1
        assert model.closed_early


class _SlowToFinish(AssistantService):
    """A service whose stream takes half a second to end after its last item."""

    async def stream(self, turn):
        async for item in super().stream(turn):
            yield item
        await asyncio.sleep(0.5)


@pytest.mark.asyncio
class TestEndOfStream:
    """The body ends with the done event, whatever the service does after it."""

    async def test_no_keep_alive_follows_the_done_event_when_the_service_is_slow_to_finish(self):
        """
        GIVEN a heartbeat of 50 ms and a service that takes 0.5 s to end its stream after the
            response
        WHEN the whole body is read
        THEN its last block is the done event, no keep-alive follows it, and the body ends long
            before the service does
        """
        # GIVEN
        settings = Settings(
            secret_key="test-secret-key",  # pragma: allowlist secret
            assistant_answer_llm_model="test-answer-model",
            assistant_stream_heartbeat_seconds=0.05,
        )
        model = ScriptedToolCallingModel(responses=[AIMessage(content="One two")])
        service = _SlowToFinish(settings, model)
        response = await chat_stream(
            _QuietRequest(),  # type: ignore[arg-type]
            _turn(),
            service,
            settings,
        )

        # WHEN
        started = time.monotonic()
        blocks = [block async for block in response.body_iterator]

        # THEN
        assert blocks[-1].startswith("event: done")
        assert time.monotonic() - started < 0.4
