"""Tests for AssistantService: one chat turn in each of the three modes."""

import asyncio
import logging
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Literal
from unittest.mock import AsyncMock, patch

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import Field
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from api.assistant.agent import service as service_module
from api.assistant.agent.checks import find_ungrounded_numbers, strip_citations
from api.assistant.agent.context import AssistantContext, SourceRegistry
from api.assistant.agent.prompt import (
    FORMULA_NUMBERS,
    PINNED_NUMBERS,
    SYSTEM_PROMPT,
    render_context_block,
)
from api.assistant.agent.service import AssistantService
from api.assistant.agent.tools import ASSISTANT_TOOLS, render_opinions, render_project
from api.assistant.client import UserApiClient
from api.assistant.errors import (
    AssistantNotFoundError,
    AssistantUnavailableError,
    AssistantUpstreamError,
)
from api.assistant.rag.retrieval import DocsRetriever, RetrievedChunk
from api.assistant.views import FuzzyView, OpinionView, ProjectView, ResultView
from api.config import Settings
from api.exceptions import ProjectNotFoundError
from api.schemas.assistant import AssistantChatRequest, ChatTurn
from tests.shared.assistant_fakes import ScriptedToolCallingModel
from tests.shared.helpers import captured_log_records

PROJECT_ID = "3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b"
QUESTION = "What is the compromise?"
EXCERPTS = "Excerpts:\n\n[1] Method - Step 3\nThe compromise is the midpoint."
_REQUEST = httpx.Request("GET", "http://localhost/x")
SERVICE_LOGGER = "api.assistant.agent.service"


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch, tmp_path):
    """Keep Settings away from the repository's own .env file."""
    monkeypatch.chdir(tmp_path)


def _settings(mode: str = "workflow", **overrides: Any) -> Settings:
    fields: dict[str, Any] = {
        "secret_key": "test-secret-key",  # pragma: allowlist secret
        "assistant_mode": mode,
        "assistant_max_tool_calls": 4,
        "assistant_max_history_turns": 10,
        "assistant_turn_timeout_seconds": 30.0,
        "assistant_answer_llm_model": "test-answer-model",
    }
    return Settings(**{**fields, **overrides})


def _chunk(chunk_text: str = "The compromise is the midpoint.") -> RetrievedChunk:
    return RetrievedChunk(
        text=f"A caption.\n\n{chunk_text}",
        title="Method",
        section="Step 3",
        url=None,
        layer="public",
        score=0.9,
        chunk_text=chunk_text,
    )


def _project() -> ProjectView:
    return ProjectView(
        id=PROJECT_ID,
        name="Flood Prevention Planning",
        description="Example project",
        scale_min=0.0,
        scale_max=100.0,
        scale_unit="%",
        role="admin",
    )


def _result() -> ResultView:
    return ResultView(
        best_compromise=FuzzyView(lower=11.54, peak=14.19, upper=17.19, centroid=14.31),
        arithmetic_mean=FuzzyView(lower=17.08, peak=20.38, upper=23.38, centroid=20.28),
        median=FuzzyView(lower=6.0, peak=8.0, upper=11.0, centroid=8.33),
        max_error=5.974358974358974,
        num_experts=13,
        agreement_level="high",
        likert_value=None,
        likert_decision=None,
        calculated_at=datetime.now(UTC),
    )


def _opinion() -> OpinionView:
    return OpinionView(
        expert_name="Jana Novakova",
        position="Hydrologist",
        lower_bound=37.0,
        peak=42.0,
        upper_bound=47.0,
        centroid=42.0,
    )


def _ctx(
    *,
    chunks: list[RetrievedChunk] | None = None,
    project_id: str | None = None,
    result: ResultView | None = None,
    opinions: list[OpinionView] | None = None,
) -> AssistantContext:
    retriever = AsyncMock(spec=DocsRetriever)
    retriever.search.return_value = chunks or []
    client = AsyncMock(spec=UserApiClient)
    client.get_project.return_value = _project()
    client.get_result.return_value = result
    client.get_opinions.return_value = opinions or []
    client.list_projects.return_value = []
    return AssistantContext(
        client=client,
        retriever=retriever,
        sources=SourceRegistry(),
        tool_outputs=[],
        current_project_id=project_id,
        locale="en",
    )


def _request(message: str = QUESTION, history: list[ChatTurn] | None = None):
    return AssistantChatRequest(message=message, history=history or [])


