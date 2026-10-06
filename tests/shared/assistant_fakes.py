"""Shared LangChain test doubles for the assistant's unit and integration tests.

GenericFakeChatModel (langchain_core.language_models.fake_chat_models) plays back
scripted messages but its reference page documents no ``bind_tools`` override,
unlike every real provider integration. ``create_agent`` must bind tools to the
model to format them for the API and to parse ``tool_calls`` back out of a
response, so a model with no working ``bind_tools`` cannot drive its tool-calling
loop. The class here implements the minimum ``BaseChatModel`` needs for that loop
to run against a scripted sequence, and records the messages of every call in
``seen``, so a test can assert what the model was shown.
"""

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from typing import Any

import httpx
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolMessage
from langchain_core.messages.ai import UsageMetadata
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import Field, PrivateAttr

from api.assistant.rag.retrieval import RetrievedChunk

# What a scripted reply reports as its token usage when the test gave it none.
DEFAULT_USAGE: UsageMetadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}


class ScriptedToolCallingModel(BaseChatModel):
    """A chat model that plays back a fixed queue of ``AIMessage`` responses.

    ``bind_tools`` returns the instance unchanged: every scripted response already
    carries whatever ``tool_calls`` the test wants, so there is nothing to format.

    A response with no ``usage_metadata`` is returned with :data:`DEFAULT_USAGE`, as a real
    model server reports usage on every reply; a test that sets its own metadata keeps it,
    and one that needs a reply without any sets ``report_usage`` to false.

    A streamed call plays the next response back in pieces (see :meth:`_astream`).

    :ivar responses: The messages to return, one per call, in order.
    :ivar report_usage: Whether a response with no ``usage_metadata`` gets the default.
    :ivar stream_chunks: The pieces a streamed call yields, when the test sets them; else
        the reply is split after every space.
    :ivar fail_after_chunks: When set, a streamed call raises a connection error after
        that many pieces.
    :ivar stream_delay_s: Seconds a streamed call waits before each piece.
    :ivar seen: The messages each call was given, one list per call, in call order.
    """

    responses: list[AIMessage]
    report_usage: bool = True
    stream_chunks: list[str] | None = None
    fail_after_chunks: int | None = None
    stream_delay_s: float = 0.0
    seen: list[list[BaseMessage]] = Field(default_factory=list)
    _call_count: int = PrivateAttr(default=0)

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        """Return this model unchanged; scripted responses need no tool formatting."""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Return the next scripted response, in call order.

        :param messages: The conversation so far; recorded in ``seen``.
        :param stop: Unused.
        :param run_manager: Unused.
        :return: The next queued response, wrapped as a :class:`ChatResult`.
        """
        self.seen.append(list(messages))
        response = self.responses[self._call_count]
        if self.report_usage and response.usage_metadata is None:
            response = response.model_copy(update={"usage_metadata": DEFAULT_USAGE})
        self._call_count += 1
        return ChatResult(generations=[ChatGeneration(message=response)])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """Play back the next scripted response in pieces, the usage on the last one.

        The pieces are ``stream_chunks`` when the test set them, else the reply split
        after every space. ``fail_after_chunks`` raises a connection error after that many
        pieces, as a model server that dies mid-answer does.

        :param messages: The conversation so far; recorded in ``seen``.
        :param stop: Unused.
        :param run_manager: Unused.
        :return: The pieces as chunks.
        :raises httpx.ConnectError: After ``fail_after_chunks`` pieces.
        """
        self.seen.append(list(messages))
        response = self.responses[self._call_count]
        self._call_count += 1
        pieces = (
            self.stream_chunks
            if self.stream_chunks is not None
            else _split_keeping_spaces(response.text)
        )
        usage = response.usage_metadata or (DEFAULT_USAGE if self.report_usage else None)
        chunks = pieces or [""]
        for index, piece in enumerate(chunks):
            if self.stream_delay_s:
                await asyncio.sleep(self.stream_delay_s)
            if self.fail_after_chunks is not None and index >= self.fail_after_chunks:
                raise httpx.ConnectError("the model server went away")
            last = index == len(chunks) - 1
            chunk = AIMessageChunk(content=piece, usage_metadata=usage if last else None)
            yield ChatGenerationChunk(message=chunk)

    @property
    def _llm_type(self) -> str:
        """Return the model type name LangChain's tracing uses."""
        return "scripted-tool-calling-model"


def _split_keeping_spaces(text: str) -> list[str]:
    """Split a reply after every space, so that the pieces join back to it exactly."""
    pieces = [piece + " " for piece in text.split(" ")]
    pieces[-1] = pieces[-1][:-1]
    return [piece for piece in pieces if piece]


class ToolEchoingModel(BaseChatModel):
    """A chat model that makes one scripted tool call, then answers with the tool's reply.

    Whatever the tool said is what the "model" answers, so a test can read the tool's
    output straight off the response and see exactly what the tool gave the model. Every
    call's messages are recorded in ``seen``, as in :class:`ScriptedToolCallingModel`.

    :ivar first_call: The response returned while no tool has replied yet.
    :ivar seen: The messages each call was given, one list per call, in call order.
    """

    first_call: AIMessage
    seen: list[list[BaseMessage]] = Field(default_factory=list)

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        """Return this model unchanged; the scripted call needs no tool formatting."""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Return the scripted call first, then the text of the latest tool reply.

        :param messages: The conversation so far; recorded in ``seen``.
        :param stop: Unused.
        :param run_manager: Unused.
        :return: The scripted call while no tool has replied, else an answer that is the
            latest tool reply's text.
        """
        self.seen.append(list(messages))
        replies = [message for message in messages if isinstance(message, ToolMessage)]
        response = AIMessage(content=replies[-1].text) if replies else self.first_call
        return ChatResult(generations=[ChatGeneration(message=response)])

    @property
    def _llm_type(self) -> str:
        """Return the model type name LangChain's tracing uses."""
        return "tool-echoing-model"


class StaticDocsRetriever:
    """A documentation retriever that returns the same chunks for every query.

    Integration tests never reach a real vector database or embedding server: the shared
    test application installs an empty one in place of the real retriever, and a test that
    needs particular passages installs its own with them.

    :param chunks: What every search returns.
    :ivar queries: Every query searched for, in order.
    """

    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks
        self.queries: list[str] = []

    async def search(self, query: str) -> list[RetrievedChunk]:
        """Record the query and return the fixed chunks.

        :param query: The search query, recorded for assertions.
        :return: A copy of the fixed chunks.
        """
        self.queries.append(query)
        return list(self._chunks)
