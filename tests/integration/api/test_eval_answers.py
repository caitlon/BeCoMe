"""Tests for the answer eval runner, driven through the real test application.

The chat model is a scripted one and the retriever a static one (``tests/shared``), so no
model server, embedding server or vector database is reached. Users, projects and tenant
checks are the test application's own, over in-memory SQLite. The questions are invented.
"""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import sys
import time
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import langsmith as ls
import psycopg
import pytest
from langchain_core.messages import AIMessage
from langsmith import run_helpers

from api.assistant import deps
from api.assistant.agent import tracing
from api.assistant.agent.prompt import SYSTEM_PROMPT
from api.assistant.rag.retrieval import RetrievedChunk
from api.assistant.rate_limit import get_assistant_throttle
from api.config import get_settings
from tests.integration.api.conftest import create_project, register_and_login, stored_accounts
from tests.shared.assistant_fakes import (
    DEFAULT_USAGE,
    ScriptedToolCallingModel,
    StaticDocsRetriever,
)

ROOT = Path(__file__).resolve().parents[3]

OWN_PROJECT = "Quince Harbour Tally"
OTHER_PROJECT = "Saffron Bridge Census"
ANSWER_URL = "http://runner:hunter2@127.0.0.1:9/v1"  # pragma: allowlist secret
DB_URL = "postgresql+psycopg://u:p@127.0.0.1:9/db"  # pragma: allowlist secret
# Spelled out, not read from the script, so that dropping a field there fails a test.
PROVENANCE_FIELDS = (  # noqa: SIM905
    "mode prompt_sha256 corpus_version app_version answer_model retrieval_mode "
    "retrieval_query_transform retrieval_rerank retrieval_k answer_max_tokens query_model "
    "max_tool_calls collection code_version answer_endpoint"
).split()
GOOD_ROW = json.dumps({"id": "q0", "arm": "cli", "status": "ok"})
_ENV = {
    "ASSISTANT_MODE": "workflow",
    "ASSISTANT_RATE_LIMIT_PER_HOUR": "0",
    "ASSISTANT_RETRIEVAL_K": "3",
    "ASSISTANT_LANGSMITH_ENABLED": "false",
    "ASSISTANT_ANSWER_LLM_MODEL": "test-answer-model",
    "ASSISTANT_ANSWER_LLM_BASE_URL": ANSWER_URL,
    "ASSISTANT_VECTOR_DB_URL": "",
    "REDIS_URL": "",
}


def _load():
    """Import the script by path, since `scripts/` is not a package.

    :return: The imported `eval_answers` module.
    """
    spec = importlib.util.spec_from_file_location(
        "eval_answers", ROOT / "scripts" / "assistant" / "eval_answers.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_answers"] = module
    spec.loader.exec_module(module)
    return module


ea = _load()
assert set(PROVENANCE_FIELDS) == set(ea._PROVENANCE_FIELDS), "update PROVENANCE_FIELDS"


def _reset() -> None:
    get_settings.cache_clear()
    deps.clear_caches()
    get_assistant_throttle.cache_clear()


@pytest.fixture(autouse=True)
def _runner_env(monkeypatch, tmp_path):
    """Give every test the same explicit settings; no .env file or shell value decides one."""
    monkeypatch.chdir(tmp_path)
    for name, value in _ENV.items():
        monkeypatch.setenv(name, value)
    _reset()
    yield
    _reset()


@pytest.fixture
def tracing_setting_on(monkeypatch):
    """Turn the assistant's LangSmith setting on, with a stand-in client so nothing is sent."""
    monkeypatch.setenv("ASSISTANT_LANGSMITH_ENABLED", "true")
    monkeypatch.setenv("ASSISTANT_LANGSMITH_API_KEY", "ls-key")  # pragma: allowlist secret
    monkeypatch.setattr(tracing, "_shared_client", MagicMock())
    _reset()


def _scripted(*answers: str) -> ScriptedToolCallingModel:
    return ScriptedToolCallingModel(responses=[AIMessage(content=text) for text in answers])


def _shown(model: ScriptedToolCallingModel) -> str:
    return "\n".join(message.text for call in model.seen for message in call)


def _chunk(url: str | None, words: str) -> RetrievedChunk:
    return RetrievedChunk(
        text="x",
        title="Guide",
        section="Part",
        url=url,
        layer="public",
        score=1.0,
        chunk_text=words,
    )


def _setup(client, model, chunks=()):
    """Sign two users in, give each a project, install the model and return the fixtures."""
    own_token = register_and_login(client, "runner@example.com")
    other_token = register_and_login(client, "someone-else@example.com")
    own = create_project(client, own_token, name=OWN_PROJECT)
    other = create_project(client, other_token, name=OTHER_PROJECT)
    account = stored_accounts(client, "runner@example.com")[0]
    overrides = client.app.dependency_overrides
    overrides[deps.get_answer_model] = lambda: model
    overrides[deps.get_docs_retriever] = lambda: StaticDocsRetriever(list(chunks))
    return {
        "user": {"id": str(account["id"]), "email": account["email"]},
        "projects": [
            {"key": "own", "id": own["id"], "name": OWN_PROJECT},
            {"key": "foreign", "id": other["id"], "name": OTHER_PROJECT},
        ],
    }


def _run(client, fixtures, questions, output, mode="workflow", versions=(None, None), **kwargs):
    kwargs.setdefault("arm", "test-arm")
    kwargs.setdefault("code_version", "code-1")
    return asyncio.run(
        ea.run_eval(
            client.app,
            questions,
            fixtures,
            settings=get_settings(),
            mode=mode,
            output=output,
            versions=versions,
            **kwargs,
        )
    )


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _argv(tmp_path: Path, mode: str = "workflow", *extra: str) -> list[str]:
    return [
        *("--questions", str(tmp_path / "q.jsonl"), "--fixtures", str(tmp_path / "f.json")),
        *("--mode", mode, "--arm", "cli", "--output", str(tmp_path / "out.jsonl"), *extra),
    ]


