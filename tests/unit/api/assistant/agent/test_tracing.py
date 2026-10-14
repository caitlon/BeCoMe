"""Tests for the LangSmith tracing scope, a no-op unless explicitly enabled."""

import json
import threading
import uuid
from unittest.mock import MagicMock, patch

import langsmith as ls
import pytest
import requests
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langsmith.run_helpers import get_tracing_context

from api.assistant.agent import tracing
from api.assistant.agent.masking import TurnRoster
from api.assistant.agent.tools import render_opinions
from api.assistant.views import OpinionView
from api.config import Settings
from tests.shared.helpers import captured_log_records

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


class _Opinion(OpinionView):
    """An opinion that carries the position the roster reads."""

    position: str


def _opinion(name: str) -> _Opinion:
    return _Opinion(
        expert_name=name,
        position="Hydrologist",
        lower_bound=37.0,
        peak=42.0,
        upper_bound=47.0,
        centroid=42.0,
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
        with patch.object(tracing, "_new_client") as client_cls, tracing.tracing_scope(_settings()):
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
        with patch.object(tracing, "_new_client", return_value=fake_client) as client_cls:
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
        with patch.object(tracing, "_new_client") as client_cls:
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


class _CapturingClient(tracing.MaskingClient):
    """A real LangSmith client, anonymizer included, that keeps what it would send as text.

    The client sends on a worker thread, so ``bodies`` waits for the worker to go idle first.
    A test can close ``gate`` to hold every request until it opens it again.

    :ivar request_threads: The name of the thread that made each request, in order.
    :ivar gate: Requests wait for it to be set.
    """

    def __init__(self, **kwargs):
        super().__init__(auto_batch_tracing=False, **kwargs)
        self._bodies: list[str] = []
        self.request_threads: list[str] = []
        self.gate = threading.Event()
        self.gate.set()

    @property
    def bodies(self) -> list[str]:
        self.wait_idle(10)
        return self._bodies

    def request_with_retries(self, method, pathname, **kwargs):
        self.gate.wait(10)
        data = (kwargs.get("request_kwargs") or {}).get("data")
        if data is not None:
            self._bodies.append(data.decode() if isinstance(data, bytes) else str(data))
            self.request_threads.append(threading.current_thread().name)
        return requests.Response()


class TestErrorsAreMasked:
    """A name in the message of an exception that ends a run does not reach LangSmith."""

    def test_a_tool_that_raises_an_opinions_block_sends_no_name(self):
        """
        GIVEN the real anonymizing client and a tool that raises a ValueError whose message
            is a rendered opinions block, which LangChain stores in the run as repr(exc)
        WHEN the tool is invoked inside a turn's tracing scope, the error is raised, and the
            turn ends with a roster that never met the two experts
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

        settings = _enabled_settings()
        with patch.object(tracing, "_new_client", build):
            turn = tracing.start_turn(settings, "q", TurnRoster())
            with (
                pytest.raises(ValueError, match="Number of opinions"),
                tracing.tracing_scope(settings, parent=turn),
            ):
                failing_tool.invoke({})
            tracing.end_turn(turn)
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
        with patch.object(tracing, "_new_client") as client_cls:
            run = tracing.start_turn(_settings(), "question", TurnRoster())

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
        with patch.object(tracing, "_new_client", return_value=client):
            run = tracing.start_turn(
                _enabled_settings(assistant_langsmith_project="p"), "why?", TurnRoster()
            )

        assert run is not None
        (call,) = client.create_run.call_args_list
        assert call.kwargs["name"] == "assistant_turn"
        assert call.kwargs["inputs"] == {"question": "why?"}
        assert call.kwargs["session_name"] == "p"
        assert "parent_run_id" not in call.kwargs

    def test_the_trace_is_held_before_its_first_run_is_posted(self):
        """
        GIVEN tracing switched on
        WHEN a turn is started
        THEN the client was told to hold the root run's trace before it was asked to create
            the run, with the turn's roster
        """
        client = MagicMock()
        roster = TurnRoster()
        with patch.object(tracing, "_new_client", return_value=client):
            run = tracing.start_turn(_enabled_settings(), "q", roster)

        calls = [call[0] for call in client.method_calls]
        assert calls.index("hold") < calls.index("create_run")
        client.hold.assert_called_once_with(str(run.trace_id), roster)

    def test_a_run_is_closed_once(self):
        """
        GIVEN a started turn that was closed with an answer
        WHEN it is closed again with an error
        THEN it was patched once and kept the answer
        """
        client = MagicMock()
        with patch.object(tracing, "_new_client", return_value=client):
            run = tracing.start_turn(_enabled_settings(), "q", TurnRoster())
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


class TestHeldTurn:
    """The runs of a turn are kept until it ends, then sent masked with the roster it gathered."""

    @pytest.fixture
    def built(self):
        """Build the shared client as a capturing one and list the clients built."""
        clients: list[_CapturingClient] = []

        def build(**kwargs):
            clients.append(_CapturingClient(**kwargs))
            return clients[-1]

        with patch.object(tracing, "_new_client", build):
            yield clients

    @staticmethod
    def _payload(client: _CapturingClient) -> str:
        return "\n".join(client.bodies)

    def test_nothing_is_sent_before_the_turn_ends_and_the_late_roster_masks_it_all(self, built):
        """
        GIVEN a turn whose question and a child run name a person, started with an empty
            roster that learns the person only afterwards
        WHEN the turn ends
        THEN nothing was sent before it ended, and what is sent then holds the label and
            the person's position as a placeholder, and neither the name, in any case, nor
            the position
        """
        settings = _enabled_settings()
        roster = TurnRoster()
        run = tracing.start_turn(settings, "What does Alice Novak think?", roster)
        with (
            tracing.tracing_scope(settings, parent=run),
            ls.trace("child", inputs={"note": "Novakovi said: Hydrologist"}) as span,
        ):
            span.end(outputs={"text": "Alice Novak agrees"})
        (client,) = built
        assert client.bodies == []

        roster.add([_opinion("Alice Novak")])
        tracing.end_turn(run, outputs={"answer": "Alice Novak, the Hydrologist, is far off"})

        payload = self._payload(client)
        assert client.bodies
        for text in ("Alice", "Novak", "Novakovi", "Hydrologist"):
            assert text not in payload
        assert "What does Expert 1 think?" in payload
        assert "[position of Expert 1]" in payload

    def test_every_kind_of_run_of_the_turn_is_held(self, built):
        """
        GIVEN a turn with a child run below its root
        WHEN the child run ends, before the turn does
        THEN neither the create nor the update of any run was sent
        """
        settings = _enabled_settings()
        run = tracing.start_turn(settings, "q", TurnRoster())
        with tracing.tracing_scope(settings, parent=run), ls.trace("child", inputs={"a": 1}):
            pass

        (client,) = built
        assert client.bodies == []
        tracing.end_turn(run, outputs={"answer": "a"})
        names = {json.loads(body).get("name") for body in client.bodies}
        assert {"assistant_turn", "child"} <= names

    def test_a_call_of_a_trace_no_turn_owns_is_dropped(self, built):
        """
        GIVEN a run made outside any turn
        WHEN it is created
        THEN nothing is sent: the client sends no call it cannot tie to a turn's roster
        """
        tracing._shared_client(_enabled_settings())
        (client,) = built

        client.create_run(
            name="outside",
            inputs={"q": "Alice Novak"},
            run_type="chain",
            id=uuid.uuid4(),
            trace_id=uuid.uuid4(),
            dotted_order="20260101T000000000000Z" + str(uuid.uuid4()),
        )

        assert client.bodies == []

    def test_a_call_with_no_trace_id_is_dropped(self, built):
        """
        GIVEN a client that holds a turn
        WHEN a call arrives with neither a trace id nor a dotted order
        THEN it is dropped, and the turn's own runs are not affected
        """
        run = tracing.start_turn(_enabled_settings(), "q", TurnRoster())
        (client,) = built

        client.update_run(run.id, outputs={"x": "Alice Novak"})
        tracing.end_turn(run, outputs={"answer": "a"})

        assert "Alice" not in "\n".join(client.bodies)
        assert json.loads(client.bodies[0])["name"] == "assistant_turn"

    def test_a_trace_id_in_another_spelling_finds_the_held_turn(self, built):
        """
        GIVEN a held turn
        WHEN a call names its trace in upper case, as text, and another has only a dotted order
        THEN both are held with the turn, and both are masked when it ends
        """
        roster = TurnRoster()
        roster.add([_opinion("Alice Novak")])
        run = tracing.start_turn(_enabled_settings(), "q", roster)
        (client,) = built
        child = uuid.uuid4()
        order = f"{run.dotted_order}.20260101T000000000000Z{child}"

        client.create_run(
            name="spelled",
            inputs={"q": "Alice Novak"},
            run_type="chain",
            id=child,
            trace_id=str(run.trace_id).upper(),
            dotted_order=order,
        )
        client.create_run(
            name="ordered",
            inputs={"q": "Alice Novak"},
            run_type="chain",
            id=uuid.uuid4(),
            dotted_order=order,
        )
        assert client.bodies == []
        tracing.end_turn(run, outputs={"answer": "a"})

        payload = "\n".join(client.bodies)
        assert "spelled" in payload
        assert "ordered" in payload
        assert "Alice" not in payload

    def test_a_run_that_ends_after_its_turn_is_masked_and_sent(self, built):
        """
        GIVEN a turn that has ended and sent its trace
        WHEN an update for one of its runs arrives afterwards
        THEN it is sent at once, masked with the turn's roster
        """
        roster = TurnRoster()
        roster.add([_opinion("Alice Novak")])
        run = tracing.start_turn(_enabled_settings(), "q", roster)
        tracing.end_turn(run, outputs={"answer": "a"})
        (client,) = built
        sent = len(client.bodies)

        client.update_run(
            run.id,
            trace_id=run.trace_id,
            dotted_order=run.dotted_order,
            outputs={"late": "Alice Novak was cut off"},
        )

        late = "\n".join(client.bodies[sent:])
        assert "late" in late
        assert "Alice" not in late
        assert "Expert 1 was cut off" in late

    def test_a_turn_is_sent_once(self, built):
        """
        GIVEN a turn that ended
        WHEN it is ended again, and its trace released again
        THEN nothing more is sent
        """
        run = tracing.start_turn(_enabled_settings(), "q", TurnRoster())
        tracing.end_turn(run, outputs={"answer": "a"})
        (client,) = built
        sent = len(client.bodies)

        tracing.end_turn(run, error="Late")
        client.release(str(run.trace_id))

        assert len(client.bodies) == sent

    def test_the_oldest_turn_past_the_bound_is_dropped_unsent_and_later_runs_are_masked(
        self, built
    ):
        """
        GIVEN a bound of one held turn and two turns started
        WHEN the first turn ends
        THEN the runs it held were dropped, and the end that arrives is masked and sent
        """
        roster = TurnRoster()
        roster.add([_opinion("Alice Novak")])
        with patch.object(tracing, "_MAX_HELD_TRACES", 1):
            first = tracing.start_turn(_enabled_settings(), "Alice Novak asks", roster)
            second = tracing.start_turn(_enabled_settings(), "other", TurnRoster())
        (client,) = built

        tracing.end_turn(first, outputs={"answer": "Alice Novak answers"})

        payload = self._payload(client)
        assert "asks" not in payload
        assert "Expert 1 answers" in payload
        assert "Alice" not in payload
        tracing.end_turn(second)

    def test_a_refused_run_does_not_stop_the_others(self, built):
        """
        GIVEN a held turn whose first run the library refuses to send
        WHEN the turn ends
        THEN the other runs are still sent and no error reaches the caller
        """
        settings = _enabled_settings()
        run = tracing.start_turn(settings, "q", TurnRoster())
        with tracing.tracing_scope(settings, parent=run), ls.trace("child", inputs={"a": 1}):
            pass
        (client,) = built
        real = ls.Client.create_run
        calls = []

        def flaky(self, *args, **kwargs):
            calls.append(kwargs.get("name"))
            if len(calls) == 1:
                raise RuntimeError("refused")
            return real(self, *args, **kwargs)

        with patch.object(ls.Client, "create_run", flaky):
            tracing.end_turn(run, outputs={"answer": "a"})
            client.wait_idle(10)

        assert calls == ["assistant_turn", "child"]
        assert "child" in self._payload(client)


class TestReleaseWorker:
    """A turn's trace is masked and sent on the client's own thread, in order."""

    @pytest.fixture
    def built(self):
        clients: list[_CapturingClient] = []

        def build(**kwargs):
            clients.append(_CapturingClient(**kwargs))
            return clients[-1]

        with patch.object(tracing, "_new_client", build):
            yield clients

    @staticmethod
    def _kinds(client: _CapturingClient) -> list[str]:
        """The sequence of calls the client sent, as create/update and the run's name."""
        names: dict[str, str] = {}
        sequence = []
        for body in client.bodies:
            run = json.loads(body)
            if run["id"] in names:
                sequence.append(f"update:{names[run['id']]}")
            else:
                names[run["id"]] = run["name"]
                sequence.append(f"create:{run['name']}")
        return sequence

    def test_ending_a_turn_returns_before_anything_is_masked_or_sent(self, built):
        """
        GIVEN a turn with a child run and a client whose requests are held shut
        WHEN the turn ends
        THEN end_turn returned with nothing sent, and once the requests are let through every
            call arrives in the order it was made, on a thread other than the caller's, masked
        """
        settings = _enabled_settings()
        roster = TurnRoster()
        roster.add([_opinion("Alice Novak")])
        run = tracing.start_turn(settings, "Alice Novak asks", roster)
        (client,) = built
        client.gate.clear()
        with tracing.tracing_scope(settings, parent=run), ls.trace("child", inputs={"a": "Alice"}):
            pass

        tracing.end_turn(run, outputs={"answer": "Alice Novak answers"})

        assert client._bodies == []
        client.gate.set()
        assert self._kinds(client) == [
            "create:assistant_turn",
            "create:child",
            "update:child",
            "update:assistant_turn",
        ]
        assert client.request_threads
        assert threading.current_thread().name not in client.request_threads
        assert set(client.request_threads) == {client.request_threads[0]}
        payload = "\n".join(client.bodies)
        assert "Alice" not in payload
        assert "Expert 1 answers" in payload

    def test_a_late_call_keeps_its_place_behind_the_release(self, built):
        """
        GIVEN a turn that ended while the client's requests were held shut
        WHEN two calls for its runs arrive afterwards
        THEN they are sent after every held call, in their own order, masked, on the worker
        """
        roster = TurnRoster()
        roster.add([_opinion("Alice Novak")])
        run = tracing.start_turn(_enabled_settings(), "q", roster)
        (client,) = built
        client.gate.clear()
        tracing.end_turn(run, outputs={"answer": "a"})

        for index in (1, 2):
            client.update_run(
                run.id,
                trace_id=run.trace_id,
                dotted_order=run.dotted_order,
                outputs={"late": f"{index} Alice Novak"},
            )
        client.gate.set()

        bodies = client.bodies
        assert len(bodies) == 4
        assert [json.loads(body).get("outputs") for body in bodies[2:]] == [
            {"late": "1 Expert 1"},
            {"late": "2 Expert 1"},
        ]
        assert threading.current_thread().name not in client.request_threads

    def test_a_call_whose_turn_left_the_released_list_is_dropped(self, built):
        """
        GIVEN a bound of one remembered turn and two turns that ended
        WHEN a call arrives for the first
        THEN it is dropped rather than sent as it is
        """
        roster = TurnRoster()
        roster.add([_opinion("Alice Novak")])
        with patch.object(tracing, "_MAX_RELEASED_TRACES", 1):
            first = tracing.start_turn(_enabled_settings(), "q", roster)
            second = tracing.start_turn(_enabled_settings(), "q", TurnRoster())
            tracing.end_turn(first)
            tracing.end_turn(second)
        (client,) = built
        sent = len(client.bodies)

        client.update_run(
            first.id,
            trace_id=first.trace_id,
            dotted_order=first.dotted_order,
            outputs={"late": "Alice Novak"},
        )

        assert len(client.bodies) == sent

    def test_a_call_that_cannot_be_masked_is_dropped_and_logged_without_its_text(self, built):
        """
        GIVEN a turn whose child run makes the mask raise an error that quotes the text
        WHEN the turn ends
        THEN the create of that run is dropped, the other calls are sent, and one record names the event and
            the exception class and carries none of the text
        """
        settings = _enabled_settings()
        run = tracing.start_turn(settings, "q", TurnRoster())
        (client,) = built
        with tracing.tracing_scope(settings, parent=run), ls.trace("bad", inputs={"a": "BOOM"}):
            pass
        real = tracing.mask_participants

        def failing(text, roster):
            if "BOOM" in text:
                raise ValueError(f"cannot read {text}")
            return real(text, roster)

        with (
            patch.object(tracing, "mask_participants", failing),
            captured_log_records("api.assistant.agent.tracing") as records,
        ):
            tracing.end_turn(run, outputs={"answer": "a"})
            client.wait_idle(10)

        names = [json.loads(body).get("name") for body in client._bodies]
        assert "BOOM" not in "".join(client._bodies)
        assert names.count("bad") == 1
        assert names.count("assistant_turn") == 2
        (record,) = [r for r in records if r.__dict__.get("event") == "assistant_trace_mask_failed"]
        assert record.__dict__["reason"] == "ValueError"
        assert "BOOM" not in record.getMessage() + str(record.__dict__)

    def test_the_shape_mask_covers_the_fields_the_librarys_anonymizer_skips(self):
        """
        GIVEN a call whose serialized, extra and events fields hold an opinions block of
            experts the roster never met
        WHEN it is masked
        THEN no name is left in any of them
        """
        block = render_opinions([_opinion("Alice Novak")])
        op = tracing._Op(
            "create",
            {
                "serialized": {"repr": block},
                "extra": {"runtime": {"note": block}},
                "events": [{"name": "x", "message": block}],
            },
        )

        masked = tracing._masked(op, TurnRoster())

        assert "Alice" not in json.dumps(masked.kwargs)
        assert "Expert 1" in json.dumps(masked.kwargs)

    def test_a_participant_named_like_the_block_layout_cannot_hide_a_strangers_row(self):
        """
        GIVEN a roster whose one expert is named lower, and a call whose outputs hold a block
            with that expert and with another the roster never met
        WHEN the call is masked
        THEN the stranger's name is gone from the block
        """
        roster = TurnRoster()
        roster.add([_opinion("lower")])
        block = render_opinions([_opinion("lower"), _opinion("Stranger Unknown")])

        masked = tracing._masked(tracing._Op("update", {"outputs": {"text": block}}), roster)

        text = json.dumps(masked.kwargs)
        assert "Stranger" not in text
        assert "Unknown" not in text

    def test_a_strangers_row_does_not_take_the_label_of_an_expert_the_roster_knows(self):
        """
        GIVEN a roster that met Bob and Alice, and a call whose outputs hold a block of
            Alice and a stranger, and the stranger's name again outside the block
        WHEN the call is masked
        THEN Alice keeps Expert 2, the stranger gets Expert 3 in the block and outside it
        """
        alice = _opinion("Alice Novak")
        roster = TurnRoster()
        roster.add([_opinion("Bob Green"), alice])
        text = render_opinions([alice, _opinion("Stranger Unknown")]) + "\nStranger spoke"

        masked = tracing._masked(tracing._Op("update", {"outputs": {"text": text}}), roster)

        out = masked.kwargs["outputs"]["text"]
        assert "- Expert 2: lower=37.00" in out
        assert "- Expert 3: lower=37.00" in out
        assert out.endswith("\nExpert 3 spoke")

    def test_a_message_object_in_a_run_is_masked_like_text(self):
        """
        GIVEN outputs that hold a LangChain message object rather than a dict
        WHEN the call is masked
        THEN the object's text is masked and it stays a structure with its content
        """
        roster = TurnRoster()
        roster.add([_opinion("Alice Novak")])
        op = tracing._Op(
            "update", {"outputs": {"output": ToolMessage(content="Alice Novak", tool_call_id="1")}}
        )

        masked = tracing._masked(op, roster)

        assert masked.kwargs["outputs"]["output"]["content"] == "Expert 1"

    def test_a_trace_id_that_is_not_a_uuid_cannot_be_held(self):
        """
        GIVEN a client
        WHEN it is asked to hold a trace whose id is not a UUID
        THEN it refuses
        """
        client = tracing.MaskingClient(api_key=_API_KEY, api_url=_ENDPOINT)

        with pytest.raises(ValueError, match="badly formed"):
            client.hold("not-a-uuid", TurnRoster())
        client.drain(1)


class TestShutdownTracing:
    """The application flushes the shared client on the way down."""

    def test_flushes_and_drops_the_shared_client(self):
        """
        GIVEN a scope that built the shared client
        WHEN tracing is shut down and a new scope is entered
        THEN the first client was flushed once, and the new scope built a second client
        """
        first, second = MagicMock(), MagicMock()
        with patch.object(tracing, "_new_client", side_effect=[first, second]) as client_cls:
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
        with patch.object(tracing, "_new_client") as client_cls:
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
        with patch.object(tracing, "_new_client", return_value=client):
            with tracing.tracing_scope(_enabled_settings()):
                pass

            tracing.shutdown_tracing()
            tracing.shutdown_tracing()

        client.cleanup.assert_called_once()

    def test_finishes_the_runs_being_masked_before_the_library_flushes(self):
        """
        GIVEN a turn that ended while the client's requests were held shut, and a second turn
            that never ended
        WHEN tracing is shut down, with the requests let through a moment later
        THEN the first turn's runs were sent before the library's cleanup ran, and the
            unfinished turn's runs were not sent at all
        """
        clients: list[_CapturingClient] = []

        def build(**kwargs):
            clients.append(_CapturingClient(**kwargs))
            return clients[-1]

        with patch.object(tracing, "_new_client", build):
            first = tracing.start_turn(_enabled_settings(), "ended", TurnRoster())
            tracing.start_turn(_enabled_settings(), "unfinished", TurnRoster())
            (client,) = clients
            client.gate.clear()
            tracing.end_turn(first, outputs={"answer": "a"})
            sent_at_cleanup: list[int] = []
            real_cleanup = client.cleanup
            client.cleanup = lambda *args, **kwargs: (
                sent_at_cleanup.append(len(client._bodies)),
                real_cleanup(*args, **kwargs),
            )
            threading.Timer(0.2, client.gate.set).start()

            tracing.shutdown_tracing()

        assert sent_at_cleanup == [2]
        assert all("unfinished" not in body for body in client._bodies)
