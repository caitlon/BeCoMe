"""The ways an answer is generated from the messages of a turn.

An :class:`AnswerGenerator` takes the conversation the chat service assembled and the
turn's context, and returns the answer text with the names of the tools that ran. There
are two: :class:`DirectGenerator` makes one model call with no tools, and
:class:`AgentGenerator` lets the model call the assistant's tools in a bounded loop.
Both send :data:`~api.assistant.agent.prompt.SYSTEM_PROMPT` unchanged.
"""

import logging
from collections.abc import Sequence
from typing import Any, Protocol, cast

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    InputAgentState,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    ToolCallRequest,
    ToolErrorMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from api.assistant.agent.context import AssistantContext
from api.assistant.agent.prompt import SYSTEM_PROMPT, render_context_block
from api.assistant.agent.tools import ASSISTANT_TOOLS, UNAVAILABLE_REPLY
from api.assistant.rag.models import strip_think_block

logger = logging.getLogger(__name__)

# The tool-call limit refuses the call that would exceed it and tells the model so, so a
# model that stays within the limit needs one model call per tool call, one to make the
# refused call and one to read the refusal and write its answer.
_MODEL_CALL_SLACK = 2

_TOOL_NAMES = frozenset(tool.name for tool in ASSISTANT_TOOLS)


class AnswerGenerator(Protocol):
    """Turns the messages of one turn into an answer."""

    async def generate(
        self, messages: list[AnyMessage], ctx: AssistantContext, question: str
    ) -> tuple[str, list[str]]:
        """Generate the answer of one turn.

        :param messages: The conversation: the kept history, then the user message of
            this turn. The system prompt is the generator's own to add.
        :param ctx: The turn's context.
        :param question: The user's own message, as asked, without any context around it.
        :return: The answer text, and the names of the tools that ran, each once, in the
            order they first ran.
        """
        ...


def user_message(parts: Sequence[str], question: str) -> str:
    """Build the user message of a turn: the context parts, then the question.

    :param parts: The context to show the model, one string per block.
    :param question: The user's own message.
    :return: The parts and ``Question: <question>`` separated by blank lines, or the bare
        question when there are no parts.
    """
    if not parts:
        return question
    return "\n\n".join([*parts, f"Question: {question}"])


def answer_text(message: BaseMessage) -> str:
    """Read the answer out of a model reply.

    A reply given as a list of content blocks is joined from its text parts, and the
    reasoning block a model may put in front of its answer is removed.

    :param message: The model's reply.
    :return: The answer, stripped; empty when the reply held nothing else.
    """
    return strip_think_block(message.text)