def _model(*responses: AIMessage) -> ScriptedToolCallingModel:
    return ScriptedToolCallingModel(responses=[*responses])


def _say(text: str = "It is the midpoint.") -> AIMessage:
    return AIMessage(content=text)


def _call(name: str, index: int = 1, **args: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": f"call-{index}", "type": "tool_call"}],
    )


def _shown(model: ScriptedToolCallingModel, call: int = 0):
    """Return the system message and the messages after it of one model call."""
    messages = model.seen[call]
    # An agent gives each message an id, which is not what the tests compare.
    return messages[0], [type(message)(content=message.content) for message in messages[1:]]


def _turn(role: Literal["user", "assistant"], content: str) -> ChatTurn:
    return ChatTurn(role=role, content=content)


def _unavailable_errors() -> list[Exception]:
    response = httpx.Response(500, request=_REQUEST)
    return [
        openai.APIConnectionError(request=_REQUEST),
        openai.APIStatusError("secret-host said no", response=response, body=None),
        httpx.ConnectError("secret-host:1234 refused"),
        httpx.HTTPStatusError("secret-host said no", request=_REQUEST, response=response),
        OperationalError("SELECT 1", {}, Exception("connection to secret-host lost")),
        InterfaceError("SELECT 1", {}, Exception("connection to secret-host closed")),
        PoolTimeoutError("QueuePool limit reached, connection to secret-host timed out"),
    ]


class _SleepingModel(ScriptedToolCallingModel):
    """A model that never answers in time."""

    async def _agenerate(self, *args: Any, **kwargs: Any):
        await asyncio.sleep(30)


class _FailingModel(ScriptedToolCallingModel):
    """A model whose every call raises the given error."""

    error: Any = None

    def _generate(self, *args: Any, **kwargs: Any):
        raise self.error


class _ToolBindingModel(ScriptedToolCallingModel):
    """A model that notes which tools it was given."""

    bound: list[str] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        self.bound.extend(tool.name for tool in tools)
        return self


class _TracedModel(ScriptedToolCallingModel):
    """A model that notes, in a shared list, that it was called."""

    events: list[str] = Field(default_factory=list)

    def _generate(self, *args: Any, **kwargs: Any):
        self.events.append("model")
        return super()._generate(*args, **kwargs)


