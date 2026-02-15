"""Shared constants and helpers for API unit tests."""

import os

# Set test defaults before importing api modules
os.environ.setdefault("SECRET_KEY", "test-secret-for-unit-tests")
os.environ["TESTING"] = "1"

from tests.shared.helpers import (  # noqa: F401
    DEFAULT_TEST_PASSWORD,
    auth_header,
    mock_datetime_offset,
)