class TestRunEval:
    """One single-turn chat per question, as the fixtures user, through the real route."""

    def test_one_row_per_question_with_every_field(self, assistant_settings, client, tmp_path):
        """
        GIVEN two invented questions and a scripted model that answers each
        WHEN the runner asks them
        THEN each gets a row with the listed fields, no credentials, and the product prompt hash
        """
        # GIVEN
        chunks = [_chunk("https://example.test/g", "First."), _chunk(None, "Second.")]
        fixtures = _setup(client, _scripted("It combines two.", "Zadne."), chunks)
        questions = [
            {"id": "q1", "question": "What does BeCoMe combine?", "lang": "en"},
            {"id": "q2", "question": "Co kombinuje BeCoMe?", "lang": "cs"},
        ]
        output = tmp_path / "out.jsonl"

        # WHEN
        summary = _run(client, fixtures, questions, output, versions=("v1", "c2"))

        # THEN
        first = _rows(output)[0]
        assert [row["id"] for row in _rows(output)] == ["q1", "q2"]
        assert (first["status"], first["answer"]) == ("ok", "It combines two.")
        assert first["question"] == "What does BeCoMe combine?"
        assert (first["lang"], first["project"], first["tool_calls"]) == ("en", None, [])
        assert set(first["checks"]) == {"citations_valid", "numbers_grounded", "ungrounded_numbers"}
        assert [(s["n"], s["has_url"]) for s in first["sources"]] == [(1, True), (2, False)]
        assert set(first["sources"][0]) == {"n", "title", "section", "layer", "has_url"}
        assert isinstance(first["latency_s"], float)
        assert first["usage"] == {**DEFAULT_USAGE, "llm_calls": 1, "complete": True}
        assert (first["arm"], first["mode"]) == ("test-arm", "workflow")
        assert first["answer_model"] == "test-answer-model"
        assert first["answer_endpoint"] == "127.0.0.1:9"
        assert (first["retrieval_k"], first["app_version"], first["corpus_version"]) == (
            3,
            "v1",
            "c2",
        )
        assert first["timestamp"].endswith("+00:00")
        settings = get_settings()
        assert first["answer_max_tokens"] == settings.assistant_answer_max_tokens
        assert first["query_model"] == settings.assistant_llm_model
        assert first["max_tool_calls"] == settings.assistant_max_tool_calls
        assert first["collection"] == settings.assistant_collection
        assert first["code_version"] == "code-1"
        assert first["prompt_sha256"] == hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
        assert first["prompt_sha256"] == ea.PROMPT_SHA256
        assert "hunter2" not in output.read_text(encoding="utf-8")
        assert (summary["rows"], summary["ok"], summary["failed"]) == (2, 2, 0)
        assert summary["median_latency_s"] is not None

    def test_a_project_question_resolves_the_fixture_key(
        self, assistant_settings, client, tmp_path
    ):
        """
        GIVEN a question that names the project key "own"
        WHEN the runner asks it
        THEN the project the key stands for is read ahead of the model, and the row names the key
        """
        # GIVEN
        model = _scripted("It has no result yet.")
        fixtures = _setup(client, model)
        questions = [{"id": "q1", "question": "What is the result?", "project": "own"}]
        output = tmp_path / "out.jsonl"

        # WHEN
        _run(client, fixtures, questions, output)

        # THEN
        row = _rows(output)[0]
        assert (row["status"], row["project"]) == ("ok", "own")
        assert OWN_PROJECT in _shown(model)

    def test_failing_turns_become_rows_and_the_run_goes_on(
        self, assistant_settings, client, tmp_path
    ):
        """
        GIVEN a question about another user's project, a plain one, and a model with one answer
        WHEN the runner asks three questions
        THEN the tenant check's 404 and the model's exception are rows, and the plain one is ok
        """
        # GIVEN
        model = _scripted("Plain answer.")
        fixtures = _setup(client, model)
        questions = [
            {"id": "q1", "question": "What is the result?", "project": "foreign"},
            {"id": "q2", "question": "What is BeCoMe?"},
            {"id": "q3", "question": "And again?"},
        ]
        output = tmp_path / "out.jsonl"

        # WHEN
        summary = _run(client, fixtures, questions, output)

        # THEN
        first, second, third = _rows(output)
        assert (first["status"], first["answer"], first["usage"]) == ("http_404", None, None)
        assert OTHER_PROJECT not in _shown(model)
        assert second["status"] == "ok"
        assert third["status"] == "IndexError"
        assert (summary["ok"], summary["failed"]) == (1, 2)

    def test_done_rows_of_the_same_arm_are_skipped(self, assistant_settings, client, tmp_path):
        """
        GIVEN an output file that holds q2 for another arm and q1 for this arm
        WHEN the runner is run again over q1 and q2
        THEN only q2 is asked and appended, since the other arm's row does not count as done
        """
        # GIVEN
        model = _scripted("Other arm.", "First.", "Second.")
        fixtures = _setup(client, model)
        output = tmp_path / "out.jsonl"
        one, two = {"id": "q1", "question": "One?"}, {"id": "q2", "question": "Two?"}
        _run(client, fixtures, [two], output, arm="other-arm")
        _run(client, fixtures, [one], output)

        # WHEN
        summary = _run(client, fixtures, [one, two], output)

        # THEN
        assert [(row["id"], row["arm"]) for row in _rows(output)] == [
            ("q2", "other-arm"),
            ("q1", "test-arm"),
            ("q2", "test-arm"),
        ]
        assert (len(model.seen), summary["rows"]) == (3, 1)

    def test_the_mode_reaches_the_service(self, assistant_settings, client, tmp_path):
        """
        GIVEN a model that first calls a tool, and the settings saying workflow
        WHEN the runner is asked for agent mode, then for workflow mode
        THEN the tool runs in agent mode only, and the app's settings override is removed
        """
        # GIVEN
        call = AIMessage(
            content="",
            tool_calls=[{"name": "list_my_projects", "args": {}, "id": "c1", "type": "tool_call"}],
        )
        model = ScriptedToolCallingModel(responses=[call, AIMessage(content="You have two.")])
        fixtures = _setup(client, model)
        question = [{"id": "q1", "question": "Which projects are mine?"}]
        agent_out, workflow_out = tmp_path / "agent.jsonl", tmp_path / "workflow.jsonl"

        # WHEN
        _run(client, fixtures, question, agent_out, mode="agent")
        flow_model = _scripted("Tools were never offered.")
        client.app.dependency_overrides[deps.get_answer_model] = lambda: flow_model
        _run(client, fixtures, question, workflow_out, mode="workflow")

        # THEN
        assert _rows(agent_out)[0]["tool_calls"] == ["list_my_projects"]
        assert _rows(workflow_out)[0]["tool_calls"] == []
        assert get_settings not in client.app.dependency_overrides


class _SlowFirstTurn(ScriptedToolCallingModel):
    """A scripted model whose first answer takes 2.5 seconds."""

    def _generate(self, messages, *args, **kwargs):
        if not self.seen:
            time.sleep(2.5)
        return super()._generate(messages, *args, **kwargs)


class _TracingProbe(StaticDocsRetriever):
    """A retriever that records whether tracing is switched off while it searches."""

    def __init__(self):
        super().__init__([])
        self.enabled = []

    async def search(self, query):
        self.enabled.append(run_helpers.get_tracing_context().get("enabled"))
        return await super().search(query)


