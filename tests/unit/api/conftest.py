"""Shared constants and helpers for API unit tests."""

import os

# The suite never inherits a developer's local switch from .env or the shell; a test
# that needs the assistant on sets it explicitly with monkeypatch.
os.environ["ASSISTANT_ENABLED"] = "false"

from tests.shared.helpers import (  # noqa: F401
    DEFAULT_TEST_PASSWORD,
    auth_header,
    mock_datetime_offset,
)
