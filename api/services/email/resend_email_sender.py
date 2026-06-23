"""Production email sender using the Resend HTTP API."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from api.services.email.base import EmailSender
from api.services.email.exceptions import EmailSendError

if TYPE_CHECKING:
    from api.config import Settings

_TIMEOUT_SECONDS = 10.0


class ResendEmailSender(EmailSender):
    """Send transactional email through the Resend HTTP API.

    :param settings: Application settings carrying the API key, URL, and sender
        identity.
    :param client: Preconfigured async HTTP client; a fresh one is created per
        request when omitted (injected directly in tests).
    """

    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None) -> None:
        """Store settings and an optional injected HTTP client."""
        self._settings = settings
        self._client = client

    async def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
        """Send a password-reset email via Resend.

        :param to_email: Recipient email address.
        :param reset_url: Full frontend reset link.
        :raises EmailSendError: If the API rejects the request or transport fails.
        """
        payload: dict[str, object] = {
            "from": f"{self._settings.email_from_name} <{self._settings.email_from}>",
            "to": [to_email],
            "subject": "Reset your BeCoMe password",
            "html": self._build_html(reset_url),
        }
        headers = {"Authorization": f"Bearer {self._settings.email_api_key}"}
        try:
            response = await self._post(payload, headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmailSendError(f"Failed to send password reset email: {exc}") from exc

    @staticmethod
    def _build_html(reset_url: str) -> str:
        """Render the reset-email HTML body.

        :param reset_url: Full frontend reset link.
        :return: HTML message body.
        """
        return (
            "<p>We received a request to reset your BeCoMe password.</p>"
            f'<p><a href="{reset_url}">Reset your password</a></p>'
            "<p>If you did not request this you can ignore this email. "
            "The link expires in one hour.</p>"
        )

    async def _post(self, payload: dict[str, object], headers: dict[str, str]) -> httpx.Response:
        """POST the payload using the injected client or a fresh one.

        :param payload: JSON request body.
        :param headers: Request headers.
        :return: The HTTP response.
        """
        if self._client is not None:
            return await self._client.post(
                self._settings.email_api_url, json=payload, headers=headers
            )
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            return await client.post(self._settings.email_api_url, json=payload, headers=headers)
