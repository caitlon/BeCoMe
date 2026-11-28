"""Integration tests that pin the assistant's logs: no record of a turn carries what a user wrote.

``TestLogsCarryNoText`` in ``test_assistant_chat.py`` covers /chat in two modes. These tests
widen it to /chat/stream, the hybrid mode, a traced turn and a stream turn that fails with an
exception whose message holds text, and they search more of each record: the traceback text
and the stack of every record, not only its message, arguments and attributes.

The model is the real chat client talking to a stub server on localhost (so the libraries'
own loggers run), or a scripted fake that raises. Tracing goes to a client that sends
nothing. Nothing here reaches a real model server, embedding server or LangSmith.
"""

import io
import json
import logging
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager, nullcontext
from typing import Any, override
from unittest.mock import patch

import pytest
import sentry_sdk
from fastapi.testclient import TestClient
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from sentry_sdk.transport import Transport

from api.assistant.agent import tracing
from api.config import get_settings
from api.main import _init_sentry
from tests.integration.api import test_assistant_chat as chat_tests
from tests.integration.api.test_assistant_chat import (
    _ALL_MODES,
    _ANSWER_SENTINEL,
    _CHATTY_LOGGERS,
    _LIBRARY_PREFIXES,
    _NAME_SENTINEL,
    _QUESTION_SENTINEL,
    CHAT,
    OWNER_LAST_NAME,
    STREAM,
    _CapturingClient,
    _events,
    _owner_project,
    _stub_model_server,
    _StubModelHandler,
    _StubModelServer,
    _use_model,
)
from tests.shared.assistant_fakes import ScriptedToolCallingModel
from tests.shared.helpers import auth_header, captured_log_records

# The chat tests' fixtures, reused as they are: ``_chat_settings`` gives every test explicit
# settings and empty caches (it applies to this module once it is named here), and
# ``configure`` changes settings in the middle of a test.
_chat_settings = chat_tests._chat_settings
configure = chat_tests.configure

_POSITION_SENTINEL = "SENTINEL-POSITION-c41e8d07"
_ERROR_SENTINEL = "SENTINEL-ERROR-9b2f6a35"
_TEXT_SENTINELS = [
    _QUESTION_SENTINEL,
    _NAME_SENTINEL,
    OWNER_LAST_NAME,
    _POSITION_SENTINEL,
    _ANSWER_SENTINEL,
    _ERROR_SENTINEL,
]
_ENDPOINTS = [CHAT, STREAM]
_ENDPOINT_IDS = ["chat", "stream"]


class _StreamingStubHandler(_StubModelHandler):
    """The chat tests' stub model, which also answers a streamed request in server-sent events."""

    @override
    def do_POST(self) -> None:
        """Answer a streamed request here, and any other as the parent class does."""
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        request = json.loads(raw)
        if not request.get("stream"):
            self.rfile = io.BytesIO(raw)
            super().do_POST()
            return
        self.server.bodies.append(request)
        pieces = ["It says ", f"{_ANSWER_SENTINEL}."]
        frames: list[dict[str, Any]] = [
            {"delta": {"role": "assistant", "content": piece}, "finish_reason": None}
            for piece in pieces
        ]
        frames.append({"delta": {}, "finish_reason": "stop"})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for frame in frames:
            chunk = {
                "id": "chatcmpl-stub",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "test-answer-model",
                "choices": [{"index": 0, **frame}],
            }
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


@contextmanager
def _streaming_stub_server(project_id: str) -> Iterator[_StubModelServer]:
    """Run the chat tests' stub model server with a handler that can also stream."""
    with _stub_model_server(project_id) as server:
        server.RequestHandlerClass = _StreamingStubHandler
        yield server


@contextmanager
def _captured_tracing(
    monkeypatch: pytest.MonkeyPatch, configure: Callable[..., None]
) -> Iterator[list[_CapturingClient]]:
    """Switch tracing on and build the shared client as one that keeps what it would send."""
    monkeypatch.setenv("ASSISTANT_LANGSMITH_API_KEY", "ls-key")  # pragma: allowlist secret
    configure(ASSISTANT_LANGSMITH_ENABLED="true", ASSISTANT_LANGSMITH_PROJECT="logs")
    built: list[_CapturingClient] = []

    def build(**kwargs: Any) -> _CapturingClient:
        built.append(_CapturingClient(**kwargs))
        return built[-1]

    with patch.object(tracing, "_new_client", build):
        yield built


