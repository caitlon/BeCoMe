"""Tests for the shared test environment in tests/test.env."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import _pin_environment, read_test_env

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

    def test_the_file_has_unix_line_endings(self):
        """
        GIVEN tests/test.env, sourced by a shell that would keep a carriage return in a value
        WHEN its raw bytes are read
        THEN no line ends in a carriage return
        """
        assert b"\r" not in _TEST_ENV.read_bytes()

    def test_no_variable_is_named_twice(self):
        """
        GIVEN tests/test.env, where the last of two lines for a name wins in one reader only
        WHEN the names of its assignments are counted
        THEN each name appears once
        """
        names = [
            line.partition("=")[0]
            for line in _TEST_ENV.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]

        assert len(names) == len(set(names))


class TestPinEnvironment:
    """The root conftest forces the file's values over whatever the caller has set."""

    def test_the_file_overrides_a_live_configuration(self, monkeypatch: pytest.MonkeyPatch):
        """
        GIVEN a process holding a live mail provider, a Sentry DSN and a hosted model provider
        WHEN the root conftest pins the environment
        THEN the file's values replace them, blank ones included
        """
        monkeypatch.setenv("EMAIL_PROVIDER", "http")
        monkeypatch.setenv("EMAIL_API_KEY", "re_live")
        monkeypatch.setenv("SENTRY_DSN", "https://k@o1.ingest.sentry.io/1")
        monkeypatch.setenv("ASSISTANT_LLM_PROVIDER", "api")

        _pin_environment()

        assert os.environ["EMAIL_PROVIDER"] == "console"
        assert os.environ["EMAIL_API_KEY"] == ""
        assert os.environ["SENTRY_DSN"] == ""
        assert os.environ["ASSISTANT_LLM_PROVIDER"] == "local"

    def test_the_tracing_library_variables_are_removed(self, monkeypatch: pytest.MonkeyPatch):
        """
        GIVEN the LangSmith library, which reads its key and endpoint from the process only,
            and a process that holds both
        WHEN the root conftest pins the environment
        THEN neither variable is in the process environment
        """
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_live")
        monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

        _pin_environment()

        assert "LANGSMITH_API_KEY" not in os.environ
        assert "LANGSMITH_ENDPOINT" not in os.environ

    def test_a_database_url_of_the_caller_is_kept(self, monkeypatch: pytest.MonkeyPatch):
        """
        GIVEN an E2E or DAST run that passes its own DATABASE_URL
        WHEN the root conftest pins the environment
        THEN that URL stays, because the database is a default and not a forced value
        """
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/e2e")

        _pin_environment()

        assert os.environ["DATABASE_URL"] == "postgresql://u:p@localhost:5432/e2e"

    def test_every_variable_of_the_file_wins(self, monkeypatch: pytest.MonkeyPatch):
        """
        GIVEN a process where every variable of tests/test.env holds another value
        WHEN the root conftest pins the environment
        THEN each holds the file's value again
        """
        expected = read_test_env()
        for name in expected:
            monkeypatch.setenv(name, "from-the-caller")

        _pin_environment()

        assert {name: os.environ[name] for name in expected} == expected

    def test_loading_the_conftest_pins_the_environment(self):
        """
        GIVEN a fresh interpreter with a live mail provider in its environment
        WHEN it only imports the root conftest, as pytest does before anything else
        THEN the mail provider is the console one and the migration database URL is blank
        """
        env = {**os.environ, "EMAIL_PROVIDER": "http", "MIGRATION_DATABASE_URL": "x"}
        code = (
            "import os, tests.conftest;"
            "print(os.environ['EMAIL_PROVIDER'], repr(os.environ['MIGRATION_DATABASE_URL']))"
        )

        result = subprocess.run(  # noqa: S603 - fixed argv, no shell; sys.executable is trusted
            [sys.executable, "-c", code],
            cwd=Path(__file__).parents[2],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.stdout.split() == ["console", "''"]
