"""Tests for the scripted chat models the assistant's tests drive an agent with."""

import pytest
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from api.assistant.rag.retrieval import RetrievedChunk
from tests.shared.assistant_fakes import (
    DEFAULT_USAGE,
    ScriptedToolCallingModel,
    StaticDocsRetriever,
    ToolEchoingModel,
)


@tool
def _lookup(topic: str) -> str:
    """Look a topic up."""
    return f"about {topic}: 42.00"


def _call(name: str = "_lookup", topic: str = "the mean") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": {"topic": topic}, "id": "call-1", "type": "tool_call"}],
    )


@pytest.mark.asyncio
class TestScriptedToolCallingModel:
    """The model plays back its script and records what it was shown."""

    async def test_plays_the_script_through_a_tool_call_and_back(self):
        """
        GIVEN a script of one tool call and one final answer
        WHEN an agent with that tool runs on it
        THEN the tool runs between the two responses and the final answer comes back
        """
        model = ScriptedToolCallingModel(responses=[_call(), AIMessage(content="Done.")])
        agent = create_agent(model, [_lookup])

        result = await agent.ainvoke({"messages": [HumanMessage(content="Explain")]})

        assert result["messages"][-1].content == "Done."
        tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert [m.content for m in tool_messages] == ["about the mean: 42.00"]

    async def test_reports_the_default_usage_unless_a_reply_has_its_own_or_it_is_off(self):
        """
        GIVEN replies with no usage, with its own usage, and a model told to report none
        WHEN each is called
        THEN the first gets the default, the second keeps its own, and the third has none
        """
        own = {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}
        model = ScriptedToolCallingModel(
            responses=[AIMessage(content="a"), AIMessage(content="b", usage_metadata=own)]
        )
        silent = ScriptedToolCallingModel(responses=[AIMessage(content="c")], report_usage=False)

        first = await model.ainvoke("x")
        second = await model.ainvoke("x")
        third = await silent.ainvoke("x")

        assert first.usage_metadata == DEFAULT_USAGE
        assert second.usage_metadata == own
        assert third.usage_metadata is None

    async def test_records_the_messages_of_every_call(self):
        """
        GIVEN a model that has been called twice by an agent
        WHEN its seen list is read
        THEN it holds one entry per call, and the second one includes the tool's reply
        """
        model = ScriptedToolCallingModel(responses=[_call(), AIMessage(content="Done.")])
        agent = create_agent(model, [_lookup])

        await agent.ainvoke({"messages": [HumanMessage(content="Explain")]})

        assert len(model.seen) == 2
        assert [m.content for m in model.seen[0]] == ["Explain"]
        assert any(
            isinstance(m, ToolMessage) and m.content == "about the mean: 42.00"
            for m in model.seen[1]
        )


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        text="A caption.\n\nThe compromise is the midpoint.",
        title="Method",
        section="Step 3",
        url=None,
        layer="public",
        score=0.9,
        chunk_text="The compromise is the midpoint.",
    )


@pytest.mark.asyncio
class TestStaticDocsRetriever:
    """The retriever returns its fixed chunks and records what was asked."""

    async def test_returns_the_same_chunks_for_any_query_and_records_each_query(self):
        """
        GIVEN a retriever holding one chunk
        WHEN two different queries are searched
        THEN each returns that chunk, and both queries are recorded in order
        """
        # GIVEN
        retriever = StaticDocsRetriever([_chunk()])

        # WHEN
        first = await retriever.search("what is the compromise")
        second = await retriever.search("something else")

        # THEN
        assert first == second == [_chunk()]
        assert retriever.queries == ["what is the compromise", "something else"]

    async def test_a_caller_changing_the_result_does_not_change_the_next_one(self):
        """
        GIVEN a result list a caller has emptied
        WHEN the same retriever is searched again
        THEN it still returns the chunk
        """
        # GIVEN
        retriever = StaticDocsRetriever([_chunk()])
        (await retriever.search("q")).clear()

        # WHEN
        again = await retriever.search("q")

        # THEN
        assert again == [_chunk()]


@pytest.mark.asyncio
class TestToolEchoingModel:
    """The model makes its one scripted call, then answers with what the tool said."""

    async def test_answers_with_the_reply_of_the_tool_it_called(self):
        """
        GIVEN a model scripted to call a tool once
        WHEN an agent with that tool runs on it
        THEN the tool runs and the final answer is the tool's own reply, word for word
        """
        # GIVEN
        model = ToolEchoingModel(first_call=_call())
        agent = create_agent(model, [_lookup])

        # WHEN
        result = await agent.ainvoke({"messages": [HumanMessage(content="Explain")]})

        # THEN
        assert result["messages"][-1].content == "about the mean: 42.00"

    async def test_answers_with_the_error_text_of_a_call_the_agent_refused(self):
        """
        GIVEN a model scripted to call a tool that does not exist
        WHEN an agent runs on it
        THEN the final answer is what the agent said back about that call, not an empty reply
        """
        # GIVEN
        model = ToolEchoingModel(first_call=_call(name="no_such_tool"))
        agent = create_agent(model, [_lookup])

        # WHEN
        result = await agent.ainvoke({"messages": [HumanMessage(content="Explain")]})

        # THEN
        assert "no_such_tool" in result["messages"][-1].content

    async def test_records_the_messages_of_every_call(self):
        """
        GIVEN a model that has been called twice by an agent
        WHEN its seen list is read
        THEN it holds one entry per call, and the second one includes the tool's reply
        """
        # GIVEN
        model = ToolEchoingModel(first_call=_call())
        agent = create_agent(model, [_lookup])

        # WHEN
        await agent.ainvoke({"messages": [HumanMessage(content="Explain")]})

        # THEN
        assert len(model.seen) == 2
        assert [m.content for m in model.seen[0]] == ["Explain"]
        assert any(
            isinstance(m, ToolMessage) and m.content == "about the mean: 42.00"
            for m in model.seen[1]
        )
