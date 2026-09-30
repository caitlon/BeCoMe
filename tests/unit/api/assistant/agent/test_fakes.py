"""Tests for the scripted chat models the assistant's tests drive an agent with."""

import pytest
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from tests.shared.assistant_fakes import ScriptedToolCallingModel


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
