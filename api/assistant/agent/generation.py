"""The ways an answer is generated from the messages of a turn.

An :class:`AnswerGenerator` takes the conversation the chat service assembled and the
turn's context, and returns the answer text, the names of the tools that ran and the
tokens the model used (:class:`~api.schemas.assistant.TurnUsage`). There are two:
:class:`DirectGenerator` makes one model call with no tools, and :class:`AgentGenerator`
lets the model call the assistant's tools in a bounded loop. Both send :data:`~api.assistant.agent.prompt.SYSTEM_PROMPT` unchanged.
"""

import logging
from collections.abc import AsyncGenerator, Sequence
from contextlib import aclosing
from dataclasses import dataclass
from pathlib import Path
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
    AIMessageChunk,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from api.assistant.agent.context import AssistantContext
from api.assistant.agent.prompt import SYSTEM_PROMPT, render_context_block
from api.assistant.agent.tools import ASSISTANT_TOOLS, UNAVAILABLE_REPLY
from api.assistant.rag.models import THINK_OPEN, has_unclosed_think_block, strip_think_block
from api.assistant.rag.retrieval import question_language
from api.schemas.assistant import TurnUsage

logger = logging.getLogger(__name__)

# The tool-call limit refuses the call that would exceed it and tells the model so, so a
# model that stays within the limit needs one model call per tool call, one to make the
# refused call and one to read the refusal and write its answer.
_MODEL_CALL_SLACK = 2

# The repository's root, for showing where a failure came from without an absolute path.
_REPO_ROOT = Path(__file__).resolve().parents[3]

_TOOL_NAMES = frozenset(tool.name for tool in ASSISTANT_TOOLS)

# The last line of the user message when the question's language is known.
_ANSWER_LANGUAGE_LINE = {"cs": "Answer in Czech.", "en": "Answer in English."}


class CutOffAnswerError(Exception):
    """Raised when a model's reply ends inside its reasoning block, so it holds no answer.

    The chat service turns it into the same failure as a blank answer, and gives it its own
    reason in the log.
    """


@dataclass(frozen=True)
class Generated:
    """What a generator produced for one turn: the text, the tools that ran, the usage."""

    text: str
    tools_used: list[str]
    usage: TurnUsage


class AnswerGenerator(Protocol):
    """Turns the messages of one turn into an answer."""

    async def generate(
        self, messages: list[AnyMessage], ctx: AssistantContext, question: str
    ) -> tuple[str, list[str], TurnUsage]:
        """Generate the answer of one turn.

        :param messages: The conversation: the kept history, then the user message of
            this turn. The system prompt is the generator's own to add.
        :param ctx: The turn's context.
        :param question: The user's own message, as asked, without any context around it.
        :return: The answer text, the names of the tools that ran, each once, in the order
            they first ran, and the usage of the model's replies in the turn.
        """
        ...

    def stream(
        self, messages: list[AnyMessage], ctx: AssistantContext, question: str
    ) -> AsyncGenerator[str | Generated]:
        """Generate the answer of one turn, yielding its text as it arrives.

        :param messages: The conversation: the kept history, then the user message of
            this turn. The system prompt is the generator's own to add.
        :param ctx: The turn's context.
        :param question: The user's own message, as asked, without any context around it.
        :return: Pieces of answer text, then one :class:`Generated` as the last item. The
            pieces join to the text of the :class:`Generated`.
        """
        ...


def user_message(parts: Sequence[str], question: str) -> str:
    """Build the user message of a turn: the context parts, the question, the language line.

    The context is English, and a model given English context sometimes answers a Czech
    question in English. The code states the answer language itself, here and not in the
    system prompt: a last line, ``Answer in Czech.`` or
    ``Answer in English.``, when :func:`~api.assistant.rag.retrieval.question_language`
    knows the question's language, and no line for any other language. The line is part of
    what the model is sent and nothing else: the grounding checks read the question, not
    this message.

    :param parts: The context to show the model, one string per block.
    :param question: The user's own message.
    :return: The parts and ``Question: <question>`` separated by blank lines, or the bare
        question when there are no parts, then the language line after a blank line.
    """
    message = "\n\n".join([*parts, f"Question: {question}"]) if parts else question
    language = question_language(question)
    if language is None:
        return message
    return f"{message}\n\n{_ANSWER_LANGUAGE_LINE[language]}"


def answer_text(message: BaseMessage) -> str:
    """Read the answer out of a model reply.

    A reply given as a list of content blocks is joined from its text parts, and the
    reasoning block a model may put in front of its answer is removed. A reply that was
    cut off inside its reasoning, so that a block opens and never closes, has no answer:
    what is left of it is the model's half-written thoughts, and it is returned as empty.
    ``strip_think_block`` is shared with the query transforms and keeps such a reply
    as it is, which is why the check is here. The generators tell that case from a blank
    reply with :func:`~api.assistant.rag.models.has_unclosed_think_block`.

    :param message: The model's reply.
    :return: The answer, stripped; empty when the reply held nothing else, or ended
        inside a reasoning block.
    """
    reply = message.text
    return "" if has_unclosed_think_block(reply) else strip_think_block(reply)


