"""Exceptions raised by the local assistant while it acts on a user's behalf."""

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
