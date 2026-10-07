"""Assistant feature request/response schemas."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.assistant.rag.corpus import Layer

# Hard ceilings on what one request may carry. Kept equal to
# Settings.assistant_max_message_chars and to twice Settings.assistant_max_history_turns
# (one user and one assistant entry per exchange), which the chat service applies as
# limits that can only lower these; a test pins both, so the numbers cannot drift apart
# silently. A history entry has a higher cap than a new message: it may be an assistant
# reply the tab replays, and one longer than the user is allowed to type must not turn
# the next request into a 422.
MAX_MESSAGE_CHARS = 4000
MAX_HISTORY_ENTRIES = 20
MAX_HISTORY_CONTENT_CHARS = 8000


class AssistantConfigResponse(BaseModel):
    """Which model, mode, and document collection currently serve the assistant.

    The three providers say where each model role runs, ``local`` or ``api``. The
    response never carries a key or a URL.
    """

    enabled: bool
    model: str
    mode: str
    collection: str
    answer_provider: str
    query_provider: str
    embedding_provider: str


class ChatTurn(BaseModel):
    """One turn of chat history, as the browser tab replays it with every request.

    Only the two conversational roles are accepted: a client-supplied ``system`` or
    ``tool`` entry would be an instruction channel the server never offered.
    """

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(max_length=MAX_HISTORY_CONTENT_CHARS)


class AssistantChatRequest(BaseModel):
    """A chat turn, with the recent history the tab is holding."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    history: list[ChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_ENTRIES)
    project_id: UUID | None = None
    locale: Literal["en", "cs"] = "en"

    @field_validator("message")
    @classmethod
    def _reject_blank_message(cls, value: str) -> str:
        """Refuse a message that is nothing but whitespace, returning any other unchanged.

        :param value: The submitted message.
        :return: The same message, untouched.
        :raises ValueError: If the message holds only whitespace.
        """
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


class SourceRef(BaseModel):
    """One documentation passage the answer may cite as ``[n]``."""

    n: int
    title: str
    section: str
    url: str | None
    layer: Layer


class AnswerChecks(BaseModel):
    """Post-generation grounding checks run on the answer before it is returned."""

    citations_valid: bool
    numbers_grounded: bool
    ungrounded_numbers: list[str]


class TurnUsage(BaseModel):
    """The tokens the answer model used in one chat turn, summed over its replies.

    ``complete`` is false when a reply reported no usage: its tokens are then missing from
    the sums, though it is still counted in ``llm_calls``.
    """

    model_config = ConfigDict(frozen=True)

    input_tokens: int
    output_tokens: int
    total_tokens: int
    llm_calls: int
    complete: bool


class TurnTiming(BaseModel):
    """How long one chat turn took, in milliseconds.

    ``ttft_ms`` is the time from the start of the answer model's call to its first piece
    of answer text, known only for a streamed turn; it is None for a turn answered in one
    piece. ``total_ms`` is the whole turn, retrieval included.
    """

    model_config = ConfigDict(frozen=True)

    ttft_ms: int | None
    total_ms: int


class AssistantChatResponse(BaseModel):
    """The assistant's answer to one chat turn."""

    answer: str
    sources: list[SourceRef]
    tools_used: list[str]
    checks: AnswerChecks
    usage: TurnUsage
    timing: TurnTiming
