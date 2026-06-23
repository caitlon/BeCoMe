"""Abstract email-sender interface for transactional mail."""

from abc import ABC, abstractmethod


class EmailSender(ABC):
    """Transactional email backend.

    Implementations either send a real message (production) or log its contents
    (development). The interface stays minimal -- one method per transactional
    message the app needs -- so concrete senders implement only what is used.
    """

    @abstractmethod
    async def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
        """Send (or log) a password-reset message.

        :param to_email: Recipient email address.
        :param reset_url: Full frontend link the user clicks to reset; it already
            carries the raw reset token as a query parameter.
        :raises EmailSendError: If a real send fails.
        """