class TestRunScope:
    """What holds for the whole loop: the credentials and the tracing."""

    def test_each_question_gets_a_fresh_token(self, assistant_settings, client, tmp_path):
        """
        GIVEN access tokens that live two seconds and a first turn that takes longer
        WHEN the runner asks two questions
        THEN the second is still answered, since its token was minted for it
        """
        # GIVEN
        fixtures = _setup(client, _SlowFirstTurn(responses=_scripted("A.", "B.").responses))
        questions = [{"id": "q1", "question": "One?"}, {"id": "q2", "question": "Two?"}]
        output = tmp_path / "out.jsonl"

        # WHEN
        with patch("api.auth.jwt.timedelta", lambda **_: timedelta(seconds=2)):
            _run(client, fixtures, questions, output)

        # THEN
        assert [row["status"] for row in _rows(output)] == ["ok", "ok"]

    def test_tracing_is_off_while_the_documents_are_searched(
        self, assistant_settings, client, tmp_path, monkeypatch, tracing_setting_on
    ):
        """
        GIVEN LANGSMITH_TRACING=true and the assistant's tracing setting on in the environment
        WHEN the runner asks a question without trace, whose search runs before the service's
            own scope
        THEN tracing is switched off at that point
        """
        # GIVEN
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        ls.utils.get_env_var.cache_clear()
        fixtures = _setup(client, _scripted("Fine."))
        probe = _TracingProbe()
        client.app.dependency_overrides[deps.get_docs_retriever] = lambda: probe

        # WHEN
        _run(client, fixtures, [{"id": "q1", "question": "One?"}], tmp_path / "out.jsonl")
        ls.utils.get_env_var.cache_clear()

        # THEN
        assert probe.enabled == [False]

    def test_trace_switches_tracing_on_while_the_documents_are_searched(
        self, assistant_settings, client, tmp_path, monkeypatch, tracing_setting_on
    ):
        """
        GIVEN LANGSMITH_TRACING=true and the assistant's tracing setting on in the environment
        WHEN the runner asks a question with trace=True
        THEN the tracing context is enabled while the documents are searched
        """
        # GIVEN
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        ls.utils.get_env_var.cache_clear()
        fixtures = _setup(client, _scripted("Fine."))
        probe = _TracingProbe()
        client.app.dependency_overrides[deps.get_docs_retriever] = lambda: probe

        # WHEN
        _run(
            client,
            fixtures,
            [{"id": "q1", "question": "One?"}],
            tmp_path / "out.jsonl",
            trace=True,
        )
        ls.utils.get_env_var.cache_clear()

        # THEN
        assert probe.enabled == [True]

    @pytest.mark.parametrize(
        ("setting_on", "trace", "flushed"),
        [(True, True, 1), (True, False, 0), (False, True, 0), (False, False, 0)],
    )
    def test_tracing_is_flushed_once_only_when_the_run_was_traced(
        self, assistant_settings, client, tmp_path, monkeypatch, setting_on, trace, flushed
    ):
        """
        GIVEN the assistant's tracing setting on or off
        WHEN the runner finishes a question with or without trace
        THEN the pending traces are flushed once if both are on, and never otherwise
        """
        # GIVEN
        if setting_on:
            monkeypatch.setenv("ASSISTANT_LANGSMITH_ENABLED", "true")
            monkeypatch.setenv("ASSISTANT_LANGSMITH_API_KEY", "ls-key")  # pragma: allowlist secret
            monkeypatch.setattr(tracing, "_shared_client", MagicMock())
            _reset()
        calls = []
        monkeypatch.setattr(ea, "shutdown_tracing", lambda: calls.append(1))
        fixtures = _setup(client, _scripted("Fine."))

        # WHEN
        _run(
            client,
            fixtures,
            [{"id": "q1", "question": "One?"}],
            tmp_path / "out.jsonl",
            trace=trace,
        )

        # THEN
        assert len(calls) == flushed

    def test_trace_with_the_setting_off_still_switches_tracing_off(
        self, assistant_settings, client, tmp_path, monkeypatch
    ):
        """
        GIVEN LANGSMITH_TRACING=true in the environment and the assistant's setting off
        WHEN the runner asks a question with trace=True
        THEN tracing is switched off around the search, since the setting is what traces
        """
        # GIVEN
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        ls.utils.get_env_var.cache_clear()
        fixtures = _setup(client, _scripted("Fine."))
        probe = _TracingProbe()
        client.app.dependency_overrides[deps.get_docs_retriever] = lambda: probe

        # WHEN
        _run(
            client,
            fixtures,
            [{"id": "q1", "question": "One?"}],
            tmp_path / "out.jsonl",
            trace=True,
        )
        ls.utils.get_env_var.cache_clear()

        # THEN
        assert probe.enabled == [False]

    def test_setting_off_without_trace_switches_tracing_off(
        self, assistant_settings, client, tmp_path, monkeypatch
    ):
        """
        GIVEN LANGSMITH_TRACING=true in the environment and the assistant's setting off
        WHEN the runner asks a question without trace
        THEN tracing is switched off around the search
        """
        # GIVEN
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        ls.utils.get_env_var.cache_clear()
        fixtures = _setup(client, _scripted("Fine."))
        probe = _TracingProbe()
        client.app.dependency_overrides[deps.get_docs_retriever] = lambda: probe

        # WHEN
        _run(client, fixtures, [{"id": "q1", "question": "One?"}], tmp_path / "out.jsonl")
        ls.utils.get_env_var.cache_clear()

        # THEN
        assert probe.enabled == [False]


class TestEvalSettings:
    """The settings the runner hands the service."""

    def test_tracing_cannot_be_enabled(self, monkeypatch):
        """
        GIVEN settings with LangSmith tracing switched on
        WHEN the runner builds the settings it runs under
        THEN tracing is off and the mode is the requested one
        """
        # GIVEN
        monkeypatch.setenv("ASSISTANT_LANGSMITH_ENABLED", "true")
        monkeypatch.setenv("ASSISTANT_LANGSMITH_API_KEY", "ls-key")  # pragma: allowlist secret
        _reset()
        assert get_settings().assistant_langsmith_enabled is True

        # WHEN
        settings = ea._eval_settings(get_settings(), "hybrid", False)

        # THEN
        assert settings.assistant_langsmith_enabled is False
        assert settings.assistant_mode == "hybrid"

    def test_trace_keeps_the_environments_tracing_setting(self, monkeypatch):
        """
        GIVEN settings with LangSmith tracing switched on by the environment
        WHEN the runner builds the settings it runs under with trace
        THEN tracing stays as the environment gave it and the mode is the requested one
        """
        # GIVEN
        monkeypatch.setenv("ASSISTANT_LANGSMITH_ENABLED", "true")
        monkeypatch.setenv("ASSISTANT_LANGSMITH_API_KEY", "ls-key")  # pragma: allowlist secret
        _reset()

        # WHEN
        traced = ea._eval_settings(get_settings(), "agent", True)

        # THEN
        assert traced.assistant_langsmith_enabled is True
        assert traced.assistant_mode == "agent"


class TestInputs:
    """Reading the questions before any turn runs."""

    def test_an_unknown_project_key_is_refused_without_the_question_text(self, tmp_path):
        """
        GIVEN a questions file whose second record names a project key the fixtures lack
        WHEN it is loaded
        THEN loading fails, naming the key and not the question
        """
        # GIVEN
        path = tmp_path / "q.jsonl"
        records = [{"id": "q1", "question": "A?"}, {"id": "q2", "question": "B?", "project": "x"}]
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

        # WHEN / THEN
        with pytest.raises(ValueError, match="'x'") as raised:
            ea._load_questions(path, {"own"})
        assert "B?" not in str(raised.value)


