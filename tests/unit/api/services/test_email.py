"""Unit tests for the email sender implementations."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from api.services.email.console_email_sender import ConsoleEmailSender
from api.services.email.exceptions import EmailSendError
from api.services.email.resend_email_sender import ResendEmailSender


def _settings(**overrides: object) -> MagicMock:
    """Build a settings stub with valid email configuration."""
    settings = MagicMock()
    settings.email_from = "no-reply@become.app"
    settings.email_from_name = "BeCoMe"
    settings.email_api_key = "re_test_key"
    settings.email_api_url = "https://api.resend.com/emails"
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


class TestConsoleEmailSender:
    """Tests for the development console email sender."""

    def test_logs_reset_link_without_network(self, caplog):
        """
        GIVEN a console email sender
        WHEN a password reset email is sent
        THEN the reset link is logged and no network call is made
        """
        # GIVEN
        sender = ConsoleEmailSender(_settings())

        # WHEN
        with caplog.at_level(logging.INFO, logger="api.service.email"):
            asyncio.run(
                sender.send_password_reset(
                    to_email="user@example.com",
                    reset_url="https://app.example/reset-password?token=abc123",
                )
            )

        # THEN
        assert "https://app.example/reset-password?token=abc123" in caplog.text


class TestResendEmailSender:
    """Tests for the production Resend HTTP email sender."""

    def test_posts_to_api_with_bearer_and_payload(self):
        """
        GIVEN a Resend sender with an injected client
        WHEN a password reset email is sent
        THEN it POSTs to the API URL with a bearer header and the reset link
        """
        # GIVEN
        response = MagicMock()
        response.raise_for_status = MagicMock()
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        sender = ResendEmailSender(_settings(), client=client)

        # WHEN
        asyncio.run(
            sender.send_password_reset(
                to_email="user@example.com",
                reset_url="https://app.example/reset-password?token=abc",
            )
        )

        # THEN
        client.post.assert_awaited_once()
        call = client.post.call_args
        assert call.args[0] == "https://api.resend.com/emails"
        assert call.kwargs["headers"]["Authorization"] == "Bearer re_test_key"
        assert call.kwargs["json"]["to"] == ["user@example.com"]
        assert "https://app.example/reset-password?token=abc" in call.kwargs["json"]["html"]

    def test_raises_send_error_on_http_status_error(self):
        """
        GIVEN a Resend sender whose response is a non-2xx status
        WHEN a password reset email is sent
        THEN EmailSendError is raised
        """
        # GIVEN
        response = MagicMock()
        response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("400", request=MagicMock(), response=MagicMock())
        )
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        sender = ResendEmailSender(_settings(), client=client)

        # WHEN / THEN
        with pytest.raises(EmailSendError):
            asyncio.run(
                sender.send_password_reset(
                    to_email="user@example.com",
                    reset_url="https://app.example/reset",
                )
            )

    def test_raises_send_error_on_transport_error(self):
        """
        GIVEN a Resend sender whose client fails to connect
        WHEN a password reset email is sent
        THEN EmailSendError is raised
        """
        # GIVEN
        client = MagicMock()
        client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        sender = ResendEmailSender(_settings(), client=client)

        # WHEN / THEN
        with pytest.raises(EmailSendError):
            asyncio.run(
                sender.send_password_reset(
                    to_email="user@example.com",
                    reset_url="https://app.example/reset",
                )
            )
