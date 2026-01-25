"""Unit tests for security event logging."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from api.auth.logging import (
    _get_client_ip,
    log_account_deletion,
    log_login_failure,
    log_login_success,
    log_password_change,
    log_registration,
)


class TestLogLoginSuccess:
    """Tests for log_login_success function."""

    def test_logs_info_with_correct_event_type(self):
        """Login success is logged at INFO level with correct event type."""
        # GIVEN
        user_id = uuid4()
        email = "test@example.com"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_login_success(user_id, email)

        # THEN
        mock_logger.info.assert_called_once()
        call_kwargs = mock_logger.info.call_args
        assert call_kwargs[1]["extra"]["event"] == "login_success"

    def test_includes_user_id_and_email(self):
        """Login success log includes user_id and email."""
        # GIVEN
        user_id = uuid4()
        email = "user@example.com"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_login_success(user_id, email)

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["user_id"] == str(user_id)
        assert extra["email"] == email

    def test_extracts_ip_from_request(self):
        """Login success extracts IP from request object."""
        # GIVEN
        user_id = uuid4()
        email = "test@example.com"
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "192.168.1.100"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_login_success(user_id, email, mock_request)

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["ip"] == "192.168.1.100"

    def test_handles_none_request(self):
        """Login success handles None request gracefully."""
        # GIVEN
        user_id = uuid4()
        email = "test@example.com"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_login_success(user_id, email, None)

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["ip"] == "unknown"


class TestLogLoginFailure:
    """Tests for log_login_failure function."""

    def test_logs_warning_level(self):
        """Login failure is logged at WARNING level."""
        # GIVEN
        email = "attacker@example.com"
        reason = "Invalid password"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_login_failure(email, reason)

        # THEN
        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args
        assert call_kwargs[1]["extra"]["event"] == "login_failure"

    def test_includes_failure_reason(self):
        """Login failure log includes the reason."""
        # GIVEN
        email = "user@example.com"
        reason = "Account locked"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_login_failure(email, reason)

        # THEN
        extra = mock_logger.warning.call_args[1]["extra"]
        assert extra["email"] == email
        assert extra["reason"] == reason

    def test_extracts_ip_from_request(self):
        """Login failure extracts IP from request."""
        # GIVEN
        email = "test@example.com"
        reason = "Wrong password"
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "10.0.0.50"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_login_failure(email, reason, mock_request)

        # THEN
        extra = mock_logger.warning.call_args[1]["extra"]
        assert extra["ip"] == "10.0.0.50"

    def test_handles_none_request(self):
        """Login failure handles None request gracefully."""
        # GIVEN
        email = "test@example.com"
        reason = "Invalid credentials"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_login_failure(email, reason, None)

        # THEN
        mock_logger.warning.assert_called_once()
        extra = mock_logger.warning.call_args[1]["extra"]
        assert extra["event"] == "login_failure"
        assert extra["email"] == email
        assert extra["reason"] == reason
        assert extra["ip"] == "unknown"


class TestLogRegistration:
    """Tests for log_registration function."""

    def test_logs_info_with_registration_event(self):
        """Registration is logged at INFO level with correct event type."""
        # GIVEN
        user_id = uuid4()
        email = "newuser@example.com"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_registration(user_id, email)

        # THEN
        mock_logger.info.assert_called_once()
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["event"] == "registration"

    def test_includes_new_user_details(self):
        """Registration log includes user_id and email."""
        # GIVEN
        user_id = uuid4()
        email = "newbie@example.com"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_registration(user_id, email)

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["user_id"] == str(user_id)
        assert extra["email"] == email

    def test_extracts_ip_from_request(self):
        """Registration extracts IP from request."""
        # GIVEN
        user_id = uuid4()
        email = "newuser@example.com"
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "203.0.113.100"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_registration(user_id, email, mock_request)

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["ip"] == "203.0.113.100"

    def test_handles_none_request(self):
        """Registration handles None request gracefully."""
        # GIVEN
        user_id = uuid4()
        email = "newuser@example.com"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_registration(user_id, email, None)

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["ip"] == "unknown"


class TestLogPasswordChange:
    """Tests for log_password_change function."""

    def test_logs_info_for_password_change(self):
        """Password change is logged at INFO level."""
        # GIVEN
        user_id = uuid4()

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_password_change(user_id)

        # THEN
        mock_logger.info.assert_called_once()
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["event"] == "password_change"
        assert extra["user_id"] == str(user_id)

    def test_extracts_ip_from_request(self):
        """Password change extracts IP from request."""
        # GIVEN
        user_id = uuid4()
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "172.16.0.1"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_password_change(user_id, mock_request)

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["ip"] == "172.16.0.1"


class TestLogAccountDeletion:
    """Tests for log_account_deletion function."""

    def test_logs_info_with_user_details(self):
        """Account deletion is logged at INFO level with user details."""
        # GIVEN
        user_id = uuid4()
        email = "deleted@example.com"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_account_deletion(user_id, email)

        # THEN
        mock_logger.info.assert_called_once()
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["event"] == "account_deletion"
        assert extra["user_id"] == str(user_id)
        assert extra["email"] == email

    def test_extracts_ip_from_request(self):
        """Account deletion extracts IP from request."""
        # GIVEN
        user_id = uuid4()
        email = "user@example.com"
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "8.8.8.8"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_account_deletion(user_id, email, mock_request)

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["ip"] == "8.8.8.8"


class TestGetClientIp:
    """Tests for _get_client_ip helper function."""

    def test_extracts_from_x_forwarded_for(self):
        """IP is extracted from X-Forwarded-For header."""
        # GIVEN
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "203.0.113.50"

        # WHEN
        result = _get_client_ip(mock_request)

        # THEN
        assert result == "203.0.113.50"
        mock_request.headers.get.assert_called_with("X-Forwarded-For")

    def test_handles_multiple_ips_in_forwarded(self):
        """First IP is extracted when X-Forwarded-For has multiple IPs."""
        # GIVEN
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "203.0.113.50, 70.41.3.18, 150.172.238.178"

        # WHEN
        result = _get_client_ip(mock_request)

        # THEN
        assert result == "203.0.113.50"

    def test_strips_whitespace_from_forwarded_ip(self):
        """Whitespace is stripped from X-Forwarded-For IP."""
        # GIVEN
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "  192.168.1.1  , 10.0.0.1"

        # WHEN
        result = _get_client_ip(mock_request)

        # THEN
        assert result == "192.168.1.1"

    def test_fallback_to_client_host(self):
        """IP falls back to client.host when no X-Forwarded-For."""
        # GIVEN
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "127.0.0.1"

        # WHEN
        result = _get_client_ip(mock_request)

        # THEN
        assert result == "127.0.0.1"

    def test_returns_unknown_when_no_client(self):
        """Returns 'unknown' when request.client is None."""
        # GIVEN
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client = None

        # WHEN
        result = _get_client_ip(mock_request)

        # THEN
        assert result == "unknown"

    def test_returns_unknown_for_none_request(self):
        """Returns 'unknown' when request is None."""
        # WHEN
        result = _get_client_ip(None)

        # THEN
        assert result == "unknown"