@pytest.mark.asyncio
class TestWorkflowMode:
    """Workflow mode fetches ahead of the model and makes one call with no tools."""

    async def test_answers_with_one_call_and_reports_no_tools(self):
        """
        GIVEN a workflow service and a model that answers once
        WHEN a turn is answered
        THEN the answer comes back after a single model call and no tool is reported
        """
        model = _model(_say("BeCoMe combines a mean and a median."))

        response = await AssistantService(_settings(), model).answer(_request(), _ctx())

        assert response.answer == "BeCoMe combines a mean and a median."
        assert response.tools_used == []
        assert len(model.seen) == 1

    async def test_sends_the_system_prompt_unchanged_and_the_excerpts_before_the_question(self):
        """
        GIVEN a retriever that finds one passage
        WHEN a turn is answered
        THEN the system message is the system prompt alone, and the user message is the
             excerpts block, a blank line and the question
        """
        model = _model(_say("It is the midpoint [1]."))
        ctx = _ctx(chunks=[_chunk()])

        response = await AssistantService(_settings(), model).answer(_request(), ctx)

        system, rest = _shown(model)
        assert system == SystemMessage(content=SYSTEM_PROMPT)
        assert rest == [HumanMessage(content=f"{EXCERPTS}\n\nQuestion: {QUESTION}")]
        assert [ref.title for ref in response.sources] == ["Method"]
        assert response.checks.citations_valid is True
        ctx.retriever.search.assert_awaited_once_with(QUESTION)

    async def test_sends_the_bare_message_when_there_is_nothing_to_show(self):
        """
        GIVEN a retriever that finds nothing and a request that names no project
        WHEN a turn is answered
        THEN the user message is the message itself
        """
        model = _model(_say())

        await AssistantService(_settings(), model).answer(_request(), _ctx())

        assert _shown(model)[1] == [HumanMessage(content=QUESTION)]

    async def test_fetches_the_project_its_result_and_its_opinions_for_a_named_project(self):
        """
        GIVEN a request that names a project which has a result and opinions
        WHEN a turn is answered
        THEN the user message holds the excerpts, the project, its result, its opinions
             and the question, in that order, with no project-id line, and all three are
             kept as grounding
        """
        model = _model(_say())
        ctx = _ctx(
            chunks=[_chunk()], project_id=PROJECT_ID, result=_result(), opinions=[_opinion()]
        )
        blocks = [
            render_project(_project()),
            render_context_block([], _result()),
            render_opinions([_opinion()]),
        ]

        await AssistantService(_settings(), model).answer(_request(), ctx)

        content = _shown(model)[1][0].content
        assert content == "\n\n".join([EXCERPTS, *blocks, f"Question: {QUESTION}"])
        assert "Current project id" not in content
        assert ctx.tool_outputs == blocks
        ctx.client.get_opinions.assert_awaited_once_with(PROJECT_ID)

    async def test_leaves_out_the_blocks_that_have_nothing_to_show(self):
        """
        GIVEN a named project with no result yet and no opinions
        WHEN a turn is answered
        THEN only the project block is shown, and no error is raised
        """
        model = _model(_say())
        ctx = _ctx(project_id=PROJECT_ID, result=None, opinions=[])

        await AssistantService(_settings(), model).answer(_request(), ctx)

        assert _shown(model)[1][0].content == (
            f"{render_project(_project())}\n\nQuestion: {QUESTION}"
        )
        assert ctx.tool_outputs == [render_project(_project())]

    async def test_a_blank_answer_is_a_failure_not_an_answer(self):
        """
        GIVEN a model whose whole reply is a reasoning block
        WHEN a turn is answered
        THEN AssistantUnavailableError is raised and one warning names the event and the mode
        """
        model = _model(_say("<think>I ran out of tokens</think>"))

        with (
            captured_log_records(SERVICE_LOGGER) as records,
            pytest.raises(AssistantUnavailableError),
        ):
            await AssistantService(_settings(), model).answer(_request(), _ctx())

        (record,) = records
        assert record.levelno == logging.WARNING
        assert (record.event, record.mode) == ("assistant_empty_answer", "workflow")

    async def test_strips_the_reasoning_block_from_the_answer(self):
        """
        GIVEN a model that thinks aloud before answering
        WHEN a turn is answered
        THEN the answer carries no reasoning
        """
        model = _model(_say("<think>hmm</think>It is the midpoint."))

        response = await AssistantService(_settings(), model).answer(_request(), _ctx())

        assert response.answer == "It is the midpoint."


@pytest.mark.asyncio
class TestTools:
    """Only agent and hybrid give the model the five tools."""

    @pytest.mark.parametrize(
        ("mode", "gets_tools"), [("workflow", False), ("hybrid", True), ("agent", True)]
    )
    async def test_the_model_is_given_tools_in_agent_and_hybrid_only(self, mode, gets_tools):
        """
        GIVEN a model that notes the tools bound to it
        WHEN a turn is answered in each mode
        THEN workflow binds none, and the other two bind exactly the assistant's five
        """
        model = _ToolBindingModel(responses=[_say()])

        await AssistantService(_settings(mode), model).answer(_request(), _ctx())

        expected = {tool.name for tool in ASSISTANT_TOOLS} if gets_tools else set()
        assert set(model.bound) == expected


@pytest.mark.asyncio
class TestHybridMode:
    """Hybrid mode fetches the project and its result, then lets the model use the tools."""

    async def test_fetches_the_project_and_result_but_leaves_opinions_to_the_tool(self):
        """
        GIVEN a named project with a result and opinions
        WHEN a hybrid turn is answered
        THEN the project and its result are in the user message, the opinions are not
             fetched, and the project-id line comes right before the question
        """
        model = _model(_say())
        ctx = _ctx(
            chunks=[_chunk()], project_id=PROJECT_ID, result=_result(), opinions=[_opinion()]
        )
        blocks = [render_project(_project()), render_context_block([], _result())]

        await AssistantService(_settings("hybrid"), model).answer(_request(), ctx)

        system, rest = _shown(model)
        assert system == SystemMessage(content=SYSTEM_PROMPT)
        assert rest == [
            HumanMessage(
                content="\n\n".join(
                    [
                        EXCERPTS,
                        *blocks,
                        f"Current project id: {PROJECT_ID}",
                        f"Question: {QUESTION}",
                    ]
                )
            )
        ]
        ctx.client.get_opinions.assert_not_awaited()
        assert ctx.tool_outputs == blocks

    async def test_can_answer_from_the_prefetch_alone(self):
        """
        GIVEN a model that answers without calling a tool
        WHEN a hybrid turn is answered
        THEN the answer comes back after one model call and no tool is reported
        """
        model = _model(_say("No further lookup needed."))

        response = await AssistantService(_settings("hybrid"), model).answer(_request(), _ctx())

        assert response.answer == "No further lookup needed."
        assert response.tools_used == []
        assert len(model.seen) == 1

    async def test_reports_the_tool_the_model_used(self):
        """
        GIVEN a model that asks for the opinions of the named project and then answers
        WHEN a hybrid turn is answered
        THEN the opinions were read through the tool and get_project_opinions is reported
        """
        model = _model(
            _call("get_project_opinions", project_id=PROJECT_ID), _say("They range widely.")
        )
        ctx = _ctx(project_id=PROJECT_ID, result=_result(), opinions=[_opinion()])

        response = await AssistantService(_settings("hybrid"), model).answer(_request(), ctx)

        assert response.tools_used == ["get_project_opinions"]
        ctx.client.get_opinions.assert_awaited_once_with(PROJECT_ID)
        assert render_opinions([_opinion()]) in ctx.tool_outputs

    async def test_sends_no_project_line_when_the_request_names_no_project(self):
        """
        GIVEN a request with no project and no passages
        WHEN a hybrid turn is answered
        THEN the user message is the bare message
        """
        model = _model(_say())

        await AssistantService(_settings("hybrid"), model).answer(_request(), _ctx())

        assert _shown(model)[1] == [HumanMessage(content=QUESTION)]


