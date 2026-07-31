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

    @abstractmethod
    async def send_email_verification(self, *, to_email: str, verify_url: str) -> None:
        """Send (or log) an account-verification message.

        :param to_email: Recipient email address.
        :param verify_url: Full frontend link the user clicks to activate the account;
            it already carries the raw verification token as a query parameter.
        :raises EmailSendError: If a real send fails.
        """

    @abstractmethod
    async def send_registration_attempt_notice(
        self, *, to_email: str, login_url: str, reset_url: str
    ) -> None:
        """Send (or log) a notice that registration was attempted with a taken address.

        Sent to the existing, verified account instead of exposing through the
        registration response that the address is taken. Carries both a sign-in
        link and a password-reset link so the recipient can act either way from
        the same message.

        :param to_email: Recipient email address (the existing account's address).
        :param login_url: Full frontend link to the sign-in page.
        :param reset_url: Full frontend link to the password-reset flow.
        :raises EmailSendError: If a real send fails.
        """