class TestCollectionVersions:
    """The collection's versions, read from the registry when it can be reached."""

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return None

        def execute(self, *_args):
            return SimpleNamespace(fetchone=lambda: ("app-1", "corpus-2"))

    def test_versions_come_from_the_registry_or_are_none(self, monkeypatch):
        """
        GIVEN no vector database URL, then one nothing answers on, then one with a registry row
        WHEN the versions are asked for
        THEN the first two give (None, None), and the last the row, read with the psycopg DSN
        """
        # WHEN
        with patch.object(psycopg, "connect") as connect:
            unset = ea._collection_versions(get_settings())
        monkeypatch.setenv("ASSISTANT_VECTOR_DB_URL", DB_URL)
        _reset()
        with patch.object(psycopg, "connect", side_effect=psycopg.OperationalError("down")):
            down = ea._collection_versions(get_settings())
        with patch.object(psycopg, "connect", return_value=self._Connection()) as connected:
            found = ea._collection_versions(get_settings())

        # THEN
        assert (unset, down, found) == ((None, None), (None, None), ("app-1", "corpus-2"))
        connect.assert_not_called()
        assert connected.call_args.args[0] == DB_URL.replace("+psycopg", "")


class TestMain:
    """The command line, end to end over the test application."""

    def test_main_writes_the_rows_and_prints_only_counts(
        self, assistant_settings, client, tmp_path, capsys
    ):
        """
        GIVEN a questions file, a fixtures file and an app that serves the chat
        WHEN main runs
        THEN it exits 0, appends one row, and prints counts and the median without any text
        """
        # GIVEN
        fixtures = _setup(client, _scripted("Secret-free answer."))
        (tmp_path / "f.json").write_text(json.dumps(fixtures), encoding="utf-8")
        (tmp_path / "q.jsonl").write_text(json.dumps({"id": "q1", "question": "Plum?"}))

        # WHEN
        with patch.object(ea, "create_app", return_value=client.app):
            code = ea.main(_argv(tmp_path))

        # THEN
        captured = capsys.readouterr()
        shown = captured.out
        assert code == 0
        assert [row["id"] for row in _rows(tmp_path / "out.jsonl")] == ["q1"]
        assert "rows=1 ok=1 failed=0 median_latency_s=" in shown
        assert "Plum" not in shown
        assert "Secret-free" not in shown
        assert "app_version and corpus_version are null" in captured.err
        assert _rows(tmp_path / "out.jsonl")[0]["code_version"] == ea.git_version(ea.REPO_ROOT)

    def test_main_exits_2_on_a_missing_file_or_a_switched_off_assistant(
        self, client, tmp_path, capsys
    ):
        """
        GIVEN a --questions path that does not exist, then a questions file with the assistant off
        WHEN main runs
        THEN it exits 2 each time, with a message instead of a traceback
        """
        # WHEN
        missing = ea.main(_argv(tmp_path))
        missing_message = capsys.readouterr().err
        (tmp_path / "q.jsonl").write_text(json.dumps({"id": "q1", "question": "A?"}))
        switched_off = ea.main(_argv(tmp_path, "agent"))

        # THEN
        assert (missing, switched_off) == (2, 2)
        assert "cannot read the questions" in missing_message
        assert "ASSISTANT_ENABLED" in capsys.readouterr().err


class TestSealGuard:
    """A sealed question set is refused unless a written registration comes with it."""

    DIGEST = "ab" * 32

    def _problem(self, registration: Path | None, sealed_run: bool) -> str | None:
        args = argparse.Namespace(sealed_run=sealed_run, registration=registration)
        with patch.object(ea, "SEALED_SHA256", frozenset({self.DIGEST})):
            return ea._seal_problem(self.DIGEST, args)

    def test_only_a_flag_with_a_non_empty_registration_lets_a_sealed_file_through(self, tmp_path):
        """
        GIVEN a questions file whose hash is on the sealed list
        WHEN the guard looks at runs without the flag, without a registration, with an empty or
            a missing one, and with a non-empty one, and at an ordinary file
        THEN only the last two have no problem
        """
        # GIVEN
        empty, filled = tmp_path / "empty.md", tmp_path / "registration.md"
        empty.write_text("", encoding="utf-8")
        filled.write_text("Pre-registered: arms, metrics, rules.\n", encoding="utf-8")

        # WHEN
        refusals = [
            self._problem(None, False),
            self._problem(None, True),
            self._problem(empty, True),
            self._problem(tmp_path / "none.md", True),
        ]
        sealed = self._problem(filled, True)
        ordinary = ea._seal_problem("cd" * 32, argparse.Namespace(sealed_run=False))

        # THEN
        assert all(refusals)
        assert "--sealed-run" in refusals[0]
        assert "--registration" in refusals[1]
        assert sealed is None
        assert ordinary is None

    def test_main_exits_2_before_doing_anything_on_a_sealed_file(self, tmp_path, capsys):
        """
        GIVEN a questions file whose hash is on the sealed list
        WHEN main runs without --sealed-run
        THEN it exits 2 with a message, and creates no output file
        """
        # GIVEN
        questions = tmp_path / "q.jsonl"
        questions.write_text(json.dumps({"id": "q1", "question": "A?"}) + "\n", encoding="utf-8")
        digest = hashlib.sha256(questions.read_bytes()).hexdigest()

        # WHEN
        with patch.object(ea, "SEALED_SHA256", frozenset({digest})):
            code = ea.main(_argv(tmp_path))

        # THEN
        assert code == 2
        assert "sealed" in capsys.readouterr().err
        assert not (tmp_path / "out.jsonl").exists()


class _RaisingRetriever:
    """A retriever whose search fails, as a document store that is down does."""

    async def search(self, query):
        raise RuntimeError("store down")


class _FlakyRetriever(StaticDocsRetriever):
    """A retriever whose searches fail or succeed in the given order."""

    def __init__(self, outcomes: list[bool]):
        super().__init__([])
        self._outcomes = iter(outcomes)

    async def search(self, query):
        if not next(self._outcomes):
            raise RuntimeError("store down")
        return await super().search(query)


