"""Exceptions raised by the assistant while it acts on a user's behalf."""

from typing import Literal

from api.exceptions import BeCoMeAPIError


class AssistantError(BeCoMeAPIError):
    """Base exception for the assistant feature."""


class AssistantNotFoundError(AssistantError):
    """Raised when the caller cannot see the requested project.

    Covers both a missing project and one the caller is not a member of: the
    underlying API answers the same 404 for either, exactly as it does for the UI,
    so this exception draws no distinction between them either. A project id that
    is not a UUID at all is refused the same way, before any request is sent.
    """


class AssistantUpstreamError(AssistantError):
    """Raised when the underlying API answers with any other non-2xx status."""


class AssistantUnavailableError(AssistantError):
    """Raised when the local LLM, embedding, or rerank server cannot be reached."""


class AssistantBusyError(AssistantError):
    """Raised when this process is already answering its limit of concurrent turns.

    The cause is load, not the caller: it is answered 503, never 429.

    :param message: Description for the log; never shown to the caller.
    :param retry_after: Whole seconds the caller should wait, sent as ``Retry-After``.
    :param reason: The limit that refused the turn: ``"process"`` for the whole process,
        ``"user"`` for this caller's own share. It goes into the one log record.
    """

    def __init__(
        self, message: str, *, retry_after: int, reason: Literal["process", "user"]
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.reason = reason


class AssistantRateLimitedError(AssistantError):
    """Raised when a user has spent their per-hour assistant message budget.

    :param message: Description for the log; never shown to the caller.
    :param retry_after: Whole seconds until the user's window closes, sent as ``Retry-After``.
    """

    def __init__(self, message: str, *, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after
