"""Production email sender using the Resend HTTP API."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from api.services.email.base import EmailSender
from api.services.email.exceptions import EmailSendError

if TYPE_CHECKING:
    from api.config import Settings

_TIMEOUT_SECONDS = 10.0
_MINUTES_PER_HOUR = 60


def _format_ttl_window(minutes: int) -> str:
    """Render a token TTL in minutes as a human-friendly expiry window.

    :param minutes: Token lifetime in minutes.
    :return: ``"1 hour"`` / ``"N hours"`` for whole hours, else ``"N minutes"``.
    """
    if minutes % _MINUTES_PER_HOUR == 0:
        hours = minutes // _MINUTES_PER_HOUR
        return "1 hour" if hours == 1 else f"{hours} hours"
    return f"{minutes} minutes"


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

    async def send_email_verification(self, *, to_email: str, verify_url: str) -> None:
        """Send an account-verification email via Resend.

        :param to_email: Recipient email address.
        :param verify_url: Full frontend activation link.
        :raises EmailSendError: If the API rejects the request or transport fails.
        """
        payload: dict[str, object] = {
            "from": f"{self._settings.email_from_name} <{self._settings.email_from}>",
            "to": [to_email],
            "subject": "Confirm your BeCoMe email",
            "html": self._build_verification_html(verify_url),
        }
        headers = {"Authorization": f"Bearer {self._settings.email_api_key}"}
        try:
            response = await self._post(payload, headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmailSendError(f"Failed to send verification email: {exc}") from exc

    async def send_registration_attempt_notice(
        self, *, to_email: str, login_url: str, reset_url: str
    ) -> None:
        """Send a registration-attempt notice via Resend.

        :param to_email: Recipient email address (the existing account's address).
        :param login_url: Full frontend sign-in link.
        :param reset_url: Full frontend password-reset link.
        :raises EmailSendError: If the API rejects the request or transport fails.
        """
        payload: dict[str, object] = {
            "from": f"{self._settings.email_from_name} <{self._settings.email_from}>",
            "to": [to_email],
            "subject": "You already have a BeCoMe account",
            "html": self._build_registration_attempt_html(login_url=login_url, reset_url=reset_url),
        }
        headers = {"Authorization": f"Bearer {self._settings.email_api_key}"}
        try:
            response = await self._post(payload, headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmailSendError(f"Failed to send registration attempt notice: {exc}") from exc

    def _build_html(self, reset_url: str) -> str:
        """Render the reset-email HTML body.

        :param reset_url: Full frontend reset link.
        :return: HTML message body, with the expiry window matching the config.
        """
        window = _format_ttl_window(self._settings.password_reset_token_ttl_minutes)
        return (
            "<p>We received a request to reset your BeCoMe password.</p>"
            f'<p><a href="{reset_url}">Reset your password</a></p>'
            "<p>If you did not request this you can ignore this email. "
            f"The link expires in {window}.</p>"
        )

    def _build_verification_html(self, verify_url: str) -> str:
        """Render the verification-email HTML body.

        :param verify_url: Full frontend activation link.
        :return: HTML message body, with the expiry window matching the config.
        """
        window = _format_ttl_window(
            self._settings.email_verification_token_ttl_hours * _MINUTES_PER_HOUR
        )
        return (
            "<p>Thanks for creating a BeCoMe account. Your account stays inactive "
            "until you confirm this email address.</p>"
            f'<p><a href="{verify_url}">Confirm your email</a></p>'
            f"<p>The link expires in {window}. If you did not create this account, "
            "you can ignore this email.</p>"
        )

    def _build_registration_attempt_html(self, *, login_url: str, reset_url: str) -> str:
        """Render the registration-attempt-notice HTML body.

        :param login_url: Full frontend sign-in link.
        :param reset_url: Full frontend password-reset link.
        :return: HTML message body.
        """
        return (
            "<p>Someone tried to sign up using this email address. "
            "Your account is untouched.</p>"
            f'<p><a href="{login_url}">Sign in</a>, or '
            f'<a href="{reset_url}">reset your password</a> if you no longer '
            "remember it.</p>"
            "<p>You do not have to do anything unless you want to.</p>"
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