class TestFailureHandling:
    """What a failed turn counts as, and when a failing environment stops the run."""

    def test_latest_rows_keeps_the_last_row_per_id_and_arm(self, tmp_path):
        """
        GIVEN an output file where q1 of arm a failed and was asked again, and q1 of arm b is ok
        WHEN the winning rows are read, and when the file does not exist
        THEN the later row wins per (id, arm), and a missing file gives nothing
        """
        # GIVEN
        path = tmp_path / "out.jsonl"
        rows = [
            {"id": "q1", "arm": "a", "status": "RuntimeError"},
            {"id": "q1", "arm": "b", "status": "ok"},
            {"id": "q1", "arm": "a", "status": "ok"},
        ]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

        # WHEN
        latest = ea.latest_rows(path)

        # THEN
        assert {key: row["status"] for key, row in latest.items()} == {
            ("q1", "a"): "ok",
            ("q1", "b"): "ok",
        }
        assert ea.latest_rows(tmp_path / "none.jsonl") == {}

    def test_a_failed_row_is_done_unless_retry_failed_asks_it_again(
        self, assistant_settings, client, tmp_path
    ):
        """
        GIVEN a question whose first turn failed
        WHEN the runner runs again, then runs with retry_failed and a working retriever
        THEN the plain rerun asks nothing, and the retry appends a row that wins
        """
        # GIVEN
        model = _scripted("Now it works.")
        fixtures = _setup(client, model)
        client.app.dependency_overrides[deps.get_docs_retriever] = _RaisingRetriever
        output = tmp_path / "out.jsonl"
        question = [{"id": "q1", "question": "One?"}]
        _run(client, fixtures, question, output)
        client.app.dependency_overrides[deps.get_docs_retriever] = lambda: StaticDocsRetriever([])

        # WHEN
        plain = _run(client, fixtures, question, output)
        retried = _run(client, fixtures, question, output, retry_failed=True)

        # THEN
        assert (plain["rows"], retried["rows"]) == (0, 1)
        assert [row["status"] for row in _rows(output)] == ["RuntimeError", "ok"]
        assert ea.latest_rows(output)[("q1", "test-arm")]["status"] == "ok"

    def test_three_failures_in_a_row_stop_the_run_with_exit_3(
        self, assistant_settings, client, tmp_path, capsys
    ):
        """
        GIVEN 25 questions and a retriever that raises
        WHEN main runs, then again with a working retriever, then with --retry-failed
        THEN the first stops after 3 rows with exit 3, the second asks the other 22, and the
            third asks exactly the 3 failed, so every question ends ok
        """
        # GIVEN
        model = _scripted(*["Answer."] * 25)
        fixtures = _setup(client, model)
        (tmp_path / "f.json").write_text(json.dumps(fixtures), encoding="utf-8")
        records = [{"id": f"q{i:02}", "question": "Why?"} for i in range(25)]
        (tmp_path / "q.jsonl").write_text("\n".join(map(json.dumps, records)), encoding="utf-8")
        output = tmp_path / "out.jsonl"
        working = StaticDocsRetriever([])

        # WHEN
        client.app.dependency_overrides[deps.get_docs_retriever] = _RaisingRetriever
        with patch.object(ea, "create_app", return_value=client.app):
            stopped = ea.main(_argv(tmp_path))
            message = capsys.readouterr().err
            rows_after_stop = len(_rows(output))
            client.app.dependency_overrides[deps.get_docs_retriever] = lambda: working
            second = ea.main(_argv(tmp_path))
            asked_by_second = len(model.seen)
            second_out = capsys.readouterr().out
            third = ea.main(_argv(tmp_path, "workflow", "--retry-failed"))
            third_out = capsys.readouterr().out

        # THEN
        assert (stopped, rows_after_stop) == (3, 3)
        assert "RuntimeError" in message
        assert "--retry-failed" in message
        assert (second, asked_by_second) == (0, 22)
        assert "unresolved=3" in second_out
        assert "unresolved=0" in third_out
        assert (third, len(model.seen)) == (0, 25)
        latest = ea.latest_rows(output)
        assert len(latest) == 25
        assert {row["status"] for row in latest.values()} == {"ok"}

    def test_an_ok_turn_resets_the_failure_streak(self, assistant_settings, client, tmp_path):
        """
        GIVEN five questions whose turns fail, succeed, fail, succeed, fail
        WHEN the runner runs
        THEN no streak reaches 3, so all five are asked and the run does not stop
        """
        # GIVEN
        fixtures = _setup(client, _scripted("A.", "B."))
        flaky = _FlakyRetriever([False, True, False, True, False])
        client.app.dependency_overrides[deps.get_docs_retriever] = lambda: flaky
        questions = [{"id": f"q{i}", "question": "Why?"} for i in range(5)]

        # WHEN
        summary = _run(client, fixtures, questions, tmp_path / "out.jsonl")

        # THEN
        assert (summary["rows"], summary["ok"], summary["stop"]) == (5, 2, None)

    def test_a_refused_user_stops_the_run_at_the_first_turn(
        self, assistant_settings, client, tmp_path
    ):
        """
        GIVEN a fixtures user the database does not know, and five questions
        WHEN the runner runs
        THEN it stops after one row at http_401, and says so
        """
        # GIVEN
        fixtures = _setup(client, _scripted("Never used."))
        fixtures["user"]["id"] = str(uuid4())
        questions = [{"id": f"q{i}", "question": "Why?"} for i in range(5)]

        # WHEN
        summary = _run(client, fixtures, questions, tmp_path / "out.jsonl")

        # THEN
        assert summary["rows"] == 1
        assert "http_401" in summary["stop"]

    def test_unresolved_counts_only_the_current_arm(self, assistant_settings, client, tmp_path):
        """
        GIVEN an output file whose latest row of another arm failed
        WHEN this arm runs one question to ok
        THEN the summary counts no unresolved pair, since the other arm's failure is not its own
        """
        # GIVEN
        fixtures = _setup(client, _scripted("One."))
        output = tmp_path / "out.jsonl"
        output.write_text(
            json.dumps({"id": "q9", "arm": "other-arm", "status": "RuntimeError"}) + "\n",
            encoding="utf-8",
        )

        # WHEN
        summary = _run(client, fixtures, [{"id": "q1", "question": "One?"}], output)

        # THEN
        assert (summary["ok"], summary["unresolved"]) == (1, 0)

    def test_the_stop_rule(self):
        """
        GIVEN turn statuses and the length of the failing streak
        WHEN the rule is asked
        THEN an ok turn and a short streak go on, a 429 stops and names the setting to change
        """
        assert ea._stop_reason("ok", 0) is None
        assert ea._stop_reason("RuntimeError", 2) is None
        assert "ASSISTANT_RATE_LIMIT_PER_HOUR" in ea._stop_reason("http_429", 1)
        assert "wait a minute" not in ea._stop_reason("http_429", 1)
        assert "3 turns in a row" in ea._stop_reason("http_503", 3)

    def test_the_streak_stop_says_when_retry_failed_is_refused(self):
        """
        GIVEN a run that stopped after 3 failed turns
        WHEN the stop message is read
        THEN it says a changed provenance field refuses --retry-failed, and names the way on
        """
        # WHEN
        message = ea._stop_reason("http_503", 3)

        # THEN
        assert "refused if a recorded provenance field changed" in message
        assert "a new --arm or a new --output asks every question again" in message


