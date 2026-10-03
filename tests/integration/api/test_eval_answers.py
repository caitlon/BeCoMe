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
from unittest.mock import patch

import langsmith as ls
import psycopg
import pytest
from langchain_core.messages import AIMessage
from langsmith import run_helpers

from api.assistant import deps
from api.assistant.agent.prompt import SYSTEM_PROMPT
from api.assistant.rag.retrieval import RetrievedChunk
from api.assistant.rate_limit import get_assistant_throttle
from api.config import get_settings
from tests.integration.api.conftest import create_project, register_and_login, stored_accounts
from tests.shared.assistant_fakes import ScriptedToolCallingModel, StaticDocsRetriever

ROOT = Path(__file__).resolve().parents[3]

OWN_PROJECT = "Quince Harbour Tally"
OTHER_PROJECT = "Saffron Bridge Census"
ANSWER_URL = "http://runner:hunter2@127.0.0.1:9/v1"  # pragma: allowlist secret
DB_URL = "postgresql+psycopg://u:p@127.0.0.1:9/db"  # pragma: allowlist secret
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


def _run(client, fixtures, questions, output, mode="workflow", versions=(None, None)):
    return asyncio.run(
        ea.run_eval(
            client.app,
            questions,
            fixtures,
            settings=get_settings(),
            arm="test-arm",
            mode=mode,
            output=output,
            versions=versions,
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
        assert (first["arm"], first["mode"]) == ("test-arm", "workflow")
        assert first["answer_model"] == "test-answer-model"
        assert first["answer_endpoint"] == "127.0.0.1:9"
        assert (first["retrieval_k"], first["app_version"], first["corpus_version"]) == (
            3,
            "v1",
            "c2",
        )
        assert first["timestamp"].endswith("+00:00")
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
        assert (first["status"], first["answer"]) == ("http_404", None)
        assert OTHER_PROJECT not in _shown(model)
        assert second["status"] == "ok"
        assert third["status"] == "IndexError"
        assert (summary["ok"], summary["failed"]) == (1, 2)

    def test_done_rows_of_the_same_arm_are_skipped(self, assistant_settings, client, tmp_path):
        """
        GIVEN an output file that holds q1 for this arm and q2 for another arm
        WHEN the runner is run again over q1 and q2
        THEN only q2 is asked and appended, since the other arm's row does not count as done
        """
        # GIVEN
        model = _scripted("Answer for q2.")
        fixtures = _setup(client, model)
        output = tmp_path / "out.jsonl"
        done = [{"id": "q1", "arm": "test-arm"}, {"id": "q2", "arm": "other-arm"}]
        output.write_text("".join(json.dumps(row) + "\n" for row in done), encoding="utf-8")
        questions = [{"id": "q1", "question": "One?"}, {"id": "q2", "question": "Two?"}]

        # WHEN
        summary = _run(client, fixtures, questions, output)

        # THEN
        assert [(row["id"], row["arm"]) for row in _rows(output)] == [
            ("q1", "test-arm"),
            ("q2", "other-arm"),
            ("q2", "test-arm"),
        ]
        assert (len(model.seen), summary["rows"]) == (1, 1)

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
        self, assistant_settings, client, tmp_path, monkeypatch
    ):
        """
        GIVEN LANGSMITH_TRACING=true in the environment
        WHEN the runner asks a question, whose search runs before the service's own scope
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
        settings = ea._eval_settings(get_settings(), "hybrid")

        # THEN
        assert settings.assistant_langsmith_enabled is False
        assert settings.assistant_mode == "hybrid"


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
        shown = capsys.readouterr().out
        assert code == 0
        assert [row["id"] for row in _rows(tmp_path / "out.jsonl")] == ["q1"]
        assert "rows=1 ok=1 failed=0 median_latency_s=" in shown
        assert "Plum" not in shown
        assert "Secret-free" not in shown

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
