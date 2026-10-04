"""Tests for the two ways an assistant answer is generated: one model call, or an agent."""

import json
import logging
from unittest.mock import AsyncMock

import pytest
from langchain.agents.middleware import ToolCallRequest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from api.assistant.agent.context import AssistantContext, SourceRegistry
from api.assistant.agent.generation import (
    AgentGenerator,
    CutOffAnswerError,
    DirectGenerator,
    _tool_failed,
    answer_text,
    user_message,
)
from api.assistant.agent.prompt import SYSTEM_PROMPT
from api.assistant.agent.tools import UNAVAILABLE_REPLY
from api.assistant.client import UserApiClient
from api.assistant.rag.retrieval import DocsRetriever, RetrievedChunk
from api.assistant.views import ProjectBrief
from tests.shared.assistant_fakes import ScriptedToolCallingModel
from tests.shared.helpers import captured_log_records

PROJECT_ID = "3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b"
QUESTION = "What is the compromise?"
ENGLISH_LINE = "\n\nAnswer in English."


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


def _ctx(chunks: list[RetrievedChunk] | None = None) -> AssistantContext:
    retriever = AsyncMock(spec=DocsRetriever)
    retriever.search.return_value = chunks or []
    client = AsyncMock(spec=UserApiClient)
    client.list_projects.return_value = []
    return AssistantContext(
        client=client,
        retriever=retriever,
        sources=SourceRegistry(),
        tool_outputs=[],
        current_project_id=None,
        locale="en",
    )


def _call(name: str, index: int = 1, **args: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": f"call-{index}", "type": "tool_call"}],
    )


def _brief() -> ProjectBrief:
    return ProjectBrief(id=PROJECT_ID, name="Floods", role="admin", is_example=False)


def _search(index: int = 1) -> AIMessage:
    return _call("search_docs", index, query=f"q{index}")


def _model(*responses: AIMessage) -> ScriptedToolCallingModel:
    return ScriptedToolCallingModel(responses=list(responses))


def _extra_fields(record: logging.LogRecord) -> set[str]:
    """Return the names of the fields a log call added through ``extra``."""
    plain = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}
    return set(vars(record)) - plain


def _user(content: str = QUESTION) -> list[BaseMessage]:
    return [HumanMessage(content=content)]


class TestUserMessage:
    """The user message is the context blocks, then the question, split by blank lines."""

    def test_puts_the_parts_before_the_question(self):
        """
        GIVEN two context parts and a question
        WHEN the user message is built
        THEN the parts come first, then the labelled question, separated by blank lines
        """
        assert user_message(["first", "second"], "Why does the median differ?") == (
            f"first\n\nsecond\n\nQuestion: Why does the median differ?{ENGLISH_LINE}"
        )

    def test_is_the_bare_question_when_there_is_no_context(self):
        """
        GIVEN no context parts
        WHEN the user message is built
        THEN it is the question alone, without the label
        """
        assert user_message([], "Why does the median differ?") == (
            f"Why does the median differ?{ENGLISH_LINE}"
        )


