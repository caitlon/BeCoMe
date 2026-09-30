"""Shared LangChain test doubles for the assistant's unit and integration tests.

GenericFakeChatModel (langchain_core.language_models.fake_chat_models) plays back
scripted messages but its reference page documents no ``bind_tools`` override,
unlike every real provider integration (ChatOpenAI, ChatAnthropic, ...).
``create_agent`` must bind tools to the model to format them for the API and to
parse ``tool_calls`` back out of a response, so a model with no working
``bind_tools`` cannot drive its tool-calling loop. These two classes implement the
minimum ``BaseChatModel`` needs for that loop to run against a scripted sequence.
Each records the messages of every call in ``seen``, so a test can assert what the
model was shown.
"""

from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from pydantic import Field, PrivateAttr


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

    def bind_tools(self, tools: Sequence[BaseTool], **kwargs: Any) -> "ScriptedToolCallingModel":
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


class ToolEchoingModel(BaseChatModel):
    """A model whose first call requests one tool, and whose second call echoes
    that tool's own result text back verbatim as the final answer.

    Used by the isolation acceptance test: scripting a fixed final answer would
    only prove the test's own string contains no leaked data, not that the tool
    itself refused to hand any over. Echoing the real ``ToolMessage`` content makes
    the assertion depend on what the tool actually returned.

    :ivar first_call: The scripted first response, carrying the tool call to make.
    :ivar seen: The messages each call was given, one list per call, in call order.
    """

    first_call: AIMessage
    seen: list[list[BaseMessage]] = Field(default_factory=list)
    _call_count: int = PrivateAttr(default=0)

    def bind_tools(self, tools: Sequence[BaseTool], **kwargs: Any) -> "ToolEchoingModel":
        """Return this model unchanged."""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Return the scripted tool call first, then echo the tool's own result.

        :param messages: The conversation so far, recorded in ``seen``; on the second
            call, the last message is the :class:`~langchain_core.messages.ToolMessage`
            the tool node produced.
        :param stop: Unused.
        :param run_manager: Unused.
        :return: The scripted first call, or an echo of the tool's result text.
        """
        self.seen.append(list(messages))
        self._call_count += 1
        if self._call_count == 1:
            return ChatResult(generations=[ChatGeneration(message=self.first_call)])
        tool_message = messages[-1]
        echo = AIMessage(content=f"Tool said: {tool_message.content}")
        return ChatResult(generations=[ChatGeneration(message=echo)])

    @property
    def _llm_type(self) -> str:
        """Return the model type name LangChain's tracing uses."""
        return "tool-echoing-model"