def _everything_a_record_says(record: logging.LogRecord) -> str:
    """Render a record as every handler could: message, arguments, attributes and tracebacks.

    This adds to the chat tests' rendering the traceback formatted again from ``exc_info``
    (with its chained causes and their messages), the traceback text a handler cached on the
    record and the stack of the call.
    """
    parts = [chat_tests._everything_a_record_says(record), record.exc_text or ""]
    parts.append(record.stack_info or "")
    if record.exc_info and record.exc_info[0] is not None:
        parts.append(logging.Formatter().formatException(record.exc_info))
    return "\n".join(parts)


def _post_capturing_records(
    client: TestClient, endpoint: str, body: dict[str, Any], token: str
) -> tuple[Any, list[logging.LogRecord]]:
    """Post a turn, with every logger a library or the application writes to at DEBUG.

    The test client does not raise a failure of the app: it is answered as a client sees it.
    """
    with ExitStack() as stack:
        captured = [stack.enter_context(captured_log_records(name)) for name in _CHATTY_LOGGERS]
        response = TestClient(client.app, raise_server_exceptions=False).post(
            endpoint, json=body, headers=auth_header(token)
        )
    return response, [record for group in captured for record in group]


def _assert_records_hold_no_text(records: list[logging.LogRecord]) -> None:
    """Fail when any record says anything a user or a model wrote."""
    for record in records:
        text = _everything_a_record_says(record)
        for sentinel in _TEXT_SENTINELS:
            assert sentinel not in text, f"{record.name} logged {sentinel}: {record.getMessage()}"


class _RaisingModel(ScriptedToolCallingModel):
    """A model that fails with an exception whose message holds text, whichever way it is called."""

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> ChatResult:
        """Raise at once, as a model call that was not streamed."""
        raise RuntimeError(f"the model failed on {_ERROR_SENTINEL}")

    async def _astream(
        self, messages: list[BaseMessage], *args: Any, **kwargs: Any
    ) -> AsyncIterator[ChatGenerationChunk]:
        """Raise at once, as a streamed call; the ``yield`` makes this an async generator."""
        raise RuntimeError(f"the model failed on {_ERROR_SENTINEL}")
        yield  # pragma: no cover


class TestLogsOfAnAnsweredTurnCarryNoText:
    """No record of an answered turn holds the question, a member's data or the answer."""

    @pytest.mark.parametrize("traced", [False, True], ids=["untraced", "traced"])
    @pytest.mark.parametrize("mode", _ALL_MODES)
    @pytest.mark.parametrize("endpoint", _ENDPOINTS, ids=_ENDPOINT_IDS)
    def test_no_record_holds_what_a_user_or_the_model_wrote(
        self, assistant_settings, client, configure, monkeypatch, endpoint, mode, traced
    ):
        """
        GIVEN the real chat client talking to a stub server on localhost, sentinel strings
            in the question, in an expert's first name and position and in the model's
            answer, every library logger at DEBUG, and tracing on or off
        WHEN a turn is answered through /chat or /chat/stream in each mode
        THEN the answer carries the model's sentinel (so the turn ran through the client),
            the model was shown the question, the name and the position (workflow and hybrid
            read the project ahead; the tool modes through the tool), some library record was
            captured (so the capture is live), the app's own assistant_turn record was captured,
            the trace client received runs when tracing is on, and no record's message,
            arguments, attributes, traceback or stack holds a sentinel
        """
        # GIVEN
        owner = _owner_project(client, position=_POSITION_SENTINEL, first_name=_NAME_SENTINEL)
        body = {"message": f"Question {_QUESTION_SENTINEL}?", "project_id": owner["id"]}
        tracing_scope: AbstractContextManager[list[_CapturingClient]] = (
            _captured_tracing(monkeypatch, configure) if traced else nullcontext([])
        )
        with tracing_scope as trace_clients, _streaming_stub_server(owner["id"]) as server:
            configure(ASSISTANT_MODE=mode, ASSISTANT_ANSWER_LLM_BASE_URL=server.base_url)

            # WHEN
            response, records = _post_capturing_records(client, endpoint, body, owner["token"])

        # THEN
        assert response.status_code == 200
        if endpoint == CHAT:
            answer = response.json()["answer"]
        else:
            events = _events(response.text)
            assert events[-1][0] == "done"
            answer = events[-1][1]["answer"]
        assert _ANSWER_SENTINEL in answer
        sent = json.dumps(server.bodies)
        for shown in (_QUESTION_SENTINEL, _NAME_SENTINEL, _POSITION_SENTINEL):
            assert shown in sent
        assert any(record.name.split(".")[0].startswith(_LIBRARY_PREFIXES) for record in records)
        assert any(getattr(record, "event", "") == "assistant_turn" for record in records)
        if traced:
            (recorder,) = trace_clients
            assert recorder.bodies
        _assert_records_hold_no_text(records)


