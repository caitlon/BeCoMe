"""Unit tests for security event logging."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from api.auth.logging import (
    log_account_deletion,
    log_email_verified,
    log_login_blocked_unverified,
    log_login_failure,
    log_login_success,
    log_password_change,
    log_password_change_failure,
    log_registration_attempt,
    log_verification_email_requested,
    log_verification_password_mismatch,
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
        assert "email" not in extra  # raw email is never logged (GDPR)
        assert "email_hash" in extra

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
        assert "email" not in extra  # raw email is never logged (GDPR)
        assert "email_hash" in extra
        assert extra["reason"] == reason

    def test_extracts_ip_from_request(self):
        """Login failure extracts IP from request."""
        # GIVEN
        email = "test@example.com"
        reason = "Wrong password"
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "10.0.0.50"

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
        assert "email" not in extra  # raw email is never logged (GDPR)
        assert "email_hash" in extra
        assert extra["reason"] == reason
        assert extra["ip"] == "unknown"


class TestLogRegistrationAttempt:
    """Tests for log_registration_attempt function."""

    def test_logs_info_with_registration_attempt_event(self):
        """A registration submission is logged at INFO level with the right event type."""
        # GIVEN
        email = "newuser@example.com"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_registration_attempt(email)

        # THEN
        mock_logger.info.assert_called_once()
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["event"] == "registration_attempt"

    def test_records_only_a_hashed_address_and_no_user_id(self):
        """The record carries a hashed address and never names the account.

        The endpoint answers the same way for a free, an unverified, and a verified
        address, and this record keeps to that. It is not a claim that the branch is
        unrecoverable from logs in general: the service records written in the same
        request share its request id and do give the branch away, so log access is the
        trust boundary. What this pins is that the security log alone names no account.
        """
        # GIVEN
        email = "newbie@example.com"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_registration_attempt(email)

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert "email" not in extra  # raw email is never logged (GDPR)
        assert "email_hash" in extra
        assert "user_id" not in extra

    def test_extracts_ip_from_request(self):
        """A registration attempt extracts the IP from the request."""
        # GIVEN
        email = "newuser@example.com"
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "203.0.113.100"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_registration_attempt(email, mock_request)

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["ip"] == "203.0.113.100"

    def test_handles_none_request(self):
        """A registration attempt handles a None request gracefully."""
        # GIVEN
        email = "newuser@example.com"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_registration_attempt(email, None)

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["ip"] == "unknown"


class TestLogLoginBlockedUnverified:
    """Tests for log_login_blocked_unverified function."""

    def test_logs_warning_with_its_own_event(self):
        """A login refused for being unverified is a warning under its own event name.

        Kept apart from login_failure so a correct password on an unverified account
        never inflates brute-force alerting.
        """
        # GIVEN
        user_id = uuid4()

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_login_blocked_unverified(user_id)

        # THEN
        mock_logger.warning.assert_called_once()
        extra = mock_logger.warning.call_args[1]["extra"]
        assert extra["event"] == "login_blocked_unverified"
        assert extra["user_id"] == str(user_id)
        assert extra["ip"] == "unknown"

    def test_extracts_ip_from_request(self):
        """The blocked-login record carries the caller IP."""
        # GIVEN
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "203.0.113.55"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_login_blocked_unverified(uuid4(), mock_request)

        # THEN
        assert mock_logger.warning.call_args[1]["extra"]["ip"] == "203.0.113.55"


class TestLogVerificationEmailRequested:
    """Tests for log_verification_email_requested function."""

    def test_records_only_a_hashed_address_and_no_user_id(self):
        """A resend request logs a hashed address and never names the account."""
        # GIVEN
        email = "resend@example.com"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_verification_email_requested(email)

        # THEN
        mock_logger.info.assert_called_once()
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["event"] == "verification_email_requested"
        assert "email" not in extra
        assert "email_hash" in extra
        assert "user_id" not in extra

    def test_extracts_ip_from_request(self):
        """The resend record carries the caller IP."""
        # GIVEN
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "203.0.113.77"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_verification_email_requested("resend@example.com", mock_request)

        # THEN
        assert mock_logger.info.call_args[1]["extra"]["ip"] == "203.0.113.77"


class TestLogVerificationPasswordMismatch:
    """Tests for log_verification_password_mismatch function."""

    def test_logs_a_warning_naming_the_account_the_link_belongs_to(self):
        """A guess against a live link is its own event, and it names the account.

        Whoever sent the request already holds a link to that account, so the record
        gives a log reader nothing the requester did not have. Keeping it apart from
        ``login_failure`` stops it from distorting brute-force alerting on logins.
        """
        # GIVEN
        user_id = uuid4()

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_verification_password_mismatch(user_id)

        # THEN
        mock_logger.warning.assert_called_once()
        extra = mock_logger.warning.call_args[1]["extra"]
        assert extra["event"] == "verification_password_mismatch"
        assert extra["user_id"] == str(user_id)
        assert "email" not in extra
        assert "token" not in extra

    def test_extracts_ip_from_request(self):
        """The mismatch record carries the caller IP."""
        # GIVEN
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "203.0.113.99"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_verification_password_mismatch(uuid4(), mock_request)

        # THEN
        assert mock_logger.warning.call_args[1]["extra"]["ip"] == "203.0.113.99"


class TestLogEmailVerified:
    """Tests for log_email_verified function."""

    def test_logs_info_with_email_verified_event(self):
        """A redeemed activation link is logged with the account it activated."""
        # GIVEN
        user_id = uuid4()

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_email_verified(user_id)

        # THEN
        mock_logger.info.assert_called_once()
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["event"] == "email_verified"
        assert extra["user_id"] == str(user_id)
        assert extra["ip"] == "unknown"

    def test_extracts_ip_from_request(self):
        """The activation record carries the caller IP."""
        # GIVEN
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "203.0.113.90"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_email_verified(uuid4(), mock_request)

        # THEN
        assert mock_logger.info.call_args[1]["extra"]["ip"] == "203.0.113.90"


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


class TestLogPasswordChangeFailure:
    """Tests for log_password_change_failure function."""

    def test_logs_warning_with_event(self):
        """A failed password change is logged at WARNING with its own event type."""
        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_password_change_failure()

        # THEN
        mock_logger.warning.assert_called_once()
        extra = mock_logger.warning.call_args[1]["extra"]
        assert extra["event"] == "password_change_failure"

    def test_extracts_ip_from_request(self):
        """Failed password change extracts IP from request."""
        # GIVEN
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "10.0.0.7"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_password_change_failure(mock_request)

        # THEN
        extra = mock_logger.warning.call_args[1]["extra"]
        assert extra["ip"] == "10.0.0.7"

    def test_handles_none_request(self):
        """Failed password change handles None request gracefully."""
        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_password_change_failure(None)

        # THEN
        extra = mock_logger.warning.call_args[1]["extra"]
        assert extra["event"] == "password_change_failure"
        assert extra["ip"] == "unknown"


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
        assert "email" not in extra  # raw email is never logged (GDPR)
        assert "email_hash" in extra

    def test_extracts_ip_from_request(self):
        """Account deletion extracts IP from request."""
        # GIVEN
        user_id = uuid4()
        email = "user@example.com"
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "8.8.8.8"

        # WHEN
        with patch("api.auth.logging.logger") as mock_logger:
            log_account_deletion(user_id, email, mock_request)

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["ip"] == "8.8.8.8"
