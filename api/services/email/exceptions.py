"""Email-specific exception hierarchy."""

from api.exceptions import BeCoMeAPIError


class EmailError(BeCoMeAPIError):
    """Base exception for email operations."""


class EmailSendError(EmailError):
    """Raised when sending an email fails."""