class TestLogsOfAFailedStreamCarryNoText:
    """A stream turn that fails on text the model's exception holds writes no record with it."""

    @pytest.mark.parametrize("traced", [False, True], ids=["untraced", "traced"])
    @pytest.mark.parametrize("mode", _ALL_MODES)
    def test_no_record_holds_the_message_of_the_models_exception(
        self, assistant_settings, client, configure, monkeypatch, mode, traced
    ):
        """
        GIVEN a model that raises an exception whose message holds a sentinel, the question,
            the project's data and every logger at DEBUG, and tracing on or off
        WHEN a turn is posted through /chat/stream in each mode
        THEN the stream ends with its error event holding the fixed public text, the failure
            was recorded as a RuntimeError (so the stub model's exception is what failed and
            the capture is live), the trace client received runs when tracing is on, and no
            record's message, arguments, attributes, traceback or stack holds a sentinel
        """
        # GIVEN
        owner = _owner_project(client, position=_POSITION_SENTINEL, first_name=_NAME_SENTINEL)
        body = {"message": f"Question {_QUESTION_SENTINEL}?", "project_id": owner["id"]}
        tracing_scope: AbstractContextManager[list[_CapturingClient]] = (
            _captured_tracing(monkeypatch, configure) if traced else nullcontext([])
        )
        with tracing_scope as trace_clients:
            configure(ASSISTANT_MODE=mode)
            _use_model(client, _RaisingModel(responses=[]))

            # WHEN
            response, records = _post_capturing_records(client, STREAM, body, owner["token"])

        # THEN
        assert response.status_code == 200
        assert _events(response.text)[-1] == (
            "error",
            {"code": 500, "detail": "Internal server error"},
        )
        assert _ERROR_SENTINEL not in response.text
        failure = [r for r in records if getattr(r, "event", "") == "assistant_stream_failed"]
        assert {getattr(r, "reason", "") for r in failure} == {"RuntimeError"}
        if traced:
            (recorder,) = trace_clients
            assert recorder.bodies
        _assert_records_hold_no_text(records)


class TestLogsOfAFailedChatTurnCarryNoText:
    """A /chat turn that fails on text the model's exception holds writes no record with it."""

    @pytest.mark.parametrize("traced", [False, True], ids=["untraced", "traced"])
    @pytest.mark.parametrize("mode", _ALL_MODES)
    def test_no_record_holds_the_message_of_the_models_exception(
        self, assistant_settings, client, configure, monkeypatch, mode, traced
    ):
        """
        GIVEN a model that raises an exception whose message holds a sentinel, the question,
            the project's data and every logger at DEBUG, and tracing on or off
        WHEN a turn is posted through /chat in each mode
        THEN the answer is the fixed 500 body without the sentinel, the failure was recorded
            once as an unhandled_exception event naming a RuntimeError and carrying the request
            id (so the stub model's exception is what failed and the capture is live), the trace
            client received runs when tracing is on, and no record's message, arguments,
            attributes, traceback or stack holds a sentinel
        """
        # GIVEN
        owner = _owner_project(client, position=_POSITION_SENTINEL, first_name=_NAME_SENTINEL)
        body = {"message": f"Question {_QUESTION_SENTINEL}?", "project_id": owner["id"]}
        tracing_scope: AbstractContextManager[list[_CapturingClient]] = (
            _captured_tracing(monkeypatch, configure) if traced else nullcontext([])
        )
        with tracing_scope as trace_clients:
            configure(ASSISTANT_MODE=mode)
            _use_model(client, _RaisingModel(responses=[]))

            # WHEN
            response, records = _post_capturing_records(client, CHAT, body, owner["token"])

        # THEN
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
        assert _ERROR_SENTINEL not in response.text
        # A record reaches every logger above its own, so the same one can be captured twice.
        failures = {id(r): r for r in records if getattr(r, "event", "") == "unhandled_exception"}
        (failure,) = failures.values()
        assert failure.exception_type == "RuntimeError"  # type: ignore[attr-defined]
        assert failure.path == CHAT  # type: ignore[attr-defined]
        assert failure.request_id  # type: ignore[attr-defined]
        if traced:
            (recorder,) = trace_clients
            assert recorder.bodies
        _assert_records_hold_no_text(records)