@pytest.mark.asyncio
class TestAgentMode:
    """Agent mode fetches nothing ahead of the model."""

    async def test_answers_after_a_tool_and_fetches_nothing_itself(self):
        """
        GIVEN a model that searches the documents and then answers
        WHEN an agent turn is answered
        THEN the only search is the tool's, and search_docs is reported
        """
        model = _model(_call("search_docs", query="compromise"), _say("It is the midpoint [1]."))
        ctx = _ctx(chunks=[_chunk()])

        response = await AssistantService(_settings("agent"), model).answer(_request(), ctx)

        assert response.tools_used == ["search_docs"]
        assert [ref.n for ref in response.sources] == [1]
        assert response.checks.citations_valid is True
        ctx.retriever.search.assert_awaited_once_with("compromise")

    async def test_shows_the_bare_message_and_no_project_fetch(self):
        """
        GIVEN a request with no project
        WHEN an agent turn is answered
        THEN the model saw the system prompt and the bare message, and nothing was fetched
        """
        model = _model(_say())
        ctx = _ctx(chunks=[_chunk()])

        await AssistantService(_settings("agent"), model).answer(_request(), ctx)

        system, rest = _shown(model)
        assert system == SystemMessage(content=SYSTEM_PROMPT)
        assert rest == [HumanMessage(content=QUESTION)]
        ctx.retriever.search.assert_not_awaited()

    async def test_names_the_current_project_in_the_message(self):
        """
        GIVEN a request that names a project
        WHEN an agent turn is answered
        THEN the model is told the project id before the question, and no project is fetched
        """
        model = _model(_say())
        ctx = _ctx(project_id=PROJECT_ID, result=_result())

        await AssistantService(_settings("agent"), model).answer(_request(), ctx)

        assert _shown(model)[1] == [
            HumanMessage(content=f"Current project id: {PROJECT_ID}\n\nQuestion: {QUESTION}")
        ]
        ctx.client.get_project.assert_not_awaited()
        ctx.client.get_result.assert_not_awaited()

    async def test_a_blank_answer_after_the_fallback_call_is_a_failure(self):
        """
        GIVEN a model that asks for tools that do not exist until the model-call limit, and
              whose fallback call only thinks
        WHEN an agent turn is answered
        THEN AssistantUnavailableError is raised and one warning names the event and the mode
        """
        model = _model(
            *(_call("nope", index) for index in range(1, 5)), _say("<think>no tokens left</think>")
        )
        settings = _settings("agent", assistant_max_tool_calls=2)

        with (
            captured_log_records(SERVICE_LOGGER) as records,
            pytest.raises(AssistantUnavailableError),
        ):
            await AssistantService(settings, model).answer(_request(), _ctx())

        (record,) = records
        assert (record.event, record.mode) == ("assistant_empty_answer", "agent")
        assert len(model.seen) == 5