class TestAnswerText:
    """A model reply becomes plain text: no reasoning block, blocks joined."""

    def test_removes_a_think_block(self):
        """
        GIVEN a reply that starts with a reasoning block
        WHEN its text is read
        THEN only the answer is left
        """
        assert answer_text(AIMessage(content="<think>hmm</think>\nThe answer.")) == "The answer."

    def test_joins_the_text_parts_of_a_block_list_and_skips_the_rest(self):
        """
        GIVEN a reply whose content is a list of blocks, a bare string among them
        WHEN its text is read
        THEN the text parts are joined and a non-text block adds nothing
        """
        message = AIMessage(
            content=[
                {"type": "text", "text": "First. "},
                {"type": "image_url", "image_url": {"url": "data:x"}},
                "Second.",
            ]
        )

        assert answer_text(message) == "First. Second."

    def test_a_reply_cut_off_inside_its_reasoning_is_empty(self):
        """
        GIVEN a reply that opens a reasoning block and is cut off before it closes
        WHEN its text is read
        THEN the answer is empty, not the half-written reasoning
        """
        assert answer_text(AIMessage(content="<think>I was working out that")) == ""

    def test_text_before_a_reasoning_block_that_never_closes_is_still_empty(self):
        """
        GIVEN a reply with some text and then a reasoning block that never closes
        WHEN its text is read
        THEN the answer is empty
        """
        assert answer_text(AIMessage(content="Half an answer <think>and then")) == ""

    def test_a_closed_reasoning_block_followed_by_text_returns_the_text(self):
        """
        GIVEN a reply whose reasoning block closes and is followed by the answer
        WHEN its text is read
        THEN the answer is the text after the block
        """
        assert answer_text(AIMessage(content="<think>x</think>Answer.")) == "Answer."

    def test_a_second_reasoning_block_that_never_closes_is_empty(self):
        """
        GIVEN a reply with a closed reasoning block, some text and a second block cut off
        WHEN its text is read
        THEN the answer is empty
        """
        assert answer_text(AIMessage(content="<think>a</think>Text <think>b")) == ""

    def test_a_later_block_that_closes_is_left_as_written(self):
        """
        GIVEN a reply with a closed reasoning block, and a second one that also closes
        WHEN its text is read
        THEN only the first block is removed and the answer is not emptied
        """
        assert answer_text(AIMessage(content="<think>a</think>Text <think>b</think> tail")) == (
            "Text <think>b</think> tail"
        )

    def test_the_last_unclosed_block_decides_even_after_a_closed_one(self):
        """
        GIVEN a reply whose first block closes and whose last block never does
        WHEN its text is read
        THEN the answer is empty
        """
        reply = "<think>a</think>One <think>b</think> two <think>c"

        assert answer_text(AIMessage(content=reply)) == ""

    def test_a_stray_closing_tag_does_not_close_a_later_block(self):
        """
        GIVEN a reply with a closing tag written in the text, and then a block that never closes
        WHEN its text is read
        THEN the answer is empty
        """
        assert answer_text(AIMessage(content="Text </think> then <think>c")) == ""

    def test_text_with_no_reasoning_block_is_untouched(self):
        """
        GIVEN a reply with no reasoning block, only a closing tag written in the text
        WHEN its text is read
        THEN it is returned as it is, stripped
        """
        assert answer_text(AIMessage(content=" Plain answer, </think> here. ")) == (
            "Plain answer, </think> here."
        )

    def test_a_blank_reply_stays_blank(self):
        """
        GIVEN a reply that holds only whitespace after the reasoning block
        WHEN its text is read
        THEN it is the empty string, for the caller to treat as a failure
        """
        assert answer_text(AIMessage(content="<think>all my tokens</think>  ")) == ""


@pytest.mark.asyncio
class TestDirectGenerator:
    """One model call, no tools."""

    async def test_sends_the_system_prompt_then_the_messages_and_reports_no_tools(self):
        """
        GIVEN a model that answers once
        WHEN a turn with a history is generated
        THEN the model saw the system prompt and then the messages, once, and no tool ran
        """
        model = _model(AIMessage(content="It is the midpoint."))
        messages = [HumanMessage(content="Earlier"), AIMessage(content="Reply"), *_user()]

        text, tools = await DirectGenerator(model).generate(messages, _ctx(), QUESTION)

        assert (text, tools) == ("It is the midpoint.", [])
        assert len(model.seen) == 1
        assert model.seen[0] == [SystemMessage(content=SYSTEM_PROMPT), *messages]

    async def test_strips_the_reasoning_block_from_the_answer(self):
        """
        GIVEN a model that thinks aloud before answering
        WHEN the turn is generated
        THEN the answer carries no reasoning
        """
        model = _model(AIMessage(content="<think>x</think>Done."))

        text, _ = await DirectGenerator(model).generate(_user(), _ctx(), QUESTION)

        assert text == "Done."

    async def test_a_reply_cut_off_inside_its_reasoning_raises_the_cut_off_error(self):
        """
        GIVEN a model whose reply opens a reasoning block and never closes it
        WHEN the turn is generated
        THEN CutOffAnswerError is raised, which the service tells from a blank answer
        """
        model = _model(AIMessage(content="<think>I was still working out"))

        with pytest.raises(CutOffAnswerError):
            await DirectGenerator(model).generate(_user(), _ctx(), QUESTION)

    async def test_a_reply_that_is_only_a_closed_reasoning_block_is_blank_not_cut_off(self):
        """
        GIVEN a model whose whole reply is a reasoning block that closes
        WHEN the turn is generated
        THEN the text is empty and nothing is raised, so a blank answer stays a blank answer
        """
        model = _model(AIMessage(content="<think>all of it</think>"))

        text, _ = await DirectGenerator(model).generate(_user(), _ctx(), QUESTION)

        assert text == ""