class _KeepEnvelopes(Transport):
    """A Sentry transport that keeps every envelope in memory instead of sending it."""

    def __init__(self) -> None:
        super().__init__()
        self.envelopes: list[Any] = []

    @override
    def capture_envelope(self, envelope: Any) -> None:
        self.envelopes.append(envelope)

    def event_count(self) -> int:
        """Count the error events among the kept envelopes."""
        return sum(
            1 for envelope in self.envelopes for item in envelope.items if item.type == "event"
        )

    def serialized(self) -> str:
        """Return every envelope item's payload as one string."""
        return json.dumps(
            [item.payload.json for envelope in self.envelopes for item in envelope.items],
            default=str,
        )


@contextmanager
def _sentry_keeping_envelopes() -> Iterator[_KeepEnvelopes]:
    """Start Sentry with the app's own initialisation, sending to a transport that keeps envelopes."""
    transport = _KeepEnvelopes()
    real_init = sentry_sdk.init

    def init_with_transport(**kwargs: Any) -> None:
        real_init(**kwargs, transport=transport)

    settings = get_settings().model_copy(
        update={"sentry_dsn": "https://public@o0.ingest.sentry.io/0"}
    )
    previous = sentry_sdk.get_client()
    try:
        with patch("api.main.sentry_sdk.init", init_with_transport):
            _init_sentry(settings)
        yield transport
    finally:
        sentry_sdk.flush()
        sentry_sdk.get_global_scope().set_client(previous)


class TestSentryEventsOfAFailedChatTurnCarryNoText:
    """The error tracker receives the failure of a /chat turn without the text in it."""

    @pytest.mark.parametrize("endpoint", _ENDPOINTS, ids=_ENDPOINT_IDS)
    def test_no_event_holds_the_message_of_the_models_exception(
        self, assistant_settings, client, configure, endpoint
    ):
        """
        GIVEN Sentry started by the app's own _init_sentry, with a transport that keeps
            envelopes, and a model that raises an exception whose message holds a sentinel
        WHEN a turn is posted through /chat or /chat/stream
        THEN the failure reached Sentry as at least one event (so the capture is live) and no
            item of any envelope holds a sentinel
        """
        # GIVEN
        owner = _owner_project(client, position=_POSITION_SENTINEL, first_name=_NAME_SENTINEL)
        body = {"message": f"Question {_QUESTION_SENTINEL}?", "project_id": owner["id"]}
        configure(ASSISTANT_MODE="workflow")
        _use_model(client, _RaisingModel(responses=[]))

        # WHEN
        with _sentry_keeping_envelopes() as transport:
            _post_capturing_records(client, endpoint, body, owner["token"])
            sentry_sdk.flush()

        # THEN
        assert transport.event_count() >= 1
        sent = transport.serialized()
        for sentinel in _TEXT_SENTINELS:
            assert sentinel not in sent


def _record_with(**fields: Any) -> logging.LogRecord:
    """Build a record whose message is clean, with the given fields set on it."""
    record = logging.LogRecord("api.x", logging.ERROR, __file__, 1, "Fixed message", None, None)
    for name, value in fields.items():
        setattr(record, name, value)
    return record


class TestTheDetectorSeesText:
    """The search for text in records reads the places a clean message does not show."""

    def test_a_sentinel_only_in_the_exception_of_a_record_is_found(self):
        """
        GIVEN a record with a clean message whose exc_info holds an exception carrying a sentinel
        WHEN the records are searched for text
        THEN the search fails on that sentinel
        """
        # GIVEN
        try:
            raise RuntimeError(f"failed on {_ERROR_SENTINEL}")
        except RuntimeError:
            record = _record_with(exc_info=sys.exc_info())

        # WHEN/THEN
        with pytest.raises(AssertionError, match=_ERROR_SENTINEL):
            _assert_records_hold_no_text([record])

    def test_a_sentinel_only_in_the_cached_traceback_text_is_found(self):
        """
        GIVEN a record with a clean message and no exc_info whose exc_text holds a sentinel
        WHEN the records are searched for text
        THEN the search fails on that sentinel
        """
        # GIVEN
        record = _record_with(exc_text=f"RuntimeError: failed on {_ERROR_SENTINEL}")

        # WHEN/THEN
        with pytest.raises(AssertionError, match=_ERROR_SENTINEL):
            _assert_records_hold_no_text([record])

    def test_a_clean_record_passes(self):
        """
        GIVEN a record with a clean message and no exception
        WHEN the records are searched for text
        THEN the search passes
        """
        # WHEN/THEN
        _assert_records_hold_no_text([_record_with()])
