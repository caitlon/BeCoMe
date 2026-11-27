"""Probes and doubles for the assistant's security tests, built on ``assistant_fakes``.

The assistant reads the application through an in-process ASGI transport, so a test cannot see
those requests on a network. :func:`record_inner_requests` puts a recording wrapper between the
client and the application. The models here script what ``ScriptedToolCallingModel`` cannot:
a callback before the first reply, a streamed tool call, and two turns held inside one model
at the same moment.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import pytest
from fastapi.testclient import TestClient
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field
from sqlalchemy.pool import QueuePool
from sqlmodel import Session, SQLModel, create_engine
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.assistant import deps
from api.assistant.client import UserApiClient
from api.db.session import get_session
from tests.integration.api.conftest import (
    create_project,
    create_test_app,
    register_verified,
    submit_opinion,
)
from tests.shared.assistant_fakes import ScriptedToolCallingModel, ToolEchoingModel
from tests.shared.helpers import DEFAULT_TEST_PASSWORD, auth_header


def tool_call_of(name: str, args: dict[str, Any], call_id: str = "call_1") -> AIMessage:
    """Build a model reply that calls one tool with exactly the given arguments."""
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}]
    )


def tool_messages(model: ScriptedToolCallingModel | ToolEchoingModel) -> list[ToolMessage]:
    """Every tool message the model was shown, in the order of its calls."""
    return [message for call in model.seen for message in call if isinstance(message, ToolMessage)]


@dataclass(frozen=True)
class InnerRequest:
    """One request the assistant's client sent to the application.

    :ivar method: The HTTP method.
    :ivar path: The request path, without the query string.
    :ivar query: The decoded query string, blank values kept.
    :ivar status: The HTTP status the application answered with, 0 while no answer started.
    """

    method: str
    path: str
    query: dict[str, list[str]]
    status: int = 0


class RecordingApp:
    """An ASGI application wrapper that records each HTTP request and the status it gets.

    :param app: The wrapped application.
    :param log: Where each request is appended, in the order it arrives.
    """

    def __init__(self, app: ASGIApp, log: list[InnerRequest]) -> None:
        self._app = app
        self._log = log

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Record an HTTP request and hand the call to the wrapped application."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        query = parse_qs(scope["query_string"].decode(), keep_blank_values=True)
        index = len(self._log)
        self._log.append(InnerRequest(scope["method"], scope["path"], query))

        async def send_and_note_status(message: Message) -> None:
            if message["type"] == "http.response.start":
                self._log[index] = replace(self._log[index], status=message["status"])
            await send(message)

        await self._app(scope, receive, send_and_note_status)


def record_inner_requests(monkeypatch: pytest.MonkeyPatch) -> list[InnerRequest]:
    """Make every assistant turn of the test send its API reads through a recorder.

    The route builds the turn's client by the name ``UserApiClient`` in
    :mod:`api.assistant.deps`, so the name is replaced there, for this test only, by a
    subclass that wraps the application it is given.

    :param monkeypatch: The test's monkeypatch fixture.
    :return: The list the requests are appended to, empty until a turn runs.
    """
    log: list[InnerRequest] = []

    class RecordingUserApiClient(UserApiClient):
        """The assistant's client, reading through :class:`RecordingApp`."""

        def __init__(self, app: ASGIApp, access_token: str, client_ip: str) -> None:
            super().__init__(RecordingApp(app, log), access_token, client_ip)

    monkeypatch.setattr(deps, "UserApiClient", RecordingUserApiClient)
    return log


class HookedEchoModel(ToolEchoingModel):
    """A tool-echoing model that runs a callback before its first reply.

    :ivar before_first_call: What to do when the model is first asked, which is after the
        request has been authenticated and before any tool has run.
    """

    before_first_call: Callable[[], None]

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Run the callback on the first call, then answer as the echoing model does."""
        if not self.seen:
            self.before_first_call()
        return super()._generate(messages, stop, run_manager, **kwargs)


class StreamingToolCallModel(ScriptedToolCallingModel):
    """A scripted model whose streamed reply is a piece of text and then its tool calls."""

    async def _astream(
        self, messages: list[BaseMessage], *args: Any, **kwargs: Any
    ) -> AsyncIterator[ChatGenerationChunk]:
        """Stream the text of the next reply, then each of its tool calls as a chunk."""
        self.seen.append(list(messages))
        response = self.responses[self._call_count]
        self._call_count += 1
        yield ChatGenerationChunk(message=AIMessageChunk(content=response.text))
        for index, call in enumerate(response.tool_calls):
            arguments = json.dumps(call["args"])
            chunk = AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {"name": call["name"], "args": arguments, "id": call["id"], "index": index}
                ],
            )
            yield ChatGenerationChunk(message=chunk)


class InterleavingModel(BaseChatModel):
    """A chat model that answers two turns at once, each held until the other has arrived.

    One instance serves both turns, as the application's one process-wide answer model does.
    A turn is told apart by the marker its question contains. Before each model call the turn
    waits at a barrier that only the other turn's call releases, so the two turns are both
    inside the model, with their traces open, at every step.

    :ivar projects: The project id of each turn, by marker.
    :ivar answers: What each turn finally answers, by marker.
    :ivar call_tools: Whether a turn first asks for the opinions of its project.
    :ivar barriers: One barrier of two parties for each model call a turn makes.
    :ivar inside: How many turns are inside the model now.
    :ivar peaks: How many turns were inside the model when each call came in, in call order.
    """

    # Kept out of the model's repr, which a trace records as the model's configuration: the
    # names of one project would otherwise sit in the trace of the other.
    projects: dict[str, str] = Field(repr=False)
    answers: dict[str, str] = Field(repr=False)
    call_tools: bool
    barriers: list[Any] = Field(repr=False)
    inside: int = 0
    peaks: list[int] = Field(default_factory=list)

    def bind_tools(self, tools: Any, **kwargs: Any) -> "InterleavingModel":
        """Return this model unchanged; the replies already carry their tool calls."""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise AssertionError("the interleaving model is only called asynchronously")

    @property
    def _llm_type(self) -> str:
        """Return the model type name LangChain's tracing uses."""
        return "interleaving-model"

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Wait for the other turn's call, then reply as the turn this call belongs to."""
        asked = " ".join(message.text for message in messages if isinstance(message, HumanMessage))
        marker = next(marker for marker in self.projects if marker in asked)
        replied = any(isinstance(message, ToolMessage) for message in messages)
        self.inside += 1
        self.peaks.append(self.inside)
        try:
            await asyncio.wait_for(self.barriers[int(replied)].wait(), 15)
        finally:
            self.inside -= 1
        if self.call_tools and not replied:
            reply = tool_call_of("get_project_opinions", {"project_id": self.projects[marker]})
        else:
            reply = AIMessage(content=self.answers[marker])
        return ChatResult(generations=[ChatGeneration(message=reply)])


