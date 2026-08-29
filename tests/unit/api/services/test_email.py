"""Unit tests for the email sender implementations."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from api.services.email.console_email_sender import ConsoleEmailSender, _mask_token
from api.services.email.exceptions import EmailSendError
from api.services.email.resend_email_sender import ResendEmailSender


def _settings(**overrides: object) -> MagicMock:
    """Build a settings stub with valid email configuration."""
    settings = MagicMock()
    settings.email_from = "no-reply@become.app"
    settings.email_from_name = "BeCoMe"
    settings.email_api_key = "re_test_key"
    settings.email_api_url = "https://api.resend.com/emails"
    settings.password_reset_token_ttl_minutes = 60
    settings.email_verification_token_ttl_hours = 24
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


class TestConsoleEmailSender:
    """Tests for the development console email sender."""

    _RAW_TOKEN = "S3cret-Reset-Token-abcdefghijklmnop-1234567890"
    _RESET_URL = f"https://app.example/reset-password?token={_RAW_TOKEN}"
    _VERIFY_URL = f"https://app.example/verify-email?token={_RAW_TOKEN}"
    _LOGIN_URL = "https://app.example/login"

    def _send(self):
        """Send a reset email through the console sender with the logger patched."""
        sender = ConsoleEmailSender(_settings())
        with patch("api.services.email.console_email_sender.logger") as mock_logger:
            asyncio.run(
                sender.send_password_reset(to_email="user@example.com", reset_url=self._RESET_URL)
            )
        return mock_logger

    def test_info_log_masks_the_raw_token(self):
        """
        GIVEN a console email sender
        WHEN a password reset email is sent
        THEN the INFO record never carries the full raw token
        """
        # WHEN
        mock_logger = self._send()

        # THEN
        mock_logger.info.assert_called_once()
        info_str = str(mock_logger.info.call_args)
        assert self._RAW_TOKEN not in info_str
        assert "..." in info_str

    def test_no_log_record_carries_the_redeemable_link(self):
        """
        GIVEN a console email sender
        WHEN a password reset email is sent
        THEN no record reaches the logger with the full link

        Records travel to the rotating file handler and, when configured, to the
        Better Stack drain. A redeemable token must not ride along on either.
        """
        # WHEN
        mock_logger = self._send()

        # THEN
        assert self._RAW_TOKEN not in str(mock_logger.method_calls)

    def test_full_link_goes_to_stdout_for_local_dev(self, capsys):
        """
        GIVEN a console email sender
        WHEN a password reset email is sent
        THEN the full link is printed, so the offline dev flow still works
        """
        # GIVEN
        sender = ConsoleEmailSender(_settings())

        # WHEN
        asyncio.run(
            sender.send_password_reset(to_email="user@example.com", reset_url=self._RESET_URL)
        )

        # THEN
        assert self._RESET_URL in capsys.readouterr().out

    def _send_verification(self):
        """Send a verification email through the console sender with the logger patched."""
        sender = ConsoleEmailSender(_settings())
        with patch("api.services.email.console_email_sender.logger") as mock_logger:
            asyncio.run(
                sender.send_email_verification(
                    to_email="user@example.com", verify_url=self._VERIFY_URL
                )
            )
        return mock_logger

    def _send_registration_attempt_notice(self):
        """Send a registration-attempt notice through the console sender, logger patched."""
        sender = ConsoleEmailSender(_settings())
        with patch("api.services.email.console_email_sender.logger") as mock_logger:
            asyncio.run(
                sender.send_registration_attempt_notice(
                    to_email="user@example.com",
                    login_url=self._LOGIN_URL,
                    reset_url=self._RESET_URL,
                )
            )
        return mock_logger

    def test_verification_log_masks_the_raw_token(self):
        """
        GIVEN a console email sender
        WHEN an email verification message is sent
        THEN the INFO record never carries the full raw token
        """
        # WHEN
        mock_logger = self._send_verification()

        # THEN
        mock_logger.info.assert_called_once()
        info_str = str(mock_logger.info.call_args)
        assert self._RAW_TOKEN not in info_str
        assert "..." in info_str

    def test_verification_no_log_record_carries_the_redeemable_link(self):
        """
        GIVEN a console email sender
        WHEN an email verification message is sent
        THEN no record reaches the logger with the full link
        """
        # WHEN
        mock_logger = self._send_verification()

        # THEN
        assert self._RAW_TOKEN not in str(mock_logger.method_calls)

    def test_verification_full_link_goes_to_stdout_for_local_dev(self, capsys):
        """
        GIVEN a console email sender
        WHEN an email verification message is sent
        THEN the full link is printed, so the offline dev flow still works
        """
        # GIVEN
        sender = ConsoleEmailSender(_settings())

        # WHEN
        asyncio.run(
            sender.send_email_verification(to_email="user@example.com", verify_url=self._VERIFY_URL)
        )

        # THEN
        assert self._VERIFY_URL in capsys.readouterr().out

    def test_registration_attempt_notice_log_masks_the_raw_token(self):
        """
        GIVEN a console email sender
        WHEN a registration-attempt notice is sent
        THEN the INFO record never carries the full raw reset token
        """
        # WHEN
        mock_logger = self._send_registration_attempt_notice()

        # THEN
        mock_logger.info.assert_called_once()
        info_str = str(mock_logger.info.call_args)
        assert self._RAW_TOKEN not in info_str
        assert "..." in info_str

    def test_registration_attempt_notice_no_log_record_carries_the_redeemable_link(self):
        """
        GIVEN a console email sender
        WHEN a registration-attempt notice is sent
        THEN no record reaches the logger with the full reset token
        """
        # WHEN
        mock_logger = self._send_registration_attempt_notice()

        # THEN
        assert self._RAW_TOKEN not in str(mock_logger.method_calls)

    def test_registration_attempt_notice_full_links_go_to_stdout_for_local_dev(self, capsys):
        """
        GIVEN a console email sender
        WHEN a registration-attempt notice is sent
        THEN both full links are printed, so the offline dev flow still works
        """
        # GIVEN
        sender = ConsoleEmailSender(_settings())

        # WHEN
        asyncio.run(
            sender.send_registration_attempt_notice(
                to_email="user@example.com",
                login_url=self._LOGIN_URL,
                reset_url=self._RESET_URL,
            )
        )

        # THEN
        out = capsys.readouterr().out
        assert self._LOGIN_URL in out
        assert self._RESET_URL in out

    def test_registration_attempt_notice_static_reset_link_is_not_masked(self, capsys):
        """
        GIVEN a registration-attempt notice carrying a static forgot-password link --
        the shape the product actually sends, since minting a real reset token for an
        unauthenticated registration attempt would let anyone flood a victim's inbox
        with working reset links
        WHEN the notice is sent
        THEN the link appears verbatim in both the log record and stdout
        """
        # GIVEN
        static_reset_url = "https://app.example/forgot-password"
        sender = ConsoleEmailSender(_settings())

        # WHEN
        with patch("api.services.email.console_email_sender.logger") as mock_logger:
            asyncio.run(
                sender.send_registration_attempt_notice(
                    to_email="user@example.com",
                    login_url=self._LOGIN_URL,
                    reset_url=static_reset_url,
                )
            )

        # THEN
        assert static_reset_url in str(mock_logger.info.call_args)
        assert static_reset_url in capsys.readouterr().out


class TestMaskToken:
    """Tests for the reset-link token masking helper."""

    def test_fully_masks_a_short_token(self):
        """A token at or below the prefix length is hidden entirely."""
        # WHEN
        masked = _mask_token("https://app.example/reset-password?token=short")

        # THEN
        assert "short" not in masked
        assert "token=..." in masked

    def test_returns_url_unchanged_without_a_token(self):
        """A URL without a token query parameter is returned as-is."""
        # GIVEN
        url = "https://app.example/reset-password"

        # WHEN/THEN
        assert _mask_token(url) == url


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

    def test_email_body_reflects_configured_ttl(self):
        """
        GIVEN a Resend sender whose token TTL is 30 minutes
        WHEN a password reset email is sent
        THEN the email body states the matching expiry window, not a hardcoded one
        """
        # GIVEN
        response = MagicMock()
        response.raise_for_status = MagicMock()
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        sender = ResendEmailSender(_settings(password_reset_token_ttl_minutes=30), client=client)

        # WHEN
        asyncio.run(
            sender.send_password_reset(
                to_email="user@example.com",
                reset_url="https://app.example/reset",
            )
        )

        # THEN
        html = client.post.call_args.kwargs["json"]["html"]
        assert "30 minutes" in html
        assert "one hour" not in html

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

        # WHEN/THEN
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

        # WHEN/THEN
        with pytest.raises(EmailSendError):
            asyncio.run(
                sender.send_password_reset(
                    to_email="user@example.com",
                    reset_url="https://app.example/reset",
                )
            )

    def test_creates_own_client_when_none_injected(self):
        """
        GIVEN a Resend sender with no injected client
        WHEN a password reset email is sent
        THEN it opens its own AsyncClient and posts through it
        """
        # GIVEN
        sender = ResendEmailSender(_settings())
        response = MagicMock()
        response.raise_for_status = MagicMock()
        own_client = MagicMock()
        own_client.post = AsyncMock(return_value=response)
        async_cm = MagicMock()
        async_cm.__aenter__ = AsyncMock(return_value=own_client)
        async_cm.__aexit__ = AsyncMock(return_value=None)

        # WHEN
        with patch(
            "api.services.email.resend_email_sender.httpx.AsyncClient",
            return_value=async_cm,
        ):
            asyncio.run(
                sender.send_password_reset(
                    to_email="user@example.com",
                    reset_url="https://app.example/reset",
                )
            )

        # THEN
        own_client.post.assert_awaited_once()

    def test_verification_posts_to_api_with_bearer_and_payload(self):
        """
        GIVEN a Resend sender with an injected client
        WHEN an email verification message is sent
        THEN it POSTs to the API URL with a bearer header and the verification link
        """
        # GIVEN
        response = MagicMock()
        response.raise_for_status = MagicMock()
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        sender = ResendEmailSender(_settings(), client=client)

        # WHEN
        asyncio.run(
            sender.send_email_verification(
                to_email="user@example.com",
                verify_url="https://app.example/verify-email?token=abc",
            )
        )

        # THEN
        client.post.assert_awaited_once()
        call = client.post.call_args
        assert call.args[0] == "https://api.resend.com/emails"
        assert call.kwargs["headers"]["Authorization"] == "Bearer re_test_key"
        assert call.kwargs["json"]["to"] == ["user@example.com"]
        assert call.kwargs["json"]["subject"] == "Confirm your BeCoMe email"
        assert "https://app.example/verify-email?token=abc" in call.kwargs["json"]["html"]

    def test_verification_email_body_reflects_configured_ttl(self):
        """
        GIVEN a Resend sender whose verification-token TTL is 1 hour
        WHEN an email verification message is sent
        THEN the email body states the matching expiry window, not a hardcoded number
        """
        # GIVEN
        response = MagicMock()
        response.raise_for_status = MagicMock()
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        sender = ResendEmailSender(_settings(email_verification_token_ttl_hours=1), client=client)

        # WHEN
        asyncio.run(
            sender.send_email_verification(
                to_email="user@example.com",
                verify_url="https://app.example/verify-email?token=abc",
            )
        )

        # THEN
        html = client.post.call_args.kwargs["json"]["html"]
        assert "1 hour" in html
        assert "24 hours" not in html

    def test_verification_raises_send_error_on_http_status_error(self):
        """
        GIVEN a Resend sender whose response is a non-2xx status
        WHEN an email verification message is sent
        THEN EmailSendError is raised with an operator-facing message
        """
        # GIVEN
        response = MagicMock()
        response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("400", request=MagicMock(), response=MagicMock())
        )
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        sender = ResendEmailSender(_settings(), client=client)

        # WHEN/THEN
        with pytest.raises(EmailSendError, match="Failed to send verification email"):
            asyncio.run(
                sender.send_email_verification(
                    to_email="user@example.com",
                    verify_url="https://app.example/verify-email?token=abc",
                )
            )

    def test_registration_attempt_notice_posts_to_api_with_bearer_and_payload(self):
        """
        GIVEN a Resend sender with an injected client
        WHEN a registration-attempt notice is sent
        THEN it POSTs to the API URL with a bearer header and both links
        """
        # GIVEN
        response = MagicMock()
        response.raise_for_status = MagicMock()
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        sender = ResendEmailSender(_settings(), client=client)

        # WHEN
        asyncio.run(
            sender.send_registration_attempt_notice(
                to_email="user@example.com",
                login_url="https://app.example/login",
                reset_url="https://app.example/reset-password?token=abc",
            )
        )

        # THEN
        client.post.assert_awaited_once()
        call = client.post.call_args
        assert call.args[0] == "https://api.resend.com/emails"
        assert call.kwargs["headers"]["Authorization"] == "Bearer re_test_key"
        assert call.kwargs["json"]["to"] == ["user@example.com"]
        assert call.kwargs["json"]["subject"] == "You already have a BeCoMe account"
        html = call.kwargs["json"]["html"]
        assert "https://app.example/login" in html
        assert "https://app.example/reset-password?token=abc" in html

    def test_registration_attempt_notice_raises_send_error_on_transport_error(self):
        """
        GIVEN a Resend sender whose client fails to connect
        WHEN a registration-attempt notice is sent
        THEN EmailSendError is raised with an operator-facing message
        """
        # GIVEN
        client = MagicMock()
        client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        sender = ResendEmailSender(_settings(), client=client)

        # WHEN/THEN
        with pytest.raises(EmailSendError, match="Failed to send registration attempt notice"):
            asyncio.run(
                sender.send_registration_attempt_notice(
                    to_email="user@example.com",
                    login_url="https://app.example/login",
                    reset_url="https://app.example/reset-password?token=abc",
                )
            )
