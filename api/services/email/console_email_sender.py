"""Development email sender that logs the message instead of sending it."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from api.services.email.base import EmailSender

if TYPE_CHECKING:
    from api.config import Settings

logger = logging.getLogger("api.service.email")

_TOKEN_PREFIX_LEN = 8


def _mask_token(reset_url: str) -> str:
    """Mask the reset token value in a reset URL.

    Keeps a few leading characters so two links stay distinguishable in the log
    without exposing the full single-use token. Returns the URL unchanged when
    it carries no ``token`` parameter.

    :param reset_url: Full reset link carrying a ``token`` query parameter.
    :return: The URL with the token value masked.

    >>> _mask_token("https://app/reset-password?token=abcdefghijklmnop")
    'https://app/reset-password?token=abcdefgh...'
    """
    parts = urlparse(reset_url)
    params = parse_qs(parts.query)
    raw = params.get("token", [""])[0]
    if not raw:
        return reset_url
    params["token"] = [f"{raw[:_TOKEN_PREFIX_LEN]}..." if len(raw) > _TOKEN_PREFIX_LEN else "..."]
    return urlunparse(parts._replace(query=urlencode(params, doseq=True)))


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

        The INFO record masks the single-use token so an aggregated log never
        captures it; the full link stays at DEBUG for the local dev flow.

        :param to_email: Recipient email address.
        :param reset_url: Full frontend reset link (carries the raw token).
        """
        logger.info(
            "Password reset link (console sender) for %s: %s",
            to_email,
            _mask_token(reset_url),
            extra={"event": "password_reset_email", "to_email": to_email},
        )
        logger.debug(
            "Password reset link (full, console sender) for %s: %s",
            to_email,
            reset_url,
            extra={"event": "password_reset_email", "to_email": to_email},
        )