def traces_by_marker(bodies: list[str]) -> dict[str, str]:
    """Group the request bodies of a capturing LangSmith client by trace.

    :param bodies: The body of every request the client made, as text.
    :return: The text of every run of a trace, joined, by the part of the root run's question
        before its first colon: the marker a turn's question starts with.
    """
    runs = [json.loads(body) for body in bodies]
    trace_of_run = {run["id"]: run["trace_id"] for run in runs if "trace_id" in run}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        trace_id = run.get("trace_id") or trace_of_run.get(run.get("id"))
        grouped.setdefault(str(trace_id), []).append(run)
    traces = {}
    for trace_runs in grouped.values():
        root = next(run for run in trace_runs if run.get("name") == "assistant_turn")
        text = "\n".join(json.dumps(run, ensure_ascii=False) for run in trace_runs)
        traces[root["inputs"]["question"].split(":")[0]] = text
    return traces


# The people of the two projects the interleaving tests build, with names, positions and
# numbers that exist nowhere else: (first name, last name, position, (lower, peak, upper)).
PEOPLE = {
    "ALPHA": [
        ("Anselma", "Brunnenmeister", "Glacier Cartographer", (10.25, 20.25, 30.25)),
        ("Cyprian", "Dunkelwald", "Fjord Ferryman", (11.25, 21.25, 31.25)),
    ],
    "BRAVO": [
        ("Eulalia", "Finsterwalder", "Dune Surveyor", (70.75, 80.75, 90.75)),
        ("Gottlieb", "Hellmuth", "Reef Gardener", (71.75, 81.75, 91.75)),
    ],
}


def sign_up(client: TestClient, email: str, first_name: str, last_name: str) -> str:
    """Register and activate an account, log it in and return its access token."""
    register_verified(client, email, first_name=first_name, last_name=last_name)
    login = client.post(
        "/api/v1/auth/login", data={"username": email, "password": DEFAULT_TEST_PASSWORD}
    )
    client.cookies.clear()
    return str(login.json()["access_token"])


def two_member_project(client: TestClient, tag: str, project_name: str) -> dict[str, str]:
    """Create a project of the two experts of ``PEOPLE[tag]``, each with an opinion.

    :return: The project's id and the first expert's access token.
    """
    first, second = PEOPLE[tag]
    first_token = sign_up(client, f"{tag.lower()}-0@example.com", first[0], first[1])
    second_email = f"{tag.lower()}-1@example.com"
    second_token = sign_up(client, second_email, second[0], second[1])
    project = create_project(client, first_token, name=project_name)
    submit_opinion(client, first_token, project["id"], *first[3], first[2])
    invitation = client.post(
        f"/api/v1/projects/{project['id']}/invite",
        json={"email": second_email},
        headers=auth_header(first_token),
    )
    client.post(
        f"/api/v1/invitations/{invitation.json()['id']}/accept", headers=auth_header(second_token)
    )
    submit_opinion(client, second_token, project["id"], *second[3], second[2])
    return {"id": project["id"], "token": first_token}


@contextmanager
def pooled_app_client(directory: Path) -> Iterator[TestClient]:
    """Build a test client whose application reads a file database through a pool of one.

    Two turns that overlap would share the one connection of an in-memory database from two
    threads. Here each read waits its turn for the pooled connection, so the turns overlap
    in the model and never in the database.

    :param directory: Where the database file goes.
    """
    engine = create_engine(
        f"sqlite:///{directory / 'interleaved.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=20,
    )
    SQLModel.metadata.create_all(engine)
    app = create_test_app()

    def pooled_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = pooled_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        engine.dispose()
