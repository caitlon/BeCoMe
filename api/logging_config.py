"""Centralized logging configuration for the API."""

import json
import logging
from logging.handlers import RotatingFileHandler

from api.config import Environment, Settings

# Rotating file handler sizing, used only when LOG_FILE is configured.
_LOG_FILE_MAX_BYTES = 10 * 1024 * 1024
_LOG_FILE_BACKUP_COUNT = 3

_TEXT_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
_DEBUG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s (%(filename)s:%(lineno)d)"

# Built-in LogRecord attributes; anything else on a record came from ``extra``.
_RESERVED_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
    }
)


class JsonLogFormatter(logging.Formatter):
    """Render log records as single-line JSON objects.

    The standard :class:`logging.Formatter` only emits the fields named in its
    format string, so values passed via ``extra={...}`` are dropped. This
    formatter serialises the core record fields plus every custom attribute, so
    structured context (``request_id``, ``status_code``, ...) survives into the
    log stream and stays queryable in the aggregator.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Serialise a record to a JSON string.

        :param record: Log record to format.
        :return: Single-line JSON document.
        """
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _build_formatter(settings: Settings) -> logging.Formatter:
    """Choose a log formatter for the active environment profile.

    Development keeps human-readable text; every other profile emits JSON so the
    Railway log drain can index ``extra`` fields.

    :param settings: Application settings.
    :return: Formatter matching the profile.
    """
    if settings.environment is Environment.DEV:
        return logging.Formatter(_DEBUG_FORMAT if settings.debug else _TEXT_FORMAT)
    return JsonLogFormatter()


def setup_logging(settings: Settings) -> None:
    """Configure the parent ``api`` logger from application settings.

    Sets the level from ``LOG_LEVEL``, attaches a console handler (and a rotating
    file handler when ``LOG_FILE`` is set), and disables propagation so uvicorn
    and SQLAlchemy logs stay separate. Child loggers such as ``api.security``
    inherit this configuration. Safe to call repeatedly: existing ``api``
    handlers are cleared first, so reloads and tests do not stack duplicates.

    :param settings: Application settings.
    """
    logger = logging.getLogger("api")
    logger.setLevel(settings.log_level.upper())
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    formatter = _build_formatter(settings)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if settings.log_file:
        file_handler = RotatingFileHandler(
            settings.log_file,
            maxBytes=_LOG_FILE_MAX_BYTES,
            backupCount=_LOG_FILE_BACKUP_COUNT,
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