def _answer_of(message: BaseMessage) -> str:
    """Read the answer out of a model reply, refusing one that was cut off.

    :param message: The model's reply.
    :return: The answer, empty when the reply was only reasoning that closed.
    :raises CutOffAnswerError: If the reply ends inside a reasoning block.
    """
    if has_unclosed_think_block(message.text):
        raise CutOffAnswerError
    return answer_text(message)


def _usage_of(replies: Sequence[BaseMessage]) -> TurnUsage:
    """Sum the token usage the model reported over its replies of one turn.

    A reply that reports no usage adds nothing to the sums and makes the result incomplete,
    but is still one call.

    :param replies: The messages the model wrote this turn; anything else in the sequence
        is skipped.
    :return: The summed usage.
    :raises ValueError: If there is no model reply in the sequence, which a generator that
        got an answer never has.
    """
    messages = [message for message in replies if isinstance(message, AIMessage)]
    if not messages:
        raise ValueError("a turn's usage needs at least one model reply")
    reported = [message.usage_metadata for message in messages if message.usage_metadata]
    return TurnUsage(
        input_tokens=sum(usage["input_tokens"] for usage in reported),
        output_tokens=sum(usage["output_tokens"] for usage in reported),
        total_tokens=sum(usage["total_tokens"] for usage in reported),
        llm_calls=len(messages),
        complete=len(reported) == len(messages),
    )


def _visible(buffer: str) -> str:
    """Say which part of a partial reply may be shown.

    The reasoning block is withheld, including while it is still open, and so is a
    trailing fragment that could be the start of its opening tag, since the tag may
    arrive split across chunks.

    :param buffer: The reply so far.
    :return: The answer text so far, never ending in a prefix of ``<think>``.
    """
    if has_unclosed_think_block(buffer):
        return ""
    shown = strip_think_block(buffer)
    for length in range(min(len(THINK_OPEN) - 1, len(shown)), 0, -1):
        if THINK_OPEN.startswith(shown[-length:]):
            return shown[:-length].rstrip()
    return shown


