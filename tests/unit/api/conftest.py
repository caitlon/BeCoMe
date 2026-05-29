"""Shared constants and helpers for API unit tests."""

import os

# Set test defaults before importing api modules (settings are cached on first use)
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-for-unit-tests")
os.environ["TESTING"] = "1"  # Must always be set; rate limiter reads it at import time

from tests.shared.helpers import (  # noqa: F401
    DEFAULT_TEST_PASSWORD,
    auth_header,
    mock_datetime_offset,
)
