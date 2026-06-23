"""Development email sender that logs the message instead of sending it."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from api.services.email.base import EmailSender

if TYPE_CHECKING:
    from api.config import Settings

logger = logging.getLogger("api.service.email")


class ConsoleEmailSender(EmailSender):
    """Log the password-reset link instead of sending an email.

    Used in development, CI, and tests: the flow works offline and the reset
    link is read straight from the application log. Never selected in
    production, so the link (and its token) only ever reaches a
    developer-visible log.

    :param settings: Application settings (kept for a uniform sender signature).
    """

    def __init__(self, settings: Settings) -> None:
        """Store settings for signature parity with real senders."""
        self._settings = settings

    async def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
        """Log the reset link; perform no network call.

        :param to_email: Recipient email address.
        :param reset_url: Full frontend reset link (carries the raw token).
        """
        logger.info(
            "Password reset link (console sender) for %s: %s",
            to_email,
            reset_url,
            extra={"event": "password_reset_email", "to_email": to_email},
        )
