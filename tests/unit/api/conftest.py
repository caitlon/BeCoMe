"""Shared constants and helpers for API unit tests."""

import os
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

# Set test defaults before importing api modules
os.environ.setdefault("SECRET_KEY", "test-secret-for-unit-tests")
os.environ["TESTING"] = "1"

# Shared test password constant
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