@pytest.mark.asyncio
class TestFailures:
    """What the caller gets when the project, a server or the clock lets the turn down."""

    @pytest.mark.parametrize(
        ("mode", "failing"),
        [
            ("workflow", "get_project"),
            ("workflow", "get_result"),
            ("workflow", "get_opinions"),
            ("hybrid", "get_project"),
            ("hybrid", "get_result"),
        ],
    )
    async def test_a_project_the_caller_cannot_see_is_a_project_not_found(self, mode, failing):
        """
        GIVEN a named project that the API answers 404 for, at any read the mode makes
        WHEN a turn is answered
        THEN ProjectNotFoundError is raised, as the UI's own project route raises it, and
             the model is never called
        """
        model = _model(_say())
        ctx = _ctx(project_id=PROJECT_ID, result=_result(), opinions=[_opinion()])
        getattr(ctx.client, failing).side_effect = AssistantNotFoundError("404")

        with pytest.raises(ProjectNotFoundError, match=f"Project {PROJECT_ID} not found"):
            await AssistantService(_settings(mode), model).answer(_request(), ctx)

        assert model.seen == []

    async def test_an_unusable_answer_from_the_api_propagates_untouched(self):
        """
        GIVEN a named project whose read fails with AssistantUpstreamError
        WHEN a turn is answered
        THEN the same error reaches the caller, for the handler that answers 503
        """
        ctx = _ctx(project_id=PROJECT_ID)
        ctx.client.get_project.side_effect = AssistantUpstreamError("500")

        with pytest.raises(AssistantUpstreamError):
            await AssistantService(_settings(), _model(_say())).answer(_request(), ctx)

    @pytest.mark.parametrize("mode", ["workflow", "hybrid", "agent"])
    @pytest.mark.parametrize("error", _unavailable_errors(), ids=lambda e: type(e).__name__)
    async def test_a_model_server_that_fails_is_unavailable(self, mode, error):
        """
        GIVEN a model that raises a connection, status or database error
        WHEN a turn is answered
        THEN AssistantUnavailableError is raised and one warning carries the error's class
             name as the reason and none of its text
        """
        model = _FailingModel(responses=[], error=error)

        with (
            captured_log_records(SERVICE_LOGGER) as records,
            pytest.raises(AssistantUnavailableError) as raised,
        ):
            await AssistantService(_settings(mode), model).answer(_request(), _ctx())

        (record,) = records
        assert record.levelno == logging.WARNING
        assert record.event == "assistant_dependency_unavailable"
        assert record.reason == type(error).__name__
        assert record.exc_info is None
        assert "secret-host" not in record.getMessage()
        assert "secret-host" not in str(raised.value)

    @pytest.mark.parametrize("mode", ["workflow", "hybrid"])
    @pytest.mark.parametrize("error", _unavailable_errors(), ids=lambda e: type(e).__name__)
    async def test_a_retriever_that_fails_is_unavailable(self, mode, error):
        """
        GIVEN a document retriever that raises a connection, status or database error
        WHEN a turn is answered
        THEN AssistantUnavailableError is raised, the reason is the error's class name and
             the model is never called
        """
        model = _model(_say())
        ctx = _ctx()
        ctx.retriever.search.side_effect = error

        with (
            captured_log_records(SERVICE_LOGGER) as records,
            pytest.raises(AssistantUnavailableError),
        ):
            await AssistantService(_settings(mode), model).answer(_request(), ctx)

        assert [(r.event, r.reason) for r in records] == [
            ("assistant_dependency_unavailable", type(error).__name__)
        ]
        assert model.seen == []

    @pytest.mark.parametrize(
        "error", [ValueError("a bug"), IntegrityError("INSERT", {}, Exception("a bug"))]
    )
    async def test_an_error_that_is_not_an_outage_is_not_turned_into_one(self, error):
        """
        GIVEN a retriever that raises a plain ValueError, or a database data error
        WHEN a turn is answered
        THEN the error reaches the caller, so a bug is not reported as an outage
        """
        ctx = _ctx()
        ctx.retriever.search.side_effect = error

        with pytest.raises(type(error), match="a bug"):
            await AssistantService(_settings(), _model(_say())).answer(_request(), ctx)

    @pytest.mark.parametrize("mode", ["workflow", "hybrid", "agent"])
    async def test_a_turn_that_outlives_its_deadline_is_unavailable(self, mode):
        """
        GIVEN a model that never answers and a turn deadline of 50 milliseconds
        WHEN a turn is answered
        THEN AssistantUnavailableError is raised after about that long and one warning
             carries the mode and the elapsed milliseconds
        """
        model = _SleepingModel(responses=[])
        settings = _settings(mode, assistant_turn_timeout_seconds=0.05)

        with (
            captured_log_records(SERVICE_LOGGER) as records,
            pytest.raises(AssistantUnavailableError),
        ):
            await AssistantService(settings, model).answer(_request(), _ctx())

        (record,) = records
        assert record.levelno == logging.WARNING
        assert (record.event, record.mode) == ("assistant_turn_timeout", mode)
        assert isinstance(record.duration_ms, int)
        assert 40 <= record.duration_ms < 5000

    async def test_the_deadline_also_covers_the_fetching(self):
        """
        GIVEN a retriever that never answers and a turn deadline of 50 milliseconds
        WHEN a turn is answered
        THEN AssistantUnavailableError is raised
        """
        ctx = _ctx()

        async def never(_query: str):
            await asyncio.sleep(30)

        ctx.retriever.search.side_effect = never
        settings = _settings(assistant_turn_timeout_seconds=0.05)

        with pytest.raises(AssistantUnavailableError):
            await AssistantService(settings, _model(_say())).answer(_request(), ctx)

    async def test_a_timeout_that_is_not_the_deadline_is_not_reported_as_one(self):
        """
        GIVEN a retriever that raises a TimeoutError of its own, well inside the deadline
        WHEN a turn is answered
        THEN that TimeoutError reaches the caller and no timeout is logged
        """
        ctx = _ctx()
        ctx.retriever.search.side_effect = TimeoutError("inner")

        with (
            captured_log_records(SERVICE_LOGGER) as records,
            pytest.raises(TimeoutError, match="inner"),
        ):
            await AssistantService(_settings(), _model(_say())).answer(_request(), ctx)

        assert records == []