class _FakeTime:
    """A clock that only moves when the runner sleeps or a test advances it."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class TestPacing:
    """The runner keeps under the chat route's per-minute limit by waiting between questions."""

    @staticmethod
    def _questions(count: int) -> list[dict]:
        return [{"id": f"q{n}", "question": f"Question {n}?"} for n in range(count)]

    @staticmethod
    def _spy_starts(fake: _FakeTime, turn_s: float = 0.0):
        """Record the fake time each question starts at; a turn then takes ``turn_s`` of it."""
        starts: list[float] = []
        real_ask = ea._ask

        async def spy(*args, **kwargs):
            starts.append(fake.now)
            result = await real_ask(*args, **kwargs)
            fake.now += turn_s
            return result

        return starts, patch.object(ea, "_ask", spy)

    @staticmethod
    def _busiest_window(starts: list[float], window: float = 60.0) -> int:
        return max(sum(s <= start < s + window for start in starts) for s in starts)

    def test_instant_questions_wait_and_no_window_holds_more_than_the_limit_less_one(
        self, assistant_settings, client, tmp_path
    ):
        """
        GIVEN 25 questions that each answer at once and a fake clock, with the limit at 20 a minute
        WHEN the runner asks them
        THEN it waits, and no 60 s window holds more than 19 starts
        """
        # GIVEN
        fixtures = _setup(client, _scripted(*["Answer."] * 25))
        fake = _FakeTime()
        starts, spy = self._spy_starts(fake)

        # WHEN
        with spy:
            summary = _run(
                client,
                fixtures,
                self._questions(25),
                tmp_path / "out.jsonl",
                clock=fake.clock,
                sleep=fake.sleep,
            )

        # THEN
        assert summary["ok"] == 25
        assert fake.sleeps
        assert self._busiest_window(starts) == 19

    def test_turns_slower_than_the_pace_cause_no_wait(self, assistant_settings, client, tmp_path):
        """
        GIVEN 25 questions whose turns each take 4 s, more than 60 / 19 s
        WHEN the runner asks them
        THEN it never waits
        """
        # GIVEN
        fixtures = _setup(client, _scripted(*["Answer."] * 25))
        fake = _FakeTime()
        _, spy = self._spy_starts(fake, turn_s=4.0)

        # WHEN
        with spy:
            _run(
                client,
                fixtures,
                self._questions(25),
                tmp_path / "out.jsonl",
                clock=fake.clock,
                sleep=fake.sleep,
            )

        # THEN
        assert fake.sleeps == []

    def test_latency_does_not_include_the_wait(self, assistant_settings, client, tmp_path):
        """
        GIVEN a limit of 2 a minute, so the second question waits, and a wait that really takes 0.5 s
        WHEN the runner asks two questions
        THEN the wait happened and every latency_s is shorter than it
        """
        # GIVEN
        fixtures = _setup(client, _scripted("One.", "Two."))
        waited: list[float] = []

        async def really_sleep(seconds: float) -> None:
            waited.append(seconds)
            await asyncio.sleep(0.5)

        # WHEN
        with patch.object(ea.rate_limit, "LIMIT_ASSISTANT_CHAT", "2/minute"):
            _run(
                client,
                fixtures,
                self._questions(2),
                tmp_path / "out.jsonl",
                sleep=really_sleep,
            )

        # THEN
        assert len(waited) == 1
        assert all(row["latency_s"] < 0.5 for row in _rows(tmp_path / "out.jsonl"))

    def test_no_pacing_never_waits(self, assistant_settings, client, tmp_path):
        """
        GIVEN 25 instant questions
        WHEN the runner asks them with pacing off
        THEN it never waits
        """
        # GIVEN
        fixtures = _setup(client, _scripted(*["Answer."] * 25))
        fake = _FakeTime()

        # WHEN
        _run(
            client,
            fixtures,
            self._questions(25),
            tmp_path / "out.jsonl",
            pacing=False,
            clock=fake.clock,
            sleep=fake.sleep,
        )

        # THEN
        assert fake.sleeps == []

    def test_the_limit_is_read_from_the_routes_constant(self, assistant_settings, client, tmp_path):
        """
        GIVEN the route's limit constant patched to 5 a minute
        WHEN the runner asks 12 instant questions
        THEN no 60 s window holds more than 4 starts
        """
        # GIVEN
        fixtures = _setup(client, _scripted(*["Answer."] * 12))
        fake = _FakeTime()
        starts, spy = self._spy_starts(fake)

        # WHEN
        with patch.object(ea.rate_limit, "LIMIT_ASSISTANT_CHAT", "5/minute"), spy:
            _run(
                client,
                fixtures,
                self._questions(12),
                tmp_path / "out.jsonl",
                clock=fake.clock,
                sleep=fake.sleep,
            )

        # THEN
        assert self._busiest_window(starts) == 4

    def test_a_limit_that_is_not_per_minute_refuses_the_run(
        self, assistant_settings, client, tmp_path
    ):
        """
        GIVEN the route's limit changed to a per-hour form
        WHEN the runner starts
        THEN it refuses, naming the constant, instead of pacing to a wrong number
        """
        # GIVEN
        fixtures = _setup(client, _scripted("One."))

        # WHEN / THEN
        with (
            patch.object(ea.rate_limit, "LIMIT_ASSISTANT_CHAT", "100/hour"),
            pytest.raises(ea.RunRefusedError, match="LIMIT_ASSISTANT_CHAT"),
        ):
            _run(client, fixtures, self._questions(1), tmp_path / "out.jsonl")

    def test_main_says_the_pacing_in_effect_and_no_pacing_switches_it_off(
        self, assistant_settings, client, tmp_path, capsys
    ):
        """
        GIVEN a one-question run
        WHEN main runs with and without --no-pacing
        THEN stderr names the pacing in effect each time
        """
        # GIVEN
        fixtures = _setup(client, _scripted("One.", "Two."))
        (tmp_path / "f.json").write_text(json.dumps(fixtures), encoding="utf-8")
        (tmp_path / "q.jsonl").write_text(json.dumps({"id": "q1", "question": "Plum?"}))

        # WHEN
        with patch.object(ea, "create_app", return_value=client.app):
            ea.main(_argv(tmp_path))
            paced = capsys.readouterr().err
            ea.main(_argv(tmp_path, "workflow", "--no-pacing", "--arm", "other"))
            unpaced = capsys.readouterr().err

        # THEN
        assert "pacing: at most 19 questions per 60 s" in paced
        assert "pacing: off" in unpaced

    @pytest.mark.parametrize(
        ("setting_on", "flag", "expected"),
        [
            (True, [], "tracing: off"),
            (True, ["--trace"], "tracing: on"),
            (False, ["--trace"], "tracing: off"),
            (False, [], "tracing: off"),
        ],
    )
    def test_main_says_whether_tracing_is_on(
        self,
        assistant_settings,
        client,
        tmp_path,
        capsys,
        monkeypatch,
        setting_on,
        flag,
        expected,
    ):
        """
        GIVEN a one-question run, with the assistant's tracing setting on or off
        WHEN main runs with or without --trace
        THEN stderr says tracing is on only when the flag is given and the setting is on, and
            notes that nothing is traced when the flag is given with the setting off
        """
        # GIVEN
        if setting_on:
            monkeypatch.setenv("ASSISTANT_LANGSMITH_ENABLED", "true")
            monkeypatch.setenv("ASSISTANT_LANGSMITH_API_KEY", "ls-key")  # pragma: allowlist secret
            monkeypatch.setattr(tracing, "_shared_client", MagicMock())
            _reset()
        fixtures = _setup(client, _scripted("One."))
        (tmp_path / "f.json").write_text(json.dumps(fixtures), encoding="utf-8")
        (tmp_path / "q.jsonl").write_text(json.dumps({"id": "q1", "question": "Plum?"}))

        # WHEN
        with patch.object(ea, "create_app", return_value=client.app):
            ea.main(_argv(tmp_path, "workflow", *flag))
        err = capsys.readouterr().err

        # THEN
        assert expected in err
        assert ("tracing: on" in err) is (expected == "tracing: on")
        note = "tracing: --trace given but ASSISTANT_LANGSMITH_ENABLED is off, nothing is traced"
        assert (note in err) is (bool(flag) and not setting_on)