@pytest.mark.asyncio
class TestAgentGenerator:
    """A tool-calling loop bounded by the tool-call and model-call limits."""

    async def test_answers_after_a_tool_and_reports_the_tool_that_ran(self):
        """
        GIVEN a model that searches the documents and then answers
        WHEN the turn is generated
        THEN the answer is the last reply and search_docs is reported
        """
        model = _model(_search(), AIMessage(content="It is the midpoint [1]."))
        ctx = _ctx([_chunk()])

        text, tools = await AgentGenerator(model, max_tool_calls=4).generate(_user(), ctx, QUESTION)

        assert (text, tools) == ("It is the midpoint [1].", ["search_docs"])
        assert [ref.title for ref in ctx.sources.refs()] == ["Method"]

    async def test_shows_the_model_the_system_prompt_and_the_messages(self):
        """
        GIVEN a model that answers at once
        WHEN a turn with a history is generated
        THEN the first call carried the system prompt, then the messages as given
        """
        model = _model(AIMessage(content="Hello."))
        messages = [HumanMessage(content="Earlier"), AIMessage(content="Reply"), *_user()]

        await AgentGenerator(model, max_tool_calls=4).generate(messages, _ctx(), QUESTION)

        assert model.seen[0][0] == SystemMessage(content=SYSTEM_PROMPT)
        assert [m.content for m in model.seen[0][1:]] == ["Earlier", "Reply", QUESTION]

    async def test_reports_each_tool_once_in_the_order_it_first_ran(self):
        """
        GIVEN a model that calls list_my_projects, search_docs, then list_my_projects again
        WHEN the turn is generated
        THEN each tool is reported once, in first-call order
        """
        model = _model(
            _call("list_my_projects", 1),
            _search(2),
            _call("list_my_projects", 3),
            AIMessage(content="Done."),
        )

        _, tools = await AgentGenerator(model, max_tool_calls=4).generate(_user(), _ctx(), QUESTION)

        assert tools == ["list_my_projects", "search_docs"]

    async def test_a_call_to_an_unknown_tool_does_not_count(self):
        """
        GIVEN a model that asks for a tool that does not exist, then answers
        WHEN the turn is generated
        THEN the answer comes back and no tool is reported
        """
        model = _model(_call("delete_everything"), AIMessage(content="I cannot do that."))

        text, tools = await AgentGenerator(model, max_tool_calls=4).generate(
            _user(), _ctx(), QUESTION
        )

        assert (text, tools) == ("I cannot do that.", [])

    async def test_a_call_with_invalid_arguments_does_not_count(self):
        """
        GIVEN a model that calls a tool with an argument it does not have, then answers
        WHEN the turn is generated
        THEN the answer comes back and no tool is reported
        """
        model = _model(
            _call("get_project_result", projectid=PROJECT_ID), AIMessage(content="Not able.")
        )

        text, tools = await AgentGenerator(model, max_tool_calls=4).generate(
            _user(), _ctx(), QUESTION
        )

        assert (text, tools) == ("Not able.", [])

    async def test_a_call_blocked_by_the_tool_limit_does_not_count_or_run(self):
        """
        GIVEN a limit of two tool calls and a model that asks three times before answering
        WHEN the turn is generated
        THEN the third call is refused without running, and the answer still arrives
        """
        model = _model(_search(1), _search(2), _search(3), AIMessage(content="Here it is."))
        ctx = _ctx([_chunk()])

        text, tools = await AgentGenerator(model, max_tool_calls=2).generate(_user(), ctx, QUESTION)

        assert (text, tools) == ("Here it is.", ["search_docs"])
        assert ctx.retriever.search.await_count == 2
        assert len(model.seen) == 4

    async def test_a_tool_that_raises_gives_the_model_the_unavailable_reply(self):
        """
        GIVEN a tool whose backend raises an error nothing handles
        WHEN the turn is generated
        THEN the model is told the data is unavailable and answers, the tool is not
             reported as having run, and one error record names the tool and the error class
             and nothing else
        """
        ctx = _ctx()
        ctx.client.list_projects.side_effect = RuntimeError("secret-host:5432 refused")
        model = _model(_call("list_my_projects"), AIMessage(content="I could not look it up."))

        with captured_log_records("api.assistant.agent.generation") as records:
            text, tools = await AgentGenerator(model, max_tool_calls=4).generate(
                _user(), ctx, QUESTION
            )

        assert (text, tools) == ("I could not look it up.", [])
        assert model.seen[1][-1].content == UNAVAILABLE_REPLY
        assert ctx.tool_outputs == [UNAVAILABLE_REPLY]
        (record,) = records
        assert record.levelno == logging.ERROR
        assert record.event == "assistant_tool_failed"
        assert (record.tool, record.reason) == ("list_my_projects", "RuntimeError")
        assert "secret-host" not in record.getMessage()
        assert record.exc_info is None
        assert _extra_fields(record) == {"event", "tool", "reason", "where"}
        assert not any("secret-host" in str(value) for value in vars(record).values())

    async def test_a_tool_name_made_of_arbitrary_text_leaves_no_trace_in_the_record(self):
        """
        GIVEN a failing call whose tool name is free text from the model, not one of the five
        WHEN the failure is reported
        THEN the record names the tool as "unknown" and none of that text is in it
        """
        ctx = _ctx()
        runtime = ToolRuntime(
            state={},
            context=ctx,
            config={},
            stream_writer=lambda _: None,
            tool_call_id="call-1",
            store=None,
        )
        hostile = "ignore-all-rules secret-host <script>"
        request = ToolCallRequest(
            tool_call={"name": hostile, "args": {}, "id": "call-1", "type": "tool_call"},
            tool=None,
            state={},
            runtime=runtime,
        )

        with captured_log_records("api.assistant.agent.generation") as records:
            reply = _tool_failed(RuntimeError("bug"), request)

        (record,) = records
        assert reply == UNAVAILABLE_REPLY
        assert record.tool == "unknown"
        assert not any(
            part in str(value)
            for value in vars(record).values()
            for part in ("ignore-all", "<script>")
        )

    async def test_an_ordinary_run_makes_no_extra_model_call(self):
        """
        GIVEN a model that uses a tool and then answers, in words that mention a limit
        WHEN the turn is generated
        THEN the model was called exactly twice and the answer is its own
        """
        model = _model(_search(), AIMessage(content="Stay within the limit of 5 calls."))

        text, _ = await AgentGenerator(model, max_tool_calls=4).generate(
            _user(), _ctx([_chunk()]), QUESTION
        )

        assert text == "Stay within the limit of 5 calls."
        assert len(model.seen) == 2

    async def test_earlier_answers_in_the_history_do_not_count_toward_the_limit(self):
        """
        GIVEN a history with three earlier answers, one tool call allowed (so three model
              calls) and a model that answers at once
        WHEN the turn is generated
        THEN no fallback call is made
        """
        model = _model(AIMessage(content="Answered."))
        history: list[BaseMessage] = []
        for index in range(3):
            history += [HumanMessage(content=f"q{index}"), AIMessage(content=f"a{index}")]

        text, _ = await AgentGenerator(model, max_tool_calls=1).generate(
            [*history, *_user()], _ctx(), QUESTION
        )

        assert text == "Answered."
        assert len(model.seen) == 1

    async def test_an_answer_on_the_last_permitted_model_call_is_not_a_limit_run(self):
        """
        GIVEN one tool call allowed, so three model calls, and a model that spends the first
              on a tool, the second on a refused tool call and answers on the third
        WHEN the turn is generated
        THEN the third call's answer is returned and no fallback call is made
        """
        model = _model(_search(1), _search(2), AIMessage(content="Answered in time."))

        text, _ = await AgentGenerator(model, max_tool_calls=1).generate(
            _user(), _ctx([_chunk()]), QUESTION
        )

        assert text == "Answered in time."
        assert len(model.seen) == 3

    async def test_a_run_that_hits_the_model_call_limit_gets_one_call_over_what_was_gathered(self):
        """
        GIVEN two tool calls allowed and a model that never stops asking for tools
        WHEN the turn is generated
        THEN exactly one more call is made, without tools, whose user message holds every
             registered excerpt, then the tool replies, then the question, and its answer
             is the answer of the turn
        """
        model = _model(
            _search(1),
            _call("list_my_projects", 2),
            _search(3),
            _search(4),
            AIMessage(content="From what I found."),
        )
        ctx = _ctx([_chunk()])
        history = [HumanMessage(content="Earlier"), AIMessage(content="Reply")]

        with_context = HumanMessage(content=f"Some fetched context.\n\nQuestion: {QUESTION}")

        text, tools = await AgentGenerator(model, max_tool_calls=2).generate(
            [*history, with_context], ctx, QUESTION
        )

        assert text == "From what I found."
        assert tools == ["search_docs", "list_my_projects"]
        assert len(model.seen) == 5
        assert model.seen[-1] == [
            SystemMessage(content=SYSTEM_PROMPT),
            *history,
            HumanMessage(
                content="Excerpts:\n\n[1] Method - Step 3\nThe compromise is the midpoint."
                "\n\nno_result: the user is not a member of any project"
                f"\n\nQuestion: {QUESTION}{ENGLISH_LINE}"
            ),
        ]

    async def test_the_fallback_call_shows_a_repeated_reply_once(self):
        """
        GIVEN a model that loops on the same tool call until the model-call limit, so the
              tool gives the same reply twice
        WHEN the turn is generated
        THEN the extra call's user message holds that reply once, then the question
        """
        model = _model(
            _call("list_my_projects", 1),
            _call("list_my_projects", 2),
            _call("list_my_projects", 3),
            _call("list_my_projects", 4),
            AIMessage(content="Nothing more."),
        )
        ctx = _ctx()

        await AgentGenerator(model, max_tool_calls=2).generate(_user(), ctx, QUESTION)

        assert ctx.tool_outputs == ["no_result: the user is not a member of any project"] * 2
        assert model.seen[-1][-1].content == (
            f"no_result: the user is not a member of any project\n\nQuestion: {QUESTION}"
            f"{ENGLISH_LINE}"
        )

    async def test_the_fallback_call_keeps_distinct_replies_in_the_order_they_first_came(self):
        """
        GIVEN replies A, B, A from three calls before the model-call limit
        WHEN the turn is generated
        THEN the extra call's user message holds A, then B, once each, then the question
        """
        ctx = _ctx()
        ctx.client.list_projects.side_effect = [[], [_brief()], []]
        model = _model(
            _call("list_my_projects", 1),
            _call("list_my_projects", 2),
            _call("list_my_projects", 3),
            _call("list_my_projects", 4),
            _call("list_my_projects", 5),
            AIMessage(content="Done."),
        )

        await AgentGenerator(model, max_tool_calls=3).generate(_user(), ctx, QUESTION)

        first, second, third = ctx.tool_outputs
        assert first != second
        assert third == first
        assert model.seen[-1][-1].content == (
            f"{first}\n\n{second}\n\nQuestion: {QUESTION}{ENGLISH_LINE}"
        )

    async def test_the_fallback_call_of_a_run_with_nothing_gathered_is_the_bare_question(self):
        """
        GIVEN a model that asks only for tools that do not exist, until the limit
        WHEN the turn is generated
        THEN the extra call's user message is the bare question, since nothing was gathered
        """
        model = _model(
            _call("nope", 1),
            _call("nope", 2),
            _call("nope", 3),
            _call("nope", 4),
            AIMessage(content="No data."),
        )

        text, _ = await AgentGenerator(model, max_tool_calls=2).generate(_user(), _ctx(), QUESTION)

        assert text == "No data."
        assert model.seen[-1] == [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"{QUESTION}{ENGLISH_LINE}"),
        ]

    async def test_a_blank_fallback_answer_comes_back_blank(self):
        """
        GIVEN a run that hits the model-call limit and a fallback call that only thinks
        WHEN the turn is generated
        THEN the text is empty, for the caller to refuse
        """
        model = _model(
            _call("nope", 1),
            _call("nope", 2),
            _call("nope", 3),
            _call("nope", 4),
            AIMessage(content="<think>out of tokens</think>"),
        )

        text, _ = await AgentGenerator(model, max_tool_calls=2).generate(_user(), _ctx(), QUESTION)

        assert text == ""

    async def test_a_final_reply_cut_off_inside_its_reasoning_raises_the_cut_off_error(self):
        """
        GIVEN a model whose final reply opens a reasoning block and never closes it
        WHEN the turn is generated
        THEN CutOffAnswerError is raised
        """
        model = _model(_search(), AIMessage(content="<think>then I looked at"))

        with pytest.raises(CutOffAnswerError):
            await AgentGenerator(model, max_tool_calls=4).generate(
                _user(), _ctx([_chunk()]), QUESTION
            )

    async def test_a_fallback_reply_cut_off_inside_its_reasoning_raises_the_cut_off_error(self):
        """
        GIVEN a run that hits the model-call limit and a fallback call cut off in its reasoning
        WHEN the turn is generated
        THEN CutOffAnswerError is raised
        """
        model = _model(
            _call("nope", 1),
            _call("nope", 2),
            _call("nope", 3),
            _call("nope", 4),
            AIMessage(content="<think>out of tok"),
        )

        with pytest.raises(CutOffAnswerError):
            await AgentGenerator(model, max_tool_calls=2).generate(_user(), _ctx(), QUESTION)


