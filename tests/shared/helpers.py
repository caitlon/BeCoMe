"""Shared constants and helpers used across unit and integration tests."""

import logging
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlmodel import Session

from api.auth.password import hash_password
from api.data.example_project import EXAMPLE_EXPERTS
from api.db.models import User
from api.db.utils import utc_now

# Shared test password constant to avoid coupling between helpers and tests
DEFAULT_TEST_PASSWORD = "SecurePass123!"


def auth_header(token: str) -> dict[str, str]:
    """Create authorization header from token.

    :param token: JWT access token
    :return: Headers dict with Bearer authorization
    """
    return {"Authorization": f"Bearer {token}"}


@contextmanager
def mock_datetime_offset(module_path: str, offset: timedelta):
    """Mock datetime.now() to return a time shifted by offset.

    Uses wraps=datetime to preserve classmethods like fromtimestamp() while
    overriding now(). Used to test token expiration by creating tokens "in the past".

    :param module_path: Full module path to mock (e.g., "api.auth.jwt.datetime")
    :param offset: Timedelta to subtract from current time (positive = past)

    Example:
        with mock_datetime_offset("api.auth.jwt.datetime", timedelta(hours=48)):
            token = create_access_token(user_id)  # Created 48 hours ago
    """
    with patch(module_path, wraps=datetime) as mock_dt:
        mock_dt.now.return_value = datetime.now(UTC) - offset
        yield mock_dt


def insert_demo_experts(session: Session) -> None:
    """Create the pool of demo accounts the example project's opinions belong to.

    Production gets the pool from the migration that added it. Tests build their
    schema with ``SQLModel.metadata.create_all``, which carries no data, so they call
    this instead. The rows match the migration: already verified, and holding a
    password hash whose plaintext is never kept.

    :param session: Session to insert into; this function commits.
    """
    unusable_password = hash_password(secrets.token_urlsafe(64))
    for expert in EXAMPLE_EXPERTS:
        session.add(
            User(
                id=expert.user_id,
                email=expert.email,
                hashed_password=unusable_password,
                first_name=expert.first_name,
                last_name=expert.last_name,
                email_verified_at=utc_now(),
                is_demo=True,
            )
        )
    session.commit()


@contextmanager
def captured_log_records(name: str) -> Iterator[list[logging.LogRecord]]:
    """Collect the records one logger emits, whatever the global logging state is.

    ``pytest``'s ``caplog`` captures through the root logger, and
    :func:`api.logging_config.setup_logging` sets ``propagate = False`` on the ``api``
    tree, so a record logged after any test has built an app would never reach it. This
    attaches a handler to the named logger itself instead, and pins its level so an
    earlier ``LOG_LEVEL`` cannot filter the record out before the handler sees it. Both
    the handler and the level are removed on the way out.

    :param name: Dotted logger name, e.g. ``api.security``.
    :return: The list the handler appends to, filled as records are emitted.

    Example:
        with captured_log_records("api.security") as records:
            do_something()
        assert [r.levelno for r in records] == [logging.DEBUG]
    """
    records: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger(name)
    handler = _Collector(level=logging.NOTSET)
    saved_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(saved_level)
