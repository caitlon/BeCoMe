"""Probes and doubles for the assistant's security tests, built on ``assistant_fakes``.

The assistant reads the application through an in-process ASGI transport, so a test cannot see
those requests on a network. :func:`record_inner_requests` puts a recording wrapper between the
client and the application. :class:`HookedEchoModel` scripts what ``ToolEchoingModel``
cannot: a callback before the first reply.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import parse_qs

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.assistant import deps
from api.assistant.client import UserApiClient
from tests.shared.assistant_fakes import ToolEchoingModel


def tool_call_of(name: str, args: dict[str, Any], call_id: str = "call_1") -> AIMessage:
    """Build a model reply that calls one tool with exactly the given arguments."""
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}]
    )


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