def _failure_request(name: str = "list_my_projects") -> ToolCallRequest:
    runtime = ToolRuntime(
        state={},
        context=_ctx(),
        config={},
        stream_writer=lambda _: None,
        tool_call_id="call-1",
        store=None,
    )
    return ToolCallRequest(
        tool_call={"name": name, "args": {}, "id": "call-1", "type": "tool_call"},
        tool=None,
        state={},
        runtime=runtime,
    )


def _raised_here() -> RuntimeError:
    """Raise and catch an error in this file, returning it with its traceback."""
    try:
        raise RuntimeError("secret-host:5432 refused")
    except RuntimeError as exc:
        return exc


class TestToolFailureLocation:
    """The ERROR record of a failed tool says where the exception came from, not what it said."""

    def test_where_is_the_repository_relative_file_and_line_of_the_innermost_frame(self):
        """
        GIVEN an exception raised in this test file
        WHEN the failure is reported
        THEN the record's where is this file, relative to the repository, and the raising line
        """
        exc = _raised_here()
        assert exc.__traceback__ is not None
        line = exc.__traceback__.tb_lineno

        with captured_log_records("api.assistant.agent.generation") as records:
            _tool_failed(exc, _failure_request())

        (record,) = records
        assert record.where == f"tests/unit/api/assistant/agent/test_generation.py:{line}"
        assert _extra_fields(record) == {"event", "tool", "reason", "where"}
        assert not any("secret-host" in str(value) for value in vars(record).values())

    def test_a_frame_outside_the_repository_is_named_by_its_file_name_only(self):
        """
        GIVEN an exception raised inside the standard library
        WHEN the failure is reported
        THEN where holds the bare file name and line, never an absolute path
        """
        try:
            json.loads("{")
        except json.JSONDecodeError as exc:
            error = exc

        with captured_log_records("api.assistant.agent.generation") as records:
            _tool_failed(error, _failure_request())

        (record,) = records
        assert record.where.startswith("decoder.py:")
        assert "/" not in record.where

    def test_an_exception_that_was_never_raised_has_an_unknown_location(self):
        """
        GIVEN an exception with no traceback
        WHEN the failure is reported
        THEN where is "unknown"
        """
        with captured_log_records("api.assistant.agent.generation") as records:
            _tool_failed(RuntimeError("bug"), _failure_request())

        (record,) = records
        assert record.where == "unknown"