class TestProvenance:
    """Rows of one arm must come from one configuration."""

    def test_a_changed_mode_or_retrieval_is_refused_and_another_arm_is_not(
        self, assistant_settings, client, tmp_path, monkeypatch
    ):
        """
        GIVEN rows of arm test-arm made in workflow mode with k=3
        WHEN the arm is run in agent mode, then with k=5, and another arm in agent mode
        THEN the first two are refused naming the field, nothing is appended, and the third runs
        """
        # GIVEN
        fixtures = _setup(client, _scripted("One.", "Other arm."))
        output = tmp_path / "out.jsonl"
        question = [{"id": "q1", "question": "One?"}]
        _run(client, fixtures, question, output)

        # WHEN
        with pytest.raises(ea.RunRefusedError, match="different mode"):
            _run(client, fixtures, question, output, mode="agent")
        monkeypatch.setenv("ASSISTANT_RETRIEVAL_K", "5")
        _reset()
        with pytest.raises(ea.RunRefusedError, match="retrieval_k"):
            _run(client, fixtures, question, output)
        other = _run(client, fixtures, question, output, mode="agent", arm="other-arm")

        # THEN
        assert len(_rows(output)) == 2
        assert other["rows"] == 1
        first = _rows(output)[0]
        assert (first["retrieval_mode"], first["retrieval_query_transform"]) == (
            "hybrid",
            "translate_en",
        )
        assert first["retrieval_rerank"] is False

    @pytest.mark.parametrize("field", PROVENANCE_FIELDS)
    def test_a_change_in_any_provenance_field_is_refused(
        self, field, assistant_settings, client, tmp_path
    ):
        """
        GIVEN a row of this arm whose one provenance field differs from the current run's
        WHEN the arm is run again
        THEN the run is refused naming that field, and nothing is appended
        """
        # GIVEN
        fixtures = _setup(client, _scripted("One."))
        output = tmp_path / "out.jsonl"
        question = [{"id": "q1", "question": "One?"}]
        _run(client, fixtures, question, output)
        row = {**_rows(output)[0], field: "changed"}
        output.write_text(json.dumps(row) + "\n", encoding="utf-8")

        # WHEN / THEN
        with pytest.raises(ea.RunRefusedError, match=field):
            _run(client, fixtures, question, output)
        assert len(_rows(output)) == 1

    def test_the_recorded_retrieval_settings_are_what_deps_builds(self, monkeypatch):
        """
        GIVEN settings with a vector database URL and a changed retrieval k
        WHEN the retriever the chat route uses is built, and the runner reads the same settings
        THEN the retrieval config the retriever holds equals the one the runner records
        """
        # GIVEN
        monkeypatch.setenv("ASSISTANT_VECTOR_DB_URL", DB_URL)
        monkeypatch.setenv("ASSISTANT_RETRIEVAL_K", "7")
        _reset()

        # WHEN
        with (
            patch.object(deps, "make_engine"),
            patch.object(deps, "open_store"),
            patch.object(deps, "make_embeddings"),
        ):
            retriever = deps.get_docs_retriever()

        # THEN
        assert retriever._config == ea._retrieval_config(get_settings())
        assert retriever._config.k == 7

    def test_main_exits_2_on_a_refused_run(self, assistant_settings, client, tmp_path, capsys):
        """
        GIVEN an output file with a row of this arm made in workflow mode
        WHEN main runs the arm in agent mode
        THEN it exits 2 and names the field
        """
        # GIVEN
        fixtures = _setup(client, _scripted("One."))
        (tmp_path / "f.json").write_text(json.dumps(fixtures), encoding="utf-8")
        (tmp_path / "q.jsonl").write_text(json.dumps({"id": "q1", "question": "One?"}))
        with patch.object(ea, "create_app", return_value=client.app):
            ea.main(_argv(tmp_path))
            capsys.readouterr()

            # WHEN
            code = ea.main(_argv(tmp_path, "agent"))

        # THEN
        assert code == 2
        assert "different mode" in capsys.readouterr().err

    def _main_with(self, client, tmp_path, versions, *, sealed_run, code_version):
        fixtures = _setup(client, _scripted("Sealed answer."))
        (tmp_path / "f.json").write_text(json.dumps(fixtures), encoding="utf-8")
        (tmp_path / "q.jsonl").write_text(json.dumps({"id": "q1", "question": "One?"}))
        (tmp_path / "reg.md").write_text("Pre-registered.\n", encoding="utf-8")
        digest = hashlib.sha256((tmp_path / "q.jsonl").read_bytes()).hexdigest()
        sealed = frozenset({digest}) if sealed_run else ea.SEALED_SHA256
        extra = ["--sealed-run", "--registration", str(tmp_path / "reg.md")] if sealed_run else []
        with (
            patch.object(ea, "SEALED_SHA256", sealed),
            patch.object(ea, "_collection_versions", return_value=versions),
            patch.object(ea, "git_version", return_value=code_version),
            patch.object(ea, "create_app", return_value=client.app),
        ):
            return ea.main(_argv(tmp_path, "workflow", *extra))

    def _sealed_main(self, client, tmp_path, versions, code_version="1a2b3c4"):
        return self._main_with(
            client, tmp_path, versions, sealed_run=True, code_version=code_version
        )

    def _ordinary_main(self, client, tmp_path, versions, code_version="1a2b3c4-dirty"):
        return self._main_with(
            client, tmp_path, versions, sealed_run=False, code_version=code_version
        )

    @pytest.mark.parametrize(
        ("versions", "unreadable"),
        [
            ((None, None), "app_version and corpus_version"),
            (("app-1", None), "corpus_version"),
            ((None, "corpus-2"), "app_version"),
        ],
    )
    def test_a_sealed_run_missing_either_version_is_refused(
        self, versions, unreadable, assistant_settings, client, tmp_path, capsys
    ):
        """
        GIVEN a sealed questions file, a registration, and a version that could not be read
        WHEN main runs with --sealed-run
        THEN it exits 2 naming which could not be read and why that can be, and writes nothing
        """
        # WHEN
        code = self._sealed_main(client, tmp_path, versions)

        # THEN
        err = capsys.readouterr().err
        assert code == 2
        assert f"could not read {unreadable}" in err
        assert "unreachable" in err
        assert "private corpus manifest" in err
        assert "missing from the registry" not in err
        assert not (tmp_path / "out.jsonl").exists()

    @pytest.mark.parametrize("code_version", [None, "1a2b3c4-dirty", "wave-1-2-g1a2b3c4-dirty"])
    def test_a_sealed_run_needs_a_clean_checkout(
        self, code_version, assistant_settings, client, tmp_path, capsys
    ):
        """
        GIVEN a sealed run with both versions, whose code version is unknown or dirty
        WHEN main runs with --sealed-run
        THEN it exits 2 saying a clean checkout is needed, and writes nothing
        """
        # WHEN
        code = self._sealed_main(client, tmp_path, ("app-1", "corpus-2"), code_version)

        # THEN
        assert code == 2
        assert "clean checkout" in capsys.readouterr().err
        assert not (tmp_path / "out.jsonl").exists()

    def test_a_sealed_run_with_both_versions_and_a_clean_checkout_goes_ahead(
        self, assistant_settings, client, tmp_path, capsys
    ):
        """
        GIVEN a sealed questions file, a registration, both versions and a clean checkout
        WHEN main runs with --sealed-run
        THEN it exits 0 and prints no warning
        """
        # WHEN
        code = self._sealed_main(client, tmp_path, ("app-1", "corpus-2"))

        # THEN
        assert code == 0
        assert "warning:" not in capsys.readouterr().err

    @pytest.mark.parametrize(
        ("versions", "warned"),
        [
            ((None, None), "app_version and corpus_version are null"),
            (("app-1", None), "corpus_version is null"),
            ((None, "corpus-2"), "app_version is null"),
        ],
    )
    def test_an_ordinary_run_warns_when_either_version_is_null(
        self, versions, warned, assistant_settings, client, tmp_path, capsys
    ):
        """
        GIVEN a registry that lacks a version, and an ordinary run from a dirty checkout
        WHEN main runs
        THEN it goes ahead and warns on stderr naming what is null
        """
        # WHEN
        code = self._ordinary_main(client, tmp_path, versions)

        # THEN
        assert code == 0
        assert f"warning: {warned} in every row" in capsys.readouterr().err

    def test_an_ordinary_run_with_both_versions_does_not_warn(
        self, assistant_settings, client, tmp_path, capsys
    ):
        """
        GIVEN both versions, and an ordinary run from a dirty checkout
        WHEN main runs
        THEN it exits 0 and prints no warning
        """
        # WHEN
        code = self._ordinary_main(client, tmp_path, ("app-1", "corpus-2"))

        # THEN
        assert code == 0
        assert "warning:" not in capsys.readouterr().err