@pytest.mark.asyncio
class TestHistory:
    """The history the model sees: recent, bounded in size, starting with the user."""

    @staticmethod
    async def _history_shown(history: list[ChatTurn], **overrides: Any):
        model = _model(_say())
        await AssistantService(_settings(**overrides), model).answer(
            _request(history=history), _ctx()
        )
        return [(type(m).__name__, m.content) for m in _shown(model)[1][:-1]]

    async def test_keeps_the_last_two_entries_per_configured_turn(self):
        """
        GIVEN a history of six entries and a limit of two turns
        WHEN a turn is answered
        THEN the model sees the last four entries, oldest first, then the message
        """
        history = [_turn("user" if i % 2 == 0 else "assistant", f"e{i}") for i in range(6)]

        shown = await self._history_shown(history, assistant_max_history_turns=2)

        assert shown == [
            ("HumanMessage", "e2"),
            ("AIMessage", "e3"),
            ("HumanMessage", "e4"),
            ("AIMessage", "e5"),
        ]

    async def test_drops_a_leading_assistant_entry(self):
        """
        GIVEN five entries and a limit of two turns, so the last four start with an
              assistant entry
        WHEN a turn is answered
        THEN that entry is dropped and the history starts with the user
        """
        history = [_turn("user" if i % 2 == 0 else "assistant", f"e{i}") for i in range(5)]

        shown = await self._history_shown(history, assistant_max_history_turns=2)

        assert shown == [("HumanMessage", "e2"), ("AIMessage", "e3"), ("HumanMessage", "e4")]

    async def test_drops_every_leading_assistant_entry(self):
        """
        GIVEN a client-made history that opens with two assistant entries
        WHEN a turn is answered
        THEN both are dropped
        """
        history = [_turn("assistant", "a1"), _turn("assistant", "a2"), _turn("user", "u1")]

        assert await self._history_shown(history) == [("HumanMessage", "u1")]

    async def test_keeps_a_leading_user_entry(self):
        """
        GIVEN a history that already starts with the user
        WHEN a turn is answered
        THEN nothing is dropped
        """
        history = [_turn("user", "u1"), _turn("assistant", "a1")]

        assert await self._history_shown(history) == [
            ("HumanMessage", "u1"),
            ("AIMessage", "a1"),
        ]

    async def test_drops_the_oldest_entries_until_the_history_fits_the_budget(self):
        """
        GIVEN four entries of 2000, 2000, 2000 and 1500 characters, 7500 in all
        WHEN a turn is answered
        THEN the oldest is dropped and, because the rest then starts with an assistant
             entry, that goes too, leaving the last two whole
        """
        history = [
            _turn("user", "a" * 2000),
            _turn("assistant", "b" * 2000),
            _turn("user", "c" * 2000),
            _turn("assistant", "d" * 1500),
        ]

        shown = await self._history_shown(history)

        assert shown == [("HumanMessage", "c" * 2000), ("AIMessage", "d" * 1500)]

    async def test_a_history_of_exactly_the_budget_is_kept_whole(self):
        """
        GIVEN two entries of 3000 characters each, 6000 in all
        WHEN a turn is answered
        THEN both are kept
        """
        history = [_turn("user", "a" * 3000), _turn("assistant", "b" * 3000)]

        shown = await self._history_shown(history)

        assert [content for _, content in shown] == ["a" * 3000, "b" * 3000]

    async def test_one_character_over_the_budget_drops_the_oldest_entry(self):
        """
        GIVEN entries of 3001 and 3000 characters, one character over the budget
        WHEN a turn is answered
        THEN the oldest is dropped and, the assistant entry then leading, that goes too
        """
        history = [_turn("user", "a" * 3001), _turn("assistant", "b" * 3000)]

        assert await self._history_shown(history) == []

    async def test_a_newest_entry_over_the_budget_leaves_the_history_empty(self):
        """
        GIVEN a short user entry followed by an assistant entry of 6001 characters
        WHEN a turn is answered
        THEN no entry is cut, and the history is empty
        """
        history = [_turn("user", "short"), _turn("assistant", "b" * 6001)]

        assert await self._history_shown(history) == []

    async def test_strips_citation_numbers_from_earlier_answers_only(self):
        """
        GIVEN an earlier answer that cites [1] and an earlier user entry that writes [1]
        WHEN a turn is answered
        THEN the answer's citation is gone and the user's own text is untouched
        """
        history = [
            _turn("user", "What does [1] mean?"),
            _turn("assistant", "It is the midpoint [1]."),
        ]

        shown = await self._history_shown(history)

        assert shown == [
            ("HumanMessage", "What does [1] mean?"),
            ("AIMessage", strip_citations("It is the midpoint [1].")),
        ]
        assert "[1]" not in shown[1][1]


