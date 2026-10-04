"""Tests for the LangSmith tracing scope, a no-op unless explicitly enabled."""

from unittest.mock import MagicMock, patch

import langsmith as ls
import pytest
from langsmith.run_helpers import get_tracing_context

from api.assistant.agent import tracing
from api.config import Settings

_ENDPOINT = "https://eu.api.smith.langchain.com"
_API_KEY = "lsv2_test"  # pragma: allowlist secret
_AMBIENT_TRACING_VARIABLES = ["LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"]


@pytest.fixture(autouse=True)
def _isolated_tracing(monkeypatch, tmp_path):
    """Keep every test away from the repository's .env, the shell and the shared client.

    The library reads its environment variables through a cache, so it is cleared
    before and after each test: a value set by one test must not outlive it.
    """
    monkeypatch.chdir(tmp_path)
    for name in (
        "ASSISTANT_LANGSMITH_ENABLED",
        "ASSISTANT_LANGSMITH_API_KEY",
        "ASSISTANT_LANGSMITH_ENDPOINT",
        "ASSISTANT_LANGSMITH_PROJECT",
        *_AMBIENT_TRACING_VARIABLES,
        "LANGSMITH_ENDPOINT",
        "LANGSMITH_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    tracing.shutdown_tracing()
    ls.utils.get_env_var.cache_clear()
    yield
    tracing.shutdown_tracing()
    ls.utils.get_env_var.cache_clear()


def _settings(**overrides) -> Settings:
    base = {
        "secret_key": "test-secret-key-for-ci",  # pragma: allowlist secret
        "assistant_langsmith_enabled": False,
        "assistant_langsmith_api_key": None,
        "assistant_langsmith_endpoint": _ENDPOINT,
        "assistant_langsmith_project": "become-assistant-local",
    }
    base.update(overrides)
    return Settings(**base)


def _enabled_settings(**overrides) -> Settings:
    return _settings(
        assistant_langsmith_enabled=True, assistant_langsmith_api_key=_API_KEY, **overrides
    )


class TestDisabledScope:
    """With the setting off, nothing is traced, whatever the environment says."""

    def test_builds_no_client(self):
        """
        GIVEN tracing switched off in the settings
        WHEN a scope is entered
        THEN no LangSmith client is built
        """
        with patch.object(tracing.ls, "Client") as client_cls, tracing.tracing_scope(_settings()):
            pass

        client_cls.assert_not_called()

    @pytest.mark.parametrize("variable", _AMBIENT_TRACING_VARIABLES)
    def test_traces_nothing_even_when_the_environment_switches_tracing_on(
        self, variable, monkeypatch
    ):
        """
        GIVEN the process environment carries a tracing switch set to true, and the
            setting is off
        WHEN the library is asked inside the scope whether tracing is enabled
        THEN it says no, though it says yes outside the scope
        """
        monkeypatch.setenv(variable, "true")
        ls.utils.get_env_var.cache_clear()
        assert ls.utils.tracing_is_enabled() is True

        with tracing.tracing_scope(_settings()):
            inside = ls.utils.tracing_is_enabled()

        assert inside is False
        assert ls.utils.tracing_is_enabled() is True

    def test_an_error_inside_the_scope_propagates(self):
        """
        GIVEN a scope with tracing off
        WHEN the body raises
        THEN the error reaches the caller
        """
        with pytest.raises(RuntimeError, match="boom"), tracing.tracing_scope(_settings()):
            raise RuntimeError("boom")


class TestEnabledScope:
    """With the setting on, tracing runs against the configured endpoint and project."""

    def test_turns_tracing_on_inside_the_scope_only(self):
        """
        GIVEN tracing switched on with a key
        WHEN the library is asked whether tracing is enabled, inside and outside the scope
        THEN it says yes inside and no outside
        """
        with tracing.tracing_scope(_enabled_settings()):
            inside = ls.utils.tracing_is_enabled()

        assert inside is True
        assert ls.utils.tracing_is_enabled() is False

    def test_uses_the_settings_and_not_the_ambient_environment(self, monkeypatch):
        """
        GIVEN an environment that names another LangSmith endpoint and key
        WHEN a scope is entered with tracing on
        THEN the client in the tracing context carries the endpoint and key of the
            settings, and the project is the configured one
        """
        monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://ambient.example")
        monkeypatch.setenv("LANGSMITH_API_KEY", "ambient-key")
        ls.utils.get_env_var.cache_clear()

        with tracing.tracing_scope(_enabled_settings(assistant_langsmith_project="local-proj")):
            context = get_tracing_context()

        assert context["client"].api_url == _ENDPOINT
        assert context["client"].api_key == _API_KEY
        assert context["project_name"] == "local-proj"

    def test_builds_one_client_for_the_whole_process(self):
        """
        GIVEN tracing switched on
        WHEN two scopes are entered one after the other
        THEN one client was built and both scopes used it
        """
        fake_client = MagicMock()
        clients = []
        with patch.object(tracing.ls, "Client", return_value=fake_client) as client_cls:
            for _ in range(2):
                with tracing.tracing_scope(_enabled_settings()):
                    clients.append(get_tracing_context()["client"])

        client_cls.assert_called_once_with(api_key=_API_KEY, api_url=_ENDPOINT)
        assert clients == [fake_client, fake_client]

    def test_an_error_inside_the_scope_propagates(self):
        """
        GIVEN a scope with tracing on
        WHEN the body raises
        THEN the error reaches the caller
        """
        with pytest.raises(RuntimeError, match="boom"), tracing.tracing_scope(_enabled_settings()):
            raise RuntimeError("boom")


class TestShutdownTracing:
    """The application flushes the shared client on the way down."""

    def test_flushes_and_drops_the_shared_client(self):
        """
        GIVEN a scope that built the shared client
        WHEN tracing is shut down and a new scope is entered
        THEN the first client was flushed once, and the new scope built a second client
        """
        first, second = MagicMock(), MagicMock()
        with patch.object(tracing.ls, "Client", side_effect=[first, second]) as client_cls:
            with tracing.tracing_scope(_enabled_settings()):
                pass

            tracing.shutdown_tracing()

            first.cleanup.assert_called_once()
            with tracing.tracing_scope(_enabled_settings()):
                assert get_tracing_context()["client"] is second

        assert client_cls.call_count == 2

    def test_does_nothing_when_no_client_was_built(self):
        """
        GIVEN a process that never traced
        WHEN tracing is shut down, twice
        THEN nothing is built and nothing fails
        """
        with patch.object(tracing.ls, "Client") as client_cls:
            tracing.shutdown_tracing()
            tracing.shutdown_tracing()

        client_cls.assert_not_called()

    def test_flushes_a_client_only_once(self):
        """
        GIVEN a scope that built the shared client
        WHEN tracing is shut down twice
        THEN the client was flushed once
        """
        client = MagicMock()
        with patch.object(tracing.ls, "Client", return_value=client):
            with tracing.tracing_scope(_enabled_settings()):
                pass

            tracing.shutdown_tracing()
            tracing.shutdown_tracing()

        client.cleanup.assert_called_once()
