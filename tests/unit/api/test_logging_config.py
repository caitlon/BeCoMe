"""Tests for centralized logging configuration."""

import json
import logging
from logging.handlers import RotatingFileHandler

from api.config import Environment, Settings
from api.logging_config import JsonLogFormatter, setup_logging
from api.logging_context import ContextFilter


def _settings(
    environment=Environment.DEV,
    log_level="INFO",
    log_file=None,
    debug=False,
    betterstack_source_token=None,
    betterstack_ingesting_host=None,
):
    """Build a Settings instance valid across all environment profiles."""
    return Settings(
        environment=environment,
        log_level=log_level,
        log_file=log_file,
        debug=debug,
        betterstack_source_token=betterstack_source_token,
        betterstack_ingesting_host=betterstack_ingesting_host,
        secret_key="a-sufficiently-strong-secret-value-for-tests",
        database_url="postgresql://user:pass@host:5432/db",
    )


def _make_record(name="api.test", level=logging.INFO, msg="hello", args=(), exc_info=None):
    """Build a minimal LogRecord for formatter tests."""
    return logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )


class TestJsonLogFormatter:
    """Tests for the JSON log formatter."""

    def test_formats_record_as_valid_json(self):
        """
        GIVEN a basic log record
        WHEN JsonLogFormatter formats it
        THEN the output parses as JSON carrying level, logger and message
        """
        # GIVEN
        formatter = JsonLogFormatter()
        record = _make_record(name="api.request", level=logging.INFO, msg="request handled")

        # WHEN
        output = formatter.format(record)

        # THEN
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "api.request"
        assert parsed["message"] == "request handled"

    def test_includes_extra_context_fields(self):
        """
        GIVEN a record carrying extra context attributes
        WHEN JsonLogFormatter formats it
        THEN those attributes appear as top-level JSON fields
        """
        # GIVEN
        formatter = JsonLogFormatter()
        record = _make_record(msg="login failed")
        record.request_id = "abc-123"
        record.event = "login_failure"

        # WHEN
        parsed = json.loads(formatter.format(record))

        # THEN
        assert parsed["request_id"] == "abc-123"
        assert parsed["event"] == "login_failure"

    def test_includes_timestamp(self):
        """
        GIVEN a basic log record
        WHEN JsonLogFormatter formats it
        THEN a non-empty timestamp field is present
        """
        # GIVEN
        formatter = JsonLogFormatter()
        record = _make_record()

        # WHEN
        parsed = json.loads(formatter.format(record))

        # THEN
        assert parsed["timestamp"]

    def test_serialises_exception_traceback(self):
        """
        GIVEN a record created from an active exception
        WHEN JsonLogFormatter formats it
        THEN the traceback is included under an exception field
        """
        # GIVEN
        formatter = JsonLogFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = _make_record(msg="unhandled", level=logging.ERROR, exc_info=sys.exc_info())

        # WHEN
        parsed = json.loads(formatter.format(record))

        # THEN
        assert "ValueError: boom" in parsed["exception"]