class DirectGenerator(AnswerGenerator):
    """One model call and no tools: the way the workflow mode answers.

    :param chat_model: The model that writes the answer.
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        """Keep the model."""
        self._model = chat_model

    async def generate(
        self, messages: list[AnyMessage], ctx: AssistantContext, question: str
    ) -> tuple[str, list[str], TurnUsage]:
        """Answer with a single call over the system prompt and the messages.

        :param messages: The conversation, ending with this turn's user message.
        :param ctx: Unused: no tool runs, and nothing is fetched here.
        :param question: Unused: the user message already carries it.
        :return: The answer text, an empty list since no tool ran, and the usage of the reply.
        :raises CutOffAnswerError: If the reply ends inside a reasoning block.
        """
        response = await self._model.ainvoke([SystemMessage(content=SYSTEM_PROMPT), *messages])
        return _answer_of(response), [], _usage_of([response])

    async def stream(
        self, messages: list[AnyMessage], ctx: AssistantContext, question: str
    ) -> AsyncGenerator[str | Generated]:
        """Answer with a single streamed call, yielding the text as it arrives.

        The reply is accumulated as it streams, and only the part outside any reasoning
        block is yielded. The finished reply is read the same way :meth:`generate` reads
        it, and what that adds to the pieces already yielded (a withheld ``<`` that was
        not a tag, the final strip) is yielded last, so the pieces join to the text of the
        final item, which is what the non-streamed call would have returned.

        :param messages: The conversation, ending with this turn's user message.
        :param ctx: Unused: no tool runs, and nothing is fetched here.
        :param question: Unused: the user message already carries it.
        :return: Pieces of answer text, then one :class:`Generated`.
        :raises CutOffAnswerError: If the reply ends inside a reasoning block.
        """
        full = AIMessageChunk(content="")
        emitted = 0
        # Closing this generator early closes the model's stream at once, not whenever the
        # garbage collector gets to it. ``astream`` is typed as an iterator, but every chat
        # model's is an async generator, which has ``aclose``.
        stream = cast(
            "AsyncGenerator[AIMessageChunk]",
            self._model.astream([SystemMessage(content=SYSTEM_PROMPT), *messages]),
        )
        async with aclosing(stream) as chunks:
            async for chunk in chunks:
                full += chunk
                visible = _visible(full.text)
                if len(visible) > emitted:
                    yield visible[emitted:]
                    emitted = len(visible)
        reply = AIMessage(content=full.text, usage_metadata=full.usage_metadata)
        final = _answer_of(reply)
        if len(final) > emitted:
            yield final[emitted:]
        yield Generated(final, [], _usage_of([reply]))


def raised_at(exc: BaseException) -> str:
    """Say where an exception was raised, without its message or a traceback.

    :param exc: The exception.
    :return: ``file:line`` of the innermost frame of its traceback. A file under the
        repository is written relative to it, which includes a library installed in the
        repository's own ``.venv`` (``.venv/lib/.../file.py``); a file outside the
        repository, the standard library for one, is written as its bare name, so that no
        absolute path is written. ``unknown`` when the exception carries no traceback.
    """
    trace = exc.__traceback__
    if trace is None:
        return "unknown"
    while trace.tb_next is not None:
        trace = trace.tb_next
    path = Path(trace.tb_frame.f_code.co_filename).resolve()
    shown = path.relative_to(_REPO_ROOT) if path.is_relative_to(_REPO_ROOT) else Path(path.name)
    return f"{shown}:{trace.tb_lineno}"


def _tool_failed(exc: Exception, request: ToolCallRequest) -> str:
    """Turn an exception nobody handled inside a tool into the tools' unavailable reply.

    The tools catch the outages themselves, so what arrives here is a bug, and it is
    logged at ERROR so error tracking sees it whatever the mode. The record carries the
    tool, the exception's class name and where it was raised (see :func:`raised_at`):
    never the message, which can name a host or a path, and never a traceback. The tool
    name comes from the model's call, so it is written only when it is one of the
    assistant's tools, and as ``unknown`` otherwise. In the installed library a call to a
    tool that does not exist is answered by the tool node itself and never reaches this
    handler; the guard is there in case that changes.

    :param exc: What the tool raised.
    :param request: The call that failed.
    :return: The ``unavailable:`` line, which the model reads as the tool's reply.
    """
    called = request.tool_call["name"]
    name = called if called in _TOOL_NAMES else "unknown"
    logger.error(
        "assistant tool %s failed",
        name,
        extra={
            "event": "assistant_tool_failed",
            "tool": name,
            "reason": type(exc).__name__,
            "where": raised_at(exc),
        },
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


class AgentGenerator(AnswerGenerator):
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
    ) -> tuple[str, list[str], TurnUsage]:
        """Run the loop, and fall back to one direct call when it ends on its limit.

        The model-call limit ends a run by adding a message of its own that says the
        limit was reached, and it leaves nothing else in the result that tells such a
        run from one that ended with an answer. What does tell them apart is the count of
        model replies the run added: a run that ended by itself holds at most
        ``run_limit`` of them, and a run the limit ended holds that many and the limit's
        own message, which no model wrote and so is left out of the usage.

        :param messages: The conversation, ending with this turn's user message.
        :param ctx: The turn's context, passed to the tools.
        :param question: The user's own message, for the fallback call.
        :return: The answer text, the names of the tools that ran, and the usage of the
            loop's replies and, when it ran, of the fallback call.
        """
        state: InputAgentState = {"messages": [*messages]}
        result = await self._agent.ainvoke(state, context=ctx)
        produced: list[BaseMessage] = result["messages"][len(messages) :]
        replies = sum(isinstance(message, AIMessage) for message in produced)
        if replies > self._model_call_limit:
            text, fallback = await self._answer_from_gathered(messages, ctx, question)
            return text, _tools_that_ran(produced), _usage_of([*produced[:-1], fallback])
        return _answer_of(produced[-1]), _tools_that_ran(produced), _usage_of(produced)

    async def stream(
        self, messages: list[AnyMessage], ctx: AssistantContext, question: str
    ) -> AsyncGenerator[str | Generated]:
        """Run the loop and yield its result in one piece: the agent mode does not stream.

        :param messages: The conversation, ending with this turn's user message.
        :param ctx: The turn's context, passed to the tools.
        :param question: The user's own message, for the fallback call.
        :return: One :class:`Generated`, after the whole run.
        """
        text, tools_used, usage = await self.generate(messages, ctx, question)
        yield Generated(text, tools_used, usage)

    async def _answer_from_gathered(
        self, messages: list[AnyMessage], ctx: AssistantContext, question: str
    ) -> tuple[str, AIMessage]:
        """Answer with one call, and no tools, over everything the run gathered.

        The user message is built as the workflow mode builds its own: the excerpts of
        every source in the registry, then the replies the tools gave, then the question.
        A run that reached the model-call limit was usually looping, and a loop repeats
        the same call, so a reply that appears more than once is shown once, in the order
        it first appeared. The size is bounded by ``max_tool_calls``, but not to the
        window: at the field limits, four replies can exceed the answer model's window,
        and a call that large is rejected by the model server, so it ends as the
        unavailable failure (the 503).

        :param messages: The conversation the run started from.
        :param ctx: The turn's context, holding the sources and the tool replies.
        :param question: The user's own message.
        :return: The answer text and the model's reply it was read from.
        :raises CutOffAnswerError: If the reply ends inside a reasoning block.
        """
        excerpts = render_context_block(ctx.sources.numbered(), None)
        parts = [*([excerpts] if excerpts else []), *dict.fromkeys(ctx.tool_outputs)]
        content = user_message(parts, question)
        response = await self._model.ainvoke(
            [SystemMessage(content=SYSTEM_PROMPT), *messages[:-1], HumanMessage(content=content)]
        )
        return _answer_of(response), response
