"""Tests for the LangSmith tracing scope, a no-op unless explicitly enabled."""

import json
from unittest.mock import MagicMock, patch

import langsmith as ls
import pytest
import requests
from langchain_core.tools import tool
from langsmith.run_helpers import get_tracing_context

from api.assistant.agent import tracing
from api.assistant.agent.tools import render_opinions
from api.assistant.views import OpinionView
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
        "LANGSMITH_TRACING_V2",
        "LANGCHAIN_TRACING",
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


def _opinion(name: str) -> OpinionView:
    return OpinionView(
        expert_name=name, lower_bound=37.0, peak=42.0, upper_bound=47.0, centroid=42.0
    )


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

        client_cls.assert_called_once()
        assert client_cls.call_args.kwargs["api_key"] == _API_KEY
        assert client_cls.call_args.kwargs["api_url"] == _ENDPOINT
        assert clients == [fake_client, fake_client]

    def test_an_error_inside_the_scope_propagates(self):
        """
        GIVEN a scope with tracing on
        WHEN the body raises
        THEN the error reaches the caller
        """
        with pytest.raises(RuntimeError, match="boom"), tracing.tracing_scope(_enabled_settings()):
            raise RuntimeError("boom")


class TestAnonymizer:
    """The shared client masks expert names in opinion blocks, wherever they sit in a run."""

    @staticmethod
    def _anonymizer():
        """Build the shared client with the library's class patched and return its anonymizer."""
        with patch.object(tracing.ls, "Client") as client_cls:
            tracing._shared_client(_enabled_settings())
        return client_cls.call_args.kwargs["anonymizer"]

    def test_masks_a_block_nested_in_lists_and_dicts(self):
        """
        GIVEN a run payload that holds an opinions block three levels down, in a list of
            messages, next to a question that names the same person
        WHEN the client's anonymizer is applied
        THEN the block's names are replaced, the question and the numbers are not
        """
        block = render_opinions([_opinion("Alice Novak"), _opinion("Bob Dvorak")])
        payload = {
            "messages": [
                [{"kwargs": {"content": "Why is Alice Novak far from the rest?"}}],
                [{"kwargs": {"content": f"Context:\n{block}"}}],
            ],
            "metadata": {"note": "plain"},
        }

        masked = self._anonymizer()(payload)

        assert (
            masked["messages"][0][0]["kwargs"]["content"] == "Why is Alice Novak far from the rest?"
        )
        content = masked["messages"][1][0]["kwargs"]["content"]
        assert "Alice" not in content
        assert "Bob" not in content
        assert "- Expert 1: lower=37.00" in content
        assert "- Expert 2: lower=37.00" in content
        assert masked["metadata"] == {"note": "plain"}

    def test_masks_a_block_deeper_than_the_librarys_default_depth(self):
        """
        GIVEN a block eleven levels down, below the depth the library searches by default
        WHEN the client's anonymizer is applied
        THEN the block's names are replaced all the same
        """
        payload: object = render_opinions([_opinion("Alice Novak")])
        for _ in range(11):
            payload = {"inner": payload}

        masked = self._anonymizer()(payload)

        assert "Alice" not in str(masked)

    def test_leaves_a_payload_without_a_block_as_it_is(self):
        """
        GIVEN a payload with no opinions block
        WHEN the client's anonymizer is applied
        THEN it comes back equal
        """
        payload = {"question": "Why?", "items": ["a", 1, None]}

        assert self._anonymizer()(payload) == payload


class _CapturingClient(ls.Client):
    """A real LangSmith client, anonymizer included, that keeps what it would send as text."""

    def __init__(self, **kwargs):
        super().__init__(auto_batch_tracing=False, **kwargs)
        self.bodies: list[str] = []

    def request_with_retries(self, method, pathname, **kwargs):
        data = (kwargs.get("request_kwargs") or {}).get("data")
        if data is not None:
            self.bodies.append(data.decode() if isinstance(data, bytes) else str(data))
        return requests.Response()


class TestErrorsAreMasked:
    """A name in the message of an exception that ends a run does not reach LangSmith."""

    def test_a_tool_that_raises_an_opinions_block_sends_no_name(self):
        """
        GIVEN the real anonymizing client and a tool that raises a ValueError whose message
            is a rendered opinions block, which LangChain stores in the run as repr(exc)
        WHEN the tool is invoked inside the tracing scope and the error is raised
        THEN the run was sent with an error, and nothing sent, the error included, holds a
            name, while the placeholders and the numbers are there
        """
        block = render_opinions([_opinion("Alice Novak"), _opinion("Bob Dvorak")])

        @tool
        def failing_tool() -> str:
            """Fail with the opinions of a project."""
            raise ValueError(block)

        captured: list[_CapturingClient] = []

        def build(**kwargs):
            captured.append(_CapturingClient(**kwargs))
            return captured[-1]

        with patch.object(tracing.ls, "Client", build):
            with (
                pytest.raises(ValueError, match="Number of opinions"),
                tracing.tracing_scope(_enabled_settings()),
            ):
                failing_tool.invoke({})
            tracing.shutdown_tracing()

        (client,) = captured
        runs = [json.loads(body) for body in client.bodies]
        errors = [run["error"] for run in runs if run.get("error")]
        assert errors
        payload = "\n".join(client.bodies)
        for name in ("Alice", "Novak", "Bob", "Dvorak"):
            assert name not in payload
        assert "Expert 1" in "\n".join(errors)
        assert "37.00" in payload


class TestTurnRun:
    """The root run of a turn exists only with tracing on, and is closed once."""

    def test_no_run_is_opened_with_tracing_off(self):
        """
        GIVEN tracing switched off in the settings
        WHEN a turn is started
        THEN there is no run and no client was built
        """
        with patch.object(tracing.ls, "Client") as client_cls:
            run = tracing.start_turn(_settings(), "question")

        assert run is None
        client_cls.assert_not_called()

    def test_the_run_is_posted_with_the_question_in_the_configured_project(self):
        """
        GIVEN tracing switched on for a project
        WHEN a turn is started
        THEN the shared client was asked to create a root run named assistant_turn with the
            question as input, in that project
        """
        client = MagicMock()
        with patch.object(tracing.ls, "Client", return_value=client):
            run = tracing.start_turn(_enabled_settings(assistant_langsmith_project="p"), "why?")

        assert run is not None
        (call,) = client.create_run.call_args_list
        assert call.kwargs["name"] == "assistant_turn"
        assert call.kwargs["inputs"] == {"question": "why?"}
        assert call.kwargs["session_name"] == "p"
        assert "parent_run_id" not in call.kwargs

    def test_a_run_is_closed_once(self):
        """
        GIVEN a started turn that was closed with an answer
        WHEN it is closed again with an error
        THEN it was patched once and kept the answer
        """
        client = MagicMock()
        with patch.object(tracing.ls, "Client", return_value=client):
            run = tracing.start_turn(_enabled_settings(), "q")
            tracing.end_turn(run, outputs={"answer": "a"})
            tracing.end_turn(run, error="Late")

        assert run.outputs == {"answer": "a"}
        assert run.error is None
        client.update_run.assert_called_once()

    def test_closing_no_run_does_nothing(self):
        """
        GIVEN a turn with tracing off, so no run
        WHEN it is closed
        THEN nothing happens
        """
        tracing.end_turn(None, error="Boom")


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
