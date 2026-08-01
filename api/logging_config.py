"""Centralized logging configuration for the API."""

import json
import logging
from logging.handlers import RotatingFileHandler

from logtail import LogtailHandler  # type: ignore[import-untyped]

from api.config import Environment, Settings
from api.logging_context import ContextFilter

# Rotating file handler sizing, used only when LOG_FILE is configured.
_LOG_FILE_MAX_BYTES = 10 * 1024 * 1024
_LOG_FILE_BACKUP_COUNT = 3

_TEXT_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
_DEBUG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s (%(filename)s:%(lineno)d)"

# Third-party loggers worth keeping, and the level each is pinned at. They sit outside
# the ``api`` tree and uvicorn switches its own off propagation, so without this their
# records reach the container's stdout but never the log drain.
#
# The levels are deliberate, not inherited from LOG_LEVEL:
#   uvicorn.error      startup, shutdown, and protocol failures -- the records that
#                      explain a boot that never finished. Low volume, high value.
#   uvicorn.access     silenced: ``api.request`` already logs a richer line per request
#                      (ip, duration, correlation id). Listed so the choice is visible.
#   sqlalchemy.engine  MUST stay above DEBUG. Its INFO level prints every statement and
#                      its DEBUG level adds the bound parameters -- password hashes, raw
#                      addresses, names, reset-token hashes -- which would ship to the
#                      drain in the clear. The dev deploy runs at DEBUG, so inheriting
#                      LOG_LEVEL here would leak on a real database. Query shape and
#                      timing are logged by the read services instead.
#   httpx / botocore   the Resend and S3 calls, already covered by ``email_sent`` and
#                      ``s3_upload`` with timings; only transport failures add anything.
_EXTERNAL_LOG_LEVELS: dict[str, int] = {
    "uvicorn.error": logging.INFO,
    "uvicorn.access": logging.WARNING,
    "sqlalchemy.engine": logging.WARNING,
    "httpx": logging.WARNING,
    "botocore": logging.WARNING,
}

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

    A developer's console keeps human-readable text. Anything running as a deployed
    service emits JSON so the log drain can index the ``extra`` fields -- and that
    includes the Railway ``dev`` service, which is a deploy that happens to run the
    dev profile rather than a laptop. Keying only on the profile would ship its
    records as plain text and leave every structured field unqueryable.

    :param settings: Application settings.
    :return: Formatter matching the profile.
    """
    is_local_dev = (
        settings.environment is Environment.DEV and settings.railway_environment_name is None
    )
    if is_local_dev:
        return logging.Formatter(_DEBUG_FORMAT if settings.debug else _TEXT_FORMAT)
    return JsonLogFormatter()


def _betterstack_host(raw: str) -> str:
    """Normalise a Better Stack ingesting host into a bare hostname.

    The Better Stack dashboard shows the ingesting host as a full URL, so an
    operator may copy it verbatim. Strip any scheme and trailing slash so the
    handler URL is always well-formed rather than carrying a duplicated scheme.

    :param raw: Configured host, with or without a scheme or trailing slash.
    :return: Bare hostname.
    """
    _, _, host = raw.rpartition("://")
    return host.rstrip("/")


def _build_handlers(settings: Settings) -> list[logging.Handler]:
    """Build the handler set shared by every logger this module configures.

    Always a console handler, plus a rotating file handler when ``LOG_FILE`` is set
    and a Better Stack handler when both of its settings are present. Each carries
    a :class:`~api.logging_context.ContextFilter` so the request-scoped
    ``request_id`` and ``user_id`` reach every record.

    The handlers are built once and shared, not rebuilt per logger: that keeps the
    Better Stack handler a single HTTP client with a single buffer instead of one
    per configured logger.

    :param settings: Application settings.
    :return: Handlers to attach, console first.
    """
    context_filter = ContextFilter()
    formatter = _build_formatter(settings)
    handlers: list[logging.Handler] = []

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    handlers.append(stream_handler)

    if settings.log_file:
        file_handler = RotatingFileHandler(
            settings.log_file,
            maxBytes=_LOG_FILE_MAX_BYTES,
            backupCount=_LOG_FILE_BACKUP_COUNT,
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    if settings.betterstack_source_token and settings.betterstack_ingesting_host:
        logtail_handler = LogtailHandler(
            source_token=settings.betterstack_source_token,
            host=f"https://{_betterstack_host(settings.betterstack_ingesting_host)}",
        )
        handlers.append(logtail_handler)

    for handler in handlers:
        handler.addFilter(context_filter)
    return handlers


def _attach(logger: logging.Logger, handlers: list[logging.Handler], level: int | str) -> None:
    """Point one logger at the shared handlers at a given level.

    Existing handlers are dropped first, so calling this more than once in a
    process -- a reload, or the tests that configure logging repeatedly -- does not
    stack duplicates. Propagation is switched off because the logger already carries
    the full handler set; leaving it on would emit each record a second time through
    an ancestor.

    :param logger: Logger to configure.
    :param handlers: Shared handler set from :func:`_build_handlers`.
    :param level: Level to set on the logger.
    """
    logger.setLevel(level)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    for handler in handlers:
        logger.addHandler(handler)


def setup_logging(settings: Settings) -> None:
    """Configure the ``api`` logger tree and the third-party loggers worth keeping.

    The ``api`` logger takes its level from ``LOG_LEVEL``; every child
    (``api.request``, ``api.security``, ``api.service.*``, ...) inherits it. The
    loggers in :data:`_EXTERNAL_LOG_LEVELS` get the same handlers at their own
    pinned levels, so uvicorn's startup failures and the transport errors from
    httpx and botocore land in the drain next to the ``api.*`` records that explain
    them -- see that mapping for why each level is what it is.

    Safe to call repeatedly: every configured logger has its handlers cleared first.

    :param settings: Application settings.
    """
    handlers = _build_handlers(settings)
    _attach(logging.getLogger("api"), handlers, settings.log_level.upper())
    for name, level in _EXTERNAL_LOG_LEVELS.items():
        _attach(logging.getLogger(name), handlers, level)