@pytest.mark.asyncio
class TestChecks:
    """A failed check changes only the flags in the response."""

    async def test_an_ungrounded_number_and_a_bad_citation_only_set_flags(self):
        """
        GIVEN an answer with a number no source supports and a citation to no source
        WHEN a turn is answered
        THEN the model was called once and the response carries both flags and the number
        """
        model = _model(_say("The error is 87654 [3]."))

        response = await AssistantService(_settings(), model).answer(_request(), _ctx())

        assert len(model.seen) == 1
        assert response.answer == "The error is 87654 [3]."
        assert response.checks.citations_valid is False
        assert response.checks.numbers_grounded is False
        assert response.checks.ungrounded_numbers == ["87654"]

    async def test_a_number_from_the_users_message_is_grounded(self):
        """
        GIVEN a question that contains the number 4711
        WHEN the answer repeats it
        THEN it is grounded
        """
        model = _model(_say("You wrote 4711."))

        response = await AssistantService(_settings(), model).answer(
            _request("Is 4711 too high?"), _ctx()
        )

        assert response.checks.ungrounded_numbers == []

    async def test_a_number_from_the_users_own_earlier_entry_is_grounded(self):
        """
        GIVEN a user entry in the history that contains the number 4711
        WHEN the answer repeats it
        THEN it is grounded
        """
        model = _model(_say("You wrote 4711."))
        history = [_turn("user", "My budget is 4711."), _turn("assistant", "Noted.")]

        response = await AssistantService(_settings(), model).answer(
            _request(history=history), _ctx()
        )

        assert response.checks.ungrounded_numbers == []

    async def test_a_number_only_an_earlier_assistant_entry_holds_is_not_grounded(self):
        """
        GIVEN an assistant entry in the history that contains the number 4711 and no source
              or user text that does
        WHEN the answer repeats it
        THEN it is reported as ungrounded
        """
        model = _model(_say("The figure is 4711."))
        history = [_turn("user", "Hello"), _turn("assistant", "It was 4711.")]

        response = await AssistantService(_settings(), model).answer(
            _request(history=history), _ctx()
        )

        assert response.checks.ungrounded_numbers == ["4711"]

    async def test_the_pinned_thresholds_and_formula_divisors_are_grounded(self):
        """
        GIVEN an answer that names the agreement thresholds 20 and 40 and the divisors 2 and 3
        WHEN a turn is answered
        THEN none is reported
        """
        model = _model(_say("Up to 20 percent, then 40; divide by 2 or by 3."))

        response = await AssistantService(_settings(), model).answer(_request(), _ctx())

        assert response.checks.ungrounded_numbers == []

    async def test_a_prefetched_project_number_is_grounded(self):
        """
        GIVEN a named project whose result was fetched ahead of the model
        WHEN the answer quotes a number from it and one that is not there
        THEN only the invented one is reported
        """
        model = _model(_say("The peak is 14.19 and the spread is 99.99."))
        ctx = _ctx(project_id=PROJECT_ID, result=_result())

        response = await AssistantService(_settings(), model).answer(_request(), ctx)

        assert response.checks.ungrounded_numbers == ["99.99"]

    async def test_the_grounding_texts_are_exactly_the_sources_the_user_and_the_pins(self):
        """
        GIVEN a turn with a source, a fetched project and a history of both roles
        WHEN the answer is checked
        THEN the grounding texts are the registry's texts, the tool outputs, the message,
             the user's own history entries, the pinned numbers and the formula divisors,
             and never the system prompt or an assistant entry
        """
        model = _model(_say("Fine."))
        ctx = _ctx(chunks=[_chunk()], project_id=PROJECT_ID, result=_result())
        history = [_turn("user", "earlier question"), _turn("assistant", "earlier answer")]

        with patch.object(
            service_module, "find_ungrounded_numbers", wraps=find_ungrounded_numbers
        ) as spy:
            await AssistantService(_settings(), model).answer(_request(history=history), ctx)

        texts = spy.call_args.args[1]
        assert sorted(texts) == sorted(
            [
                *ctx.sources.texts(),
                *ctx.tool_outputs,
                QUESTION,
                "earlier question",
                *PINNED_NUMBERS,
                *FORMULA_NUMBERS,
            ]
        )
        assert SYSTEM_PROMPT not in texts