class TestSetupLogging:
    """Tests for setup_logging."""

    def test_configures_api_logger_with_handler(self):
        """
        GIVEN application settings
        WHEN setup_logging runs
        THEN the 'api' logger gains at least one handler
        """
        # GIVEN
        settings = _settings()

        # WHEN
        setup_logging(settings)

        # THEN
        assert logging.getLogger("api").handlers

    def test_sets_level_from_settings(self):
        """
        GIVEN settings with log_level WARNING
        WHEN setup_logging runs
        THEN the 'api' logger level is WARNING
        """
        # GIVEN
        settings = _settings(log_level="WARNING")

        # WHEN
        setup_logging(settings)

        # THEN
        assert logging.getLogger("api").level == logging.WARNING

    def test_disables_propagation(self):
        """
        GIVEN application settings
        WHEN setup_logging runs
        THEN the 'api' logger does not propagate to the root logger
        """
        # GIVEN
        settings = _settings()

        # WHEN
        setup_logging(settings)

        # THEN
        assert logging.getLogger("api").propagate is False

    def test_uses_json_formatter_outside_development(self):
        """
        GIVEN the production profile
        WHEN setup_logging runs
        THEN the stream handler uses the JSON formatter
        """
        # GIVEN
        settings = _settings(environment=Environment.PROD)

        # WHEN
        setup_logging(settings)

        # THEN
        handler = logging.getLogger("api").handlers[0]
        assert isinstance(handler.formatter, JsonLogFormatter)

    def test_uses_text_formatter_in_development(self):
        """
        GIVEN the development profile
        WHEN setup_logging runs
        THEN the stream handler uses a plain text formatter
        """
        # GIVEN
        settings = _settings(environment=Environment.DEV)

        # WHEN
        setup_logging(settings)

        # THEN
        handler = logging.getLogger("api").handlers[0]
        assert not isinstance(handler.formatter, JsonLogFormatter)

    def test_repeated_calls_do_not_stack_handlers(self):
        """
        GIVEN setup_logging has already run
        WHEN it runs again with the same settings
        THEN the handler count stays the same
        """
        # GIVEN
        settings = _settings()
        setup_logging(settings)
        first_count = len(logging.getLogger("api").handlers)

        # WHEN
        setup_logging(settings)

        # THEN
        assert len(logging.getLogger("api").handlers) == first_count

    def test_attaches_context_filter_to_handlers(self):
        """
        GIVEN application settings
        WHEN setup_logging runs
        THEN the stream handler carries a ContextFilter
        """
        # GIVEN
        settings = _settings()

        # WHEN
        setup_logging(settings)

        # THEN
        handler = logging.getLogger("api").handlers[0]
        assert any(isinstance(log_filter, ContextFilter) for log_filter in handler.filters)

    def test_adds_rotating_file_handler_when_log_file_set(self, tmp_path):
        """
        GIVEN settings with a log_file path
        WHEN setup_logging runs
        THEN a RotatingFileHandler is attached alongside the stream handler
        """
        # GIVEN
        settings = _settings(log_file=str(tmp_path / "api.log"))

        # WHEN
        setup_logging(settings)

        # THEN
        handlers = logging.getLogger("api").handlers
        assert any(isinstance(handler, RotatingFileHandler) for handler in handlers)

    def test_child_logger_inherits_level(self):
        """
        GIVEN setup_logging configured the parent 'api' logger
        WHEN the effective level of the child 'api.security' logger is read
        THEN it matches the configured parent level
        """
        # GIVEN
        settings = _settings(log_level="WARNING")

        # WHEN
        setup_logging(settings)

        # THEN
        assert logging.getLogger("api.security").getEffectiveLevel() == logging.WARNING

    def test_adds_betterstack_handler_when_configured(self):
        """
        GIVEN settings with both Better Stack fields set
        WHEN setup_logging runs
        THEN a LogtailHandler is attached to the 'api' logger
        """
        # GIVEN
        from unittest.mock import patch

        settings = _settings(
            betterstack_source_token="tok",
            betterstack_ingesting_host="s1.example.betterstackdata.com",
        )

        # WHEN
        with patch("api.logging_config.LogtailHandler") as mock_handler:
            setup_logging(settings)

        # THEN
        mock_handler.assert_called_once()
        assert mock_handler.return_value in logging.getLogger("api").handlers

    def test_normalizes_betterstack_host_with_scheme(self):
        """
        GIVEN a Better Stack host copied as a full https URL with a trailing slash
        WHEN setup_logging runs
        THEN LogtailHandler receives a single-scheme, bare host
        """
        # GIVEN
        from unittest.mock import patch

        settings = _settings(
            betterstack_source_token="tok",
            betterstack_ingesting_host="https://s1.example.betterstackdata.com/",
        )

        # WHEN
        with patch("api.logging_config.LogtailHandler") as mock_handler:
            setup_logging(settings)

        # THEN
        assert mock_handler.call_args.kwargs["host"] == "https://s1.example.betterstackdata.com"

    def test_skips_betterstack_handler_when_unconfigured(self):
        """
        GIVEN settings without Better Stack fields
        WHEN setup_logging runs
        THEN no LogtailHandler is created
        """
        # GIVEN
        from unittest.mock import patch

        settings = _settings()

        # WHEN
        with patch("api.logging_config.LogtailHandler") as mock_handler:
            setup_logging(settings)

        # THEN
        mock_handler.assert_not_called()


class TestCreateAppLogging:
    """Tests that the application factory wires logging."""

    def test_create_app_invokes_setup_logging(self):
        """
        GIVEN the application factory
        WHEN create_app runs
        THEN setup_logging is invoked once
        """
        # GIVEN
        from unittest.mock import patch

        from api.main import create_app

        # WHEN / THEN
        with patch("api.main.setup_logging") as mock_setup:
            create_app()

        mock_setup.assert_called_once()


class TestSentryInit:
    """Tests for the Sentry initialisation guard."""

    def test_initializes_when_dsn_set(self):
        """
        GIVEN settings carrying a Sentry DSN
        WHEN _init_sentry runs
        THEN sentry_sdk.init is called once
        """
        # GIVEN
        from unittest.mock import MagicMock, patch

        from api.main import _init_sentry

        settings = MagicMock()
        settings.sentry_dsn = "https://key@o0.ingest.sentry.io/1"
        settings.environment = Environment.PROD

        # WHEN / THEN
        with patch("api.main.sentry_sdk.init") as mock_init:
            _init_sentry(settings)

        mock_init.assert_called_once()

    def test_skipped_when_dsn_absent(self):
        """
        GIVEN settings without a Sentry DSN
        WHEN _init_sentry runs
        THEN sentry_sdk.init is not called
        """
        # GIVEN
        from unittest.mock import MagicMock, patch

        from api.main import _init_sentry

        settings = MagicMock()
        settings.sentry_dsn = None

        # WHEN / THEN
        with patch("api.main.sentry_sdk.init") as mock_init:
            _init_sentry(settings)

        mock_init.assert_not_called()
