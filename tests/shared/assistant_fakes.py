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

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import Field, PrivateAttr

from api.assistant.rag.retrieval import RetrievedChunk


class ScriptedToolCallingModel(BaseChatModel):
    """A chat model that plays back a fixed queue of ``AIMessage`` responses.

    ``bind_tools`` returns the instance unchanged: every scripted response already
    carries whatever ``tool_calls`` the test wants, so there is nothing to format.

    :ivar responses: The messages to return, one per call, in order.
    :ivar seen: The messages each call was given, one list per call, in call order.
    """

    responses: list[AIMessage]
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
        self._call_count += 1
        return ChatResult(generations=[ChatGeneration(message=response)])

    @property
    def _llm_type(self) -> str:
        """Return the model type name LangChain's tracing uses."""
        return "scripted-tool-calling-model"


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