class DirectGenerator:
    """One model call and no tools: the way the workflow mode answers.

    :param chat_model: The model that writes the answer.
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        """Keep the model."""
        self._model = chat_model

    async def generate(
        self, messages: list[AnyMessage], ctx: AssistantContext, question: str
    ) -> tuple[str, list[str]]:
        """Answer with a single call over the system prompt and the messages.

        :param messages: The conversation, ending with this turn's user message.
        :param ctx: Unused: no tool runs, and nothing is fetched here.
        :param question: Unused: the user message already carries it.
        :return: The answer text and an empty list, since no tool ran.
        """
        response = await self._model.ainvoke([SystemMessage(content=SYSTEM_PROMPT), *messages])
        return answer_text(response), []


def _tool_failed(exc: Exception, request: ToolCallRequest) -> str:
    """Turn an exception nobody handled inside a tool into the tools' unavailable reply.

    The tools catch the outages themselves, so what arrives here is a bug, and it is
    logged at ERROR so error tracking sees it whatever the mode. The record carries the
    tool and the exception's class name only: never the message, which can name a host
    or a path, and never a traceback. The tool name comes from the model's call, so it
    is written only when it is one of the assistant's tools, and as ``unknown`` otherwise.

    :param exc: What the tool raised.
    :param request: The call that failed.
    :return: The ``unavailable:`` line, which the model reads as the tool's reply.
    """
    called = request.tool_call["name"]
    name = called if called in _TOOL_NAMES else "unknown"
    logger.error(
        "assistant tool %s failed",
        name,
        extra={"event": "assistant_tool_failed", "tool": name, "reason": type(exc).__name__},
    )
    ctx = cast(AssistantContext, request.runtime.context)
    ctx.tool_outputs.append(UNAVAILABLE_REPLY)
    return UNAVAILABLE_REPLY


def _tools_that_ran(produced: Sequence[BaseMessage]) -> list[str]:
    """Name the tools that ran during an agent run.

    A call to a tool that does not exist, a call with invalid arguments, a call the
    tool-call limit refused and a call that raised all come back as error messages, and
    none of them counts.

    :param produced: The messages the run added to the conversation.
    :return: The names of the assistant's tools with a successful reply, each once, in
        the order they first ran.
    """
    names = (
        message.name
        for message in produced
        if isinstance(message, ToolMessage)
        and message.status == "success"
        and message.name in _TOOL_NAMES
    )
    return list(dict.fromkeys(name for name in names if name is not None))


class AgentGenerator:
    """A tool-calling loop over the assistant's five tools: agent and hybrid modes.

    The agent is built once, here, because the system prompt does not vary by turn; each
    turn reaches the tools through the context it is invoked with. The loop is bounded
    by ``max_tool_calls`` tool calls and by that many model calls plus
    :data:`_MODEL_CALL_SLACK`. A tool that raises does not end the turn: the model is
    told the data is unavailable. A run that reaches the model-call limit without an
    answer gets one more model call, without tools, over what was already gathered.

    :param chat_model: The model that drives the loop and writes the answer.
    :param max_tool_calls: The most tool calls one turn may make.
    """

    def __init__(self, chat_model: BaseChatModel, max_tool_calls: int) -> None:
        """Build the agent."""
        self._model = chat_model
        self._model_call_limit = max_tool_calls + _MODEL_CALL_SLACK
        middleware: list[AgentMiddleware[Any, Any, Any]] = [
            ModelCallLimitMiddleware(run_limit=self._model_call_limit, exit_behavior="end"),
            ToolCallLimitMiddleware(run_limit=max_tool_calls),
            ToolErrorMiddleware(_tool_failed),
        ]
        self._agent = create_agent(
            model=chat_model,
            tools=ASSISTANT_TOOLS,
            system_prompt=SYSTEM_PROMPT,
            context_schema=AssistantContext,
            middleware=middleware,
        )

    async def generate(
        self, messages: list[AnyMessage], ctx: AssistantContext, question: str
    ) -> tuple[str, list[str]]:
        """Run the loop, and fall back to one direct call when it ends on its limit.

        The model-call limit ends a run by adding a message of its own that says the
        limit was reached, and it leaves nothing else in the result that tells such a
        run from one that ended with an answer. What does tell them apart is the count of
        model replies the run added: a run that ended by itself holds at most
        ``run_limit`` of them, and a run the limit ended holds that many and the limit's
        own message.

        :param messages: The conversation, ending with this turn's user message.
        :param ctx: The turn's context, passed to the tools.
        :param question: The user's own message, for the fallback call.
        :return: The answer text, and the names of the tools that ran.
        """
        state: InputAgentState = {"messages": [*messages]}
        result = await self._agent.ainvoke(state, context=ctx)
        produced: list[BaseMessage] = result["messages"][len(messages) :]
        replies = sum(isinstance(message, AIMessage) for message in produced)
        if replies > self._model_call_limit:
            text = await self._answer_from_gathered(messages, ctx, question)
        else:
            text = answer_text(produced[-1])
        return text, _tools_that_ran(produced)

    async def _answer_from_gathered(
        self, messages: list[AnyMessage], ctx: AssistantContext, question: str
    ) -> str:
        """Answer with one call, and no tools, over everything the run gathered.

        The user message is built as the workflow mode builds its own: the excerpts of
        every source in the registry, then the replies the tools gave, then the question.
        Its size is bounded by ``max_tool_calls``: the turn made at most that many tool
        calls, and the replies are capped in size, so the default four fit the answer
        model's 16384-token window together with the history.

        :param messages: The conversation the run started from.
        :param ctx: The turn's context, holding the sources and the tool replies.
        :param question: The user's own message.
        :return: The answer text.
        """
        excerpts = render_context_block(ctx.sources.numbered(), None)
        parts = [*([excerpts] if excerpts else []), *ctx.tool_outputs]
        content = user_message(parts, question)
        response = await self._model.ainvoke(
            [SystemMessage(content=SYSTEM_PROMPT), *messages[:-1], HumanMessage(content=content)]
        )
        return answer_text(response)