class TestInputErrors:
    """Bad inputs end in a one-line message, not a traceback."""

    def _main(self, client, tmp_path, questions_text, *extra):
        fixtures = _setup(client, _scripted("Fine."))
        (tmp_path / "f.json").write_text(json.dumps(fixtures), encoding="utf-8")
        (tmp_path / "q.jsonl").write_text(questions_text, encoding="utf-8")
        with patch.object(ea, "create_app", return_value=client.app):
            return ea.main(_argv(tmp_path, "workflow", *extra))

    def test_a_truncated_last_line_in_the_output_is_named(
        self, assistant_settings, client, tmp_path, capsys
    ):
        """
        GIVEN an output file whose second line was cut short by a crash
        WHEN main runs
        THEN it exits 2 naming the line number
        """
        # GIVEN
        (tmp_path / "out.jsonl").write_text(GOOD_ROW + '\n{"id": "q1", "ar')

        # WHEN
        code = self._main(client, tmp_path, json.dumps({"id": "q1", "question": "One?"}))

        # THEN
        assert code == 2
        assert "line 2 is not valid JSON" in capsys.readouterr().err

    @pytest.mark.parametrize(
        ("line", "reason"),
        [
            ("[1]", "not a JSON object"),
            ('{"x": 1}', "no id"),
            ('{"id": "q1"}', "no arm"),
            ('{"id": "q0", "arm": "other"}', "no status"),
            ('{"id": "q0", "arm": {"a": 1}, "status": "ok"}', "arm is not a string"),
            ('{"id": 7, "arm": "cli", "status": "ok"}', "id is not a string"),
        ],
    )
    def test_an_output_line_that_is_not_an_eval_row_is_named(
        self, line, reason, assistant_settings, client, tmp_path, capsys
    ):
        """
        GIVEN an output file whose second line is valid JSON but not an eval row
        WHEN main runs with --retry-failed
        THEN it exits 2 naming the line number and the condition, and not a traceback
        """
        # GIVEN
        (tmp_path / "out.jsonl").write_text(GOOD_ROW + "\n" + line + "\n")

        # WHEN
        code = self._main(
            client, tmp_path, json.dumps({"id": "q1", "question": "One?"}), "--retry-failed"
        )

        # THEN
        assert code == 2
        assert f"line 2 is not an eval row: {reason}" in capsys.readouterr().err

    def test_a_line_separator_inside_an_answer_does_not_split_the_row(
        self, assistant_settings, client, tmp_path
    ):
        """
        GIVEN an output row whose answer holds U+2028, U+2029 and U+0085 as unescaped text
        WHEN the file is read, and the arm is run again
        THEN it is one row, the rerun is not refused, and no question is asked again
        """
        # GIVEN
        fixtures = _setup(client, _scripted("One."))
        output = tmp_path / "out.jsonl"
        question = [{"id": "q1", "question": "One?"}]
        _run(client, fixtures, question, output)
        row = {**_rows(output)[0], "answer": "a\u2028b\u2029c\u0085d"}
        output.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

        # WHEN
        again = _run(client, fixtures, question, output)

        # THEN
        assert again["rows"] == 0
        assert len(ea._read_rows(output)) == 1

    def test_a_line_separator_inside_a_question_does_not_split_the_record(self, tmp_path):
        """
        GIVEN a questions file whose one question holds U+2028
        WHEN the questions are loaded
        THEN there is one record
        """
        # GIVEN
        path = tmp_path / "q.jsonl"
        record = {"id": "q1", "question": "a\u2028b"}
        path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

        # WHEN
        records = ea._load_questions(path, set())

        # THEN
        assert records == [record]

    def test_a_question_record_that_is_not_an_object_is_refused(
        self, assistant_settings, client, tmp_path, capsys
    ):
        """
        GIVEN a questions file whose first line is a JSON list
        WHEN main runs
        THEN it exits 2 saying the record is not a JSON object
        """
        # WHEN
        code = self._main(client, tmp_path, "[1, 2]\n")

        # THEN
        assert code == 2
        assert "question record 1 is not a JSON object" in capsys.readouterr().err

    def test_a_missing_output_directory_is_created(self, assistant_settings, client, tmp_path):
        """
        GIVEN an --output whose parent directories do not exist
        WHEN the runner runs
        THEN they are created and the row is written
        """
        # GIVEN
        fixtures = _setup(client, _scripted("Fine."))
        output = tmp_path / "deep" / "er" / "out.jsonl"

        # WHEN
        _run(client, fixtures, [{"id": "q1", "question": "One?"}], output)

        # THEN
        assert [row["id"] for row in _rows(output)] == ["q1"]
