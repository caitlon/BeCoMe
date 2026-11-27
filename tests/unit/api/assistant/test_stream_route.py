"""Unit tests for the body of the streaming chat route, driven without the HTTP stack."""

import asyncio
import json
import time
import unicodedata
from unittest.mock import AsyncMock, patch

import langsmith as ls
import pytest
import requests
from langchain_core.messages import AIMessage
from starlette.requests import ClientDisconnect

from api.assistant.agent import service as service_module
from api.assistant.agent import tracing
from api.assistant.agent.context import AssistantContext, SourceRegistry
from api.assistant.agent.service import AssistantService
from api.assistant.client import UserApiClient
from api.assistant.deps import PreparedTurn
from api.assistant.rag.retrieval import DocsRetriever
from api.assistant.sse import KEEP_ALIVE
from api.config import Settings
from api.routes.assistant import chat_stream
from api.schemas.assistant import AssistantChatRequest
from tests.shared.assistant_fakes import NoNetworkAdapter, ScriptedToolCallingModel
from tests.shared.helpers import captured_log_records


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
    """A service whose stream takes ten seconds to end after its last item."""

    async def stream(self, turn):
        async for item in super().stream(turn):
            yield item
        await asyncio.sleep(10)


@pytest.mark.asyncio
class TestEndOfStream:
    """The body ends with the done event, whatever the service does after it."""

    async def test_no_keep_alive_follows_the_done_event_when_the_service_is_slow_to_finish(self):
        """
        GIVEN a heartbeat of 50 ms and a service that takes 10 s to end its stream after the
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
        assert time.monotonic() - started < 5


@pytest.mark.asyncio
class TestInvisibleCharactersOnTheWire:
    """No event of the stream carries a character that renders as nothing."""

    async def test_no_token_and_no_final_answer_holds_a_formatting_character(self):
        """
        GIVEN a model that streams a zero-width space, a bidi override and a soft hyphen
        WHEN the whole body is read
        THEN no token event and not the done event's answer holds one, and the tokens join
            to the answer
        """
        # GIVEN
        settings = Settings(
            secret_key="test-secret-key",  # pragma: allowlist secret
            assistant_answer_llm_model="test-answer-model",
        )
        model = ScriptedToolCallingModel(
            responses=[AIMessage(content="One\u200btwo \u202ethree\u00ad four")],
            stream_chunks=["One\u200b", "two ", "\u202e", "three\u00ad", " four"],
        )
        response = await chat_stream(
            _QuietRequest(),  # type: ignore[arg-type]
            _turn(),
            AssistantService(settings, model),
            settings,
        )

        # WHEN
        blocks = [block async for block in response.body_iterator]

        # THEN
        events = [
            (lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: ")))
            for block in blocks
            if (lines := block.strip().split("\n"))[0].startswith("event: ")
        ]
        texts = [payload["text"] for name, payload in events if name == "token"]
        (answer,) = [payload["answer"] for name, payload in events if name == "done"]
        assert "".join(texts) == answer == "Onetwo three four"
        assert not any(
            unicodedata.category(char) in {"Cc", "Cf"} and char not in "\n\t"
            for text in [*texts, answer]
            for char in text
        )


@pytest.mark.asyncio
class TestReasoningThatNeverCloses:
    """A reply cut off inside its reasoning after some text ends as a normal answer."""

    async def test_the_text_before_the_unclosed_block_is_streamed_and_the_last_event_is_done(
        self,
    ):
        """
        GIVEN a model that streams an answer and then opens a reasoning block, the tag split
              across chunks, and is cut off
        WHEN the whole body is read
        THEN the tokens join to the answer, nothing of the block is sent, there is no error
             event, and the last event is done with that answer
        """
        # GIVEN
        settings = Settings(
            secret_key="test-secret-key",  # pragma: allowlist secret
            assistant_answer_llm_model="test-answer-model",
        )
        chunks = ["One two ", "<thi", "nk>secret ", "thoughts"]
        model = ScriptedToolCallingModel(
            responses=[AIMessage(content="".join(chunks))], stream_chunks=chunks
        )
        response = await chat_stream(
            _QuietRequest(),  # type: ignore[arg-type]
            _turn(),
            AssistantService(settings, model),
            settings,
        )

        # WHEN
        blocks = [block async for block in response.body_iterator]

        # THEN
        events = [
            (lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: ")))
            for block in blocks
            if (lines := block.strip().split("\n"))[0].startswith("event: ")
        ]
        names = [name for name, _ in events]
        texts = [payload["text"] for name, payload in events if name == "token"]
        assert "error" not in names
        assert names[-1] == "done"
        assert "".join(texts) == events[-1][1]["answer"] == "One two"

    @pytest.mark.parametrize(
        "chunks",
        [
            ["  \n ", "<thi", "nk>secret ", "thoughts"],
            ["<think>a</think>", "  \n  ", "<think>b"],
        ],
    )
    async def test_blanks_before_the_unclosed_block_end_the_stream_with_a_503_error_event(
        self, chunks: list[str]
    ):
        """
        GIVEN a model whose reply has only whitespace, or a closed block and whitespace, before
              a reasoning block that never closes, streamed in pieces
        WHEN the whole body is read
        THEN no token and no done event is sent, and the only event is an error with the public
             503 detail and nothing of the reasoning, and the log gives the reason cut_off
        """
        # GIVEN
        settings = Settings(
            secret_key="test-secret-key",  # pragma: allowlist secret
            assistant_answer_llm_model="test-answer-model",
        )
        model = ScriptedToolCallingModel(
            responses=[AIMessage(content="".join(chunks))], stream_chunks=chunks
        )
        response = await chat_stream(
            _QuietRequest(),  # type: ignore[arg-type]
            _turn(),
            AssistantService(settings, model),
            settings,
        )

        # WHEN
        with captured_log_records("api.assistant.agent.service") as records:
            blocks = [block async for block in response.body_iterator]

        # THEN
        events = [
            (lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: ")))
            for block in blocks
            if (lines := block.strip().split("\n"))[0].startswith("event: ")
        ]
        assert events == [
            ("error", {"code": 503, "detail": "The assistant is temporarily unavailable"})
        ]
        assert "secret" not in "".join(blocks)
        (record,) = [r for r in records if getattr(r, "event", "") == "assistant_empty_answer"]
        assert record.reason == "cut_off"


class _RecordingClient(tracing.MaskingClient):
    """A LangSmith client that sends nothing and records the traces it was told to release.

    :ivar released: The id of each trace handed to :meth:`release`, in order.
    """

    def __init__(self, **kwargs):
        super().__init__(auto_batch_tracing=False, **kwargs)
        self.released: list[str] = []
        self.session.mount("http://", NoNetworkAdapter())
        self.session.mount("https://", NoNetworkAdapter())

    def release(self, trace_id: str) -> None:
        self.released.append(trace_id)
        super().release(trace_id)

    def request_with_retries(self, method, pathname, **kwargs):
        return requests.Response()


@pytest.fixture
def traced():
    """Switch tracing on with a recording client, and hand back the runs the turns open.

    :return: The client, and the list that receives each turn's root run.
    """
    client = _RecordingClient()
    runs: list = []

    def start_and_keep(*args, **kwargs):
        runs.append(tracing.start_turn(*args, **kwargs))
        return runs[-1]

    tracing.shutdown_tracing()
    ls.utils.get_env_var.cache_clear()
    with (
        patch.object(tracing, "_new_client", return_value=client),
        patch.object(service_module, "start_turn", side_effect=start_and_keep),
    ):
        yield client, runs
    tracing.shutdown_tracing()
    ls.utils.get_env_var.cache_clear()


def _traced_settings() -> Settings:
    return Settings(
        secret_key="test-secret-key",  # pragma: allowlist secret
        assistant_answer_llm_model="test-answer-model",
        assistant_langsmith_enabled=True,
        assistant_langsmith_api_key="lsv2_test",  # pragma: allowlist secret
    )


async def _send_nowhere(message) -> None:
    """Take what the response sends."""


async def _never_disconnects():
    """Stand in for a receive channel of a client that stays."""
    await asyncio.Event().wait()


@pytest.mark.asyncio
class TestTraceOfAResponseThatIsTornDown:
    """The held trace of a stream ends once, whether or not the body was ever read."""

    async def test_a_body_that_is_never_read_still_ends_the_trace(self, traced):
        """
        GIVEN a prepared stream whose trace is held, and a client that is gone before Starlette
            reads the first piece of the body, so that sending the headers fails
        WHEN the response is run
        THEN the trace is ended, with no answer and the disconnect as its error, and released once
        """
        # GIVEN
        client, runs = traced
        settings = _traced_settings()
        response = await chat_stream(
            _QuietRequest(),  # type: ignore[arg-type]
            _turn(),
            AssistantService(
                settings, ScriptedToolCallingModel(responses=[AIMessage(content="a")])
            ),
            settings,
        )
        (run,) = runs
        assert run.end_time is None
        assert client.released == []

        async def failing_send(message) -> None:
            raise OSError("client gone")

        # WHEN
        with pytest.raises(ClientDisconnect):
            await response(
                {"type": "http", "asgi": {"spec_version": "2.4"}}, _never_disconnects, failing_send
            )

        # THEN
        assert run.end_time is not None
        assert not run.outputs
        assert run.error == "ClientDisconnect"
        assert client.released == [str(run.trace_id)]

    async def test_a_turn_that_streams_is_ended_once_with_its_answer(self, traced):
        """
        GIVEN a prepared stream whose trace is held
        WHEN the response is run to its end
        THEN the trace was ended by the stream with the answer, and released exactly once
        """
        # GIVEN
        client, runs = traced
        settings = _traced_settings()
        response = await chat_stream(
            _QuietRequest(),  # type: ignore[arg-type]
            _turn(),
            AssistantService(
                settings, ScriptedToolCallingModel(responses=[AIMessage(content="One two")])
            ),
            settings,
        )
        (run,) = runs

        # WHEN
        await response(
            {"type": "http", "asgi": {"spec_version": "2.4"}}, _never_disconnects, _send_nowhere
        )

        # THEN
        assert run.outputs == {"answer": "One two"}
        assert run.error is None
        assert client.released == [str(run.trace_id)]

    async def test_a_failed_write_after_the_first_piece_closes_the_body_and_cancels_the_model(
        self, traced
    ):
        """
        GIVEN a stream whose model waits 30 s, a heartbeat of 50 ms, and a client that takes the
            headers and the first keep-alive and then fails a write
        WHEN the response is run
        THEN the model's call was cancelled before the response returned, and the trace was
            ended and released once
        """
        # GIVEN
        client, runs = traced
        settings = _traced_settings().model_copy(
            update={"assistant_stream_heartbeat_seconds": 0.05}
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
        (run,) = runs
        sent: list[dict] = []

        async def second_write_fails(message) -> None:
            sent.append(message)
            if len(sent) == 2:
                raise OSError("client gone")

        # WHEN
        with pytest.raises(ClientDisconnect):
            await response(
                {"type": "http", "asgi": {"spec_version": "2.4"}},
                _never_disconnects,
                second_write_fails,
            )

        # THEN
        assert model.closed_early
        assert run.end_time is not None
        assert client.released == [str(run.trace_id)]

    async def test_the_trace_is_ended_once_when_the_server_reports_spec_2_3(self, traced):
        """
        GIVEN a prepared stream whose trace is held, a server reporting ASGI 2.3 (uvicorn does),
            and a client whose disconnect is the first message
        WHEN the response is run
        THEN the trace is ended and released exactly once
        """
        # GIVEN
        client, runs = traced
        settings = _traced_settings()
        response = await chat_stream(
            _QuietRequest(),  # type: ignore[arg-type]
            _turn(),
            AssistantService(
                settings, ScriptedToolCallingModel(responses=[AIMessage(content="a")])
            ),
            settings,
        )
        (run,) = runs

        async def disconnected():
            return {"type": "http.disconnect"}

        # WHEN
        await response(
            {"type": "http", "asgi": {"spec_version": "2.3"}}, disconnected, _send_nowhere
        )

        # THEN
        assert run.end_time is not None
        assert client.released == [str(run.trace_id)]

    async def test_a_turn_with_tracing_off_streams_as_before(self):
        """
        GIVEN a prepared stream with tracing off, so no trace
        WHEN the response is run to its end
        THEN it sends the headers, the pieces and a done event, and nothing raises
        """
        # GIVEN
        settings = Settings(
            secret_key="test-secret-key",  # pragma: allowlist secret
            assistant_answer_llm_model="test-answer-model",
        )
        response = await chat_stream(
            _QuietRequest(),  # type: ignore[arg-type]
            _turn(),
            AssistantService(
                settings, ScriptedToolCallingModel(responses=[AIMessage(content="One two")])
            ),
            settings,
        )
        sent: list[dict] = []

        async def collect(message) -> None:
            sent.append(message)

        # WHEN
        await response(
            {"type": "http", "asgi": {"spec_version": "2.4"}}, _never_disconnects, collect
        )

        # THEN
        assert sent[0]["type"] == "http.response.start"
        body = b"".join(m["body"] for m in sent[1:])
        assert b"event: done" in body
        assert sent[-1] == {"type": "http.response.body", "body": b"", "more_body": False}