@pytest.mark.asyncio
class TestObservability:
    """One record per answered turn, and generation runs inside the tracing scope."""

    async def test_logs_one_record_per_turn_with_counts_and_no_text(self):
        """
        GIVEN a hybrid turn that uses a tool, with a named project and a source
        WHEN it is answered
        THEN one INFO record carries the mode, the model, the tool names, the counts, the
             flags and the duration, and no field holds the message, the answer or an id
        """
        message = "Zebra question about the compromise"
        answer = "Zebra answer: the compromise is the midpoint [1]."
        model = _model(_call("list_my_projects"), _say(answer))
        ctx = _ctx(chunks=[_chunk()], project_id=PROJECT_ID, result=_result())

        with captured_log_records(SERVICE_LOGGER) as records:
            await AssistantService(_settings("hybrid"), model).answer(_request(message), ctx)

        (record,) = records
        assert record.levelno == logging.INFO
        assert record.event == "assistant_turn"
        assert record.mode == "hybrid"
        assert record.model == "test-answer-model"
        assert record.tool_names == ["list_my_projects"]
        assert record.tool_call_count == 1
        assert record.source_count == 1
        assert record.citations_valid is True
        assert record.numbers_grounded is True
        assert record.ungrounded_number_count == 0
        assert isinstance(record.duration_ms, int)
        texts = [str(value) for value in vars(record).values()]
        assert not any(
            secret in text for text in texts for secret in ("Zebra", "midpoint", PROJECT_ID)
        )

    async def test_the_record_counts_the_ungrounded_numbers(self):
        """
        GIVEN an answer with two invented numbers and a bad citation
        WHEN the turn is answered
        THEN the record carries the two flags as False and the count 2
        """
        model = _model(_say("It is 87654 and 45678 [2]."))

        with captured_log_records(SERVICE_LOGGER) as records:
            await AssistantService(_settings(), model).answer(_request(), _ctx())

        (record,) = records
        assert record.citations_valid is False
        assert record.numbers_grounded is False
        assert record.ungrounded_number_count == 2

    @pytest.mark.parametrize("mode", ["workflow", "hybrid", "agent"])
    async def test_generation_runs_inside_the_tracing_scope(self, mode):
        """
        GIVEN a tracing scope that notes when it opens and closes
        WHEN a turn is answered in any mode
        THEN the model was called between the two
        """
        model = _TracedModel(responses=[_say()])

        @contextmanager
        def scope(settings):
            model.events.append("open")
            try:
                yield
            finally:
                model.events.append("close")

        with patch.object(service_module, "tracing_scope", scope):
            await AssistantService(_settings(mode), model).answer(_request(), _ctx())

        assert model.events == ["open", "model", "close"]
