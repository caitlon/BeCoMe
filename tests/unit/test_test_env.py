"""Tests for the shared test environment in tests/test.env."""

import os
import re
from pathlib import Path

from tests.conftest import read_test_env

_TEST_ENV = Path(__file__).parents[1] / "test.env"


class TestTestEnvironmentFile:
    """Three readers parse tests/test.env, and agree only on plain lines."""

    def test_every_line_is_a_plain_assignment_or_a_comment(self):
        """
        GIVEN tests/test.env, read by the root conftest, sourced by a shell and grepped in CI
        WHEN each line that is not blank or a comment is checked
        THEN it is NAME=value with no quotes, spaces, expansion or other shell syntax
        """
        lines = [
            line
            for line in _TEST_ENV.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]

        assert lines
        assert [
            line for line in lines if not re.fullmatch(r"[A-Z][A-Z0-9_]*=[A-Za-z0-9_./:-]*", line)
        ] == []

    def test_the_run_starts_from_the_file(self):
        """
        GIVEN the root conftest, loaded before this module
        WHEN the process environment is compared with tests/test.env
        THEN every variable of the file holds the file's value, blank ones included
        """
        expected = read_test_env()

        assert expected["EMAIL_PROVIDER"] == "console"
        assert {name: os.environ.get(name) for name in expected} == expected

    def test_the_tracing_library_variables_are_removed(self):
        """
        GIVEN the LangSmith library, which reads its key and endpoint from the process only
        WHEN the root conftest has run
        THEN neither variable is in the process environment
        """
        assert "LANGSMITH_API_KEY" not in os.environ
        assert "LANGSMITH_ENDPOINT" not in os.environ
