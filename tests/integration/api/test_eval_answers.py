"""Tests for the answer eval runner, driven through the real test application.

The chat model is a scripted one from ``tests/shared/assistant_fakes.py`` and the retriever
is a static one, so no model server, embedding server or vector database is reached. The
users, projects and tenant checks are the test application's own, over in-memory SQLite.
The questions are invented here; nothing reads the sealed question set.
"""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
import pytest
from langchain_core.messages import AIMessage

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
# The credentials in the URL must never reach a row.
ANSWER_URL = "http://runner:hunter2@127.0.0.1:9/v1"  # pragma: allowlist secret
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


def _setup(client, model, chunks=()):
    """Sign two users in, give each a project, install the model and return the fixtures."""
    own_token = register_and_login(client, "runner@example.com")
    other_token = register_and_login(client, "someone-else@example.com")
    own = create_project(client, own_token, name=OWN_PROJECT)
    other = create_project(client, other_token, name=OTHER_PROJECT)
    account = stored_accounts(client, "runner@example.com")[0]
    client.app.dependency_overrides[deps.get_answer_model] = lambda: model
    client.app.dependency_overrides[deps.get_docs_retriever] = lambda: StaticDocsRetriever(
        list(chunks)
    )
    return {
        "user": {"id": str(account["id"]), "email": account["email"]},
        "projects": [
            {"key": "own", "id": own["id"], "name": OWN_PROJECT},
            {"key": "foreign", "id": other["id"], "name": OTHER_PROJECT},
        ],
    }


def _run(
    client, fixtures, questions, output, mode="workflow", arm="test-arm", versions=(None, None)
):
    return asyncio.run(
        ea.run_eval(
            client.app,
            questions,
            fixtures,
            settings=get_settings(),
            arm=arm,
            mode=mode,
            output=output,
            versions=versions,
        )
    )


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _chunk(url: str | None, words: str) -> RetrievedChunk:
    return RetrievedChunk(
        text="indexed",
        title="Method guide",
        section="Aggregation",
        url=url,
        layer="public",
        score=1.0,
        chunk_text=words,
    )


class TestRunEval:
    """One single-turn chat per question, as the fixtures user, through the real route."""

    def test_one_row_per_question_with_every_field(self, assistant_settings, client, tmp_path):
        """
        GIVEN two invented questions and a scripted model that answers each
        WHEN the runner asks them
        THEN the output holds one row per question with the listed fields and the summary counts them
        """
        # GIVEN
        model = _scripted("It combines two averages.", "Zadne.")
        fixtures = _setup(
            client,
            model,
            [
                _chunk("https://example.test/guide", "First passage."),
                _chunk(None, "Second passage."),
            ],
        )
        questions = [
            {"id": "q1", "question": "What does BeCoMe combine?", "lang": "en"},
            {"id": "q2", "question": "Co kombinuje BeCoMe?", "lang": "cs"},
        ]
        output = tmp_path / "out.jsonl"

        # WHEN
        summary = _run(client, fixtures, questions, output, versions=("v1", "c2"))

        # THEN
        rows = _rows(output)
        assert [row["id"] for row in rows] == ["q1", "q2"]
        first = rows[0]
        assert first["status"] == "ok"
        assert first["answer"] == "It combines two averages."
        assert first["question"] == "What does BeCoMe combine?"
        assert first["lang"] == "en"
        assert first["project"] is None
        assert first["tool_calls"] == []
        assert set(first["checks"]) == {"citations_valid", "numbers_grounded", "ungrounded_numbers"}
        assert first["sources"] == [
            {
                "n": 1,
                "title": "Method guide",
                "section": "Aggregation",
                "layer": "public",
                "has_url": True,
            },
            {
                "n": 2,
                "title": "Method guide",
                "section": "Aggregation",
                "layer": "public",
                "has_url": False,
            },
        ]
        assert isinstance(first["latency_s"], float)
        assert first["arm"] == "test-arm"
        assert first["mode"] == "workflow"
        assert first["answer_model"] == "test-answer-model"
        assert first["answer_endpoint"] == "127.0.0.1:9"
        assert first["retrieval_k"] == 3
        assert first["app_version"] == "v1"
        assert first["corpus_version"] == "c2"
        assert first["timestamp"].endswith("+00:00")
        assert summary["rows"] == 2
        assert summary["ok"] == 2
        assert summary["failed"] == 0
        assert summary["median_latency_s"] is not None

    def test_credentials_in_the_endpoint_never_reach_a_row(
        self, assistant_settings, client, tmp_path
    ):
        """
        GIVEN an answer model URL that carries a user name and a password
        WHEN a row is written
        THEN neither appears anywhere in the file
        """
        # GIVEN
        fixtures = _setup(client, _scripted("Fine."))
        output = tmp_path / "out.jsonl"

        # WHEN
        _run(client, fixtures, [{"id": "q1", "question": "Hello?"}], output)

        # THEN
        text = output.read_text(encoding="utf-8")
        assert "hunter2" not in text
        assert "runner:" not in text

    def test_prompt_sha256_is_the_hash_of_the_product_prompt(
        self, assistant_settings, client, tmp_path
    ):
        """
        GIVEN a run
        WHEN a row is written
        THEN prompt_sha256 is the sha256 of the product's SYSTEM_PROMPT
        """
        # GIVEN
        fixtures = _setup(client, _scripted("Fine."))
        output = tmp_path / "out.jsonl"

        # WHEN
        _run(client, fixtures, [{"id": "q1", "question": "Hello?"}], output)

        # THEN
        expected = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
        assert _rows(output)[0]["prompt_sha256"] == expected
        assert expected == ea.PROMPT_SHA256

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
        assert row["status"] == "ok"
        assert row["project"] == "own"
        assert OWN_PROJECT in _shown(model)

    def test_a_project_of_another_user_fails_the_row_and_the_run_goes_on(
        self, assistant_settings, client, tmp_path
    ):
        """
        GIVEN a question about a project the fixtures user is not a member of, then a plain one
        WHEN the runner asks both
        THEN the first row carries the tenant check's 404 and the second is answered
        """
        # GIVEN
        model = _scripted("Plain answer.")
        fixtures = _setup(client, model)
        questions = [
            {"id": "q1", "question": "What is the result?", "project": "foreign"},
            {"id": "q2", "question": "What is BeCoMe?"},
        ]
        output = tmp_path / "out.jsonl"

        # WHEN
        summary = _run(client, fixtures, questions, output)

        # THEN
        first, second = _rows(output)
        assert first["status"] == "http_404"
        assert first["answer"] is None
        assert OTHER_PROJECT not in _shown(model)
        assert second["status"] == "ok"
        assert (summary["ok"], summary["failed"]) == (1, 1)

    def test_a_turn_that_raises_is_recorded_by_its_class_name(
        self, assistant_settings, client, tmp_path
    ):
        """
        GIVEN a model with no answer left to give, so the second turn raises
        WHEN the runner asks two questions
        THEN the second row carries the exception's class name and the first stays ok
        """
        # GIVEN
        fixtures = _setup(client, _scripted("Only one answer."))
        questions = [{"id": "q1", "question": "One?"}, {"id": "q2", "question": "Two?"}]
        output = tmp_path / "out.jsonl"

        # WHEN
        _run(client, fixtures, questions, output)

        # THEN
        first, second = _rows(output)
        assert first["status"] == "ok"
        assert second["status"] == "IndexError"

    def test_done_rows_of_the_same_arm_are_skipped(self, assistant_settings, client, tmp_path):
        """
        GIVEN an output file that already holds q1 for this arm and q1 for another arm
        WHEN the runner is run again over q1 and q2
        THEN only q2 is asked and appended, and the other arm's row does not count as done
        """
        # GIVEN
        model = _scripted("Answer for q2.", "Answer for q1.")
        fixtures = _setup(client, model)
        output = tmp_path / "out.jsonl"
        done = [{"id": "q1", "arm": "test-arm"}, {"id": "q2", "arm": "other-arm"}]
        output.write_text("".join(json.dumps(row) + "\n" for row in done), encoding="utf-8")
        questions = [{"id": "q1", "question": "One?"}, {"id": "q2", "question": "Two?"}]

        # WHEN
        summary = _run(client, fixtures, questions, output)

        # THEN
        rows = _rows(output)
        assert [(row["id"], row["arm"]) for row in rows] == [
            ("q1", "test-arm"),
            ("q2", "other-arm"),
            ("q2", "test-arm"),
        ]
        assert len(model.seen) == 1
        assert summary["rows"] == 1

    def test_the_mode_reaches_the_service(self, assistant_settings, client, tmp_path):
        """
        GIVEN a model that first calls a tool, and the settings saying workflow
        WHEN the runner is asked for agent mode
        THEN the turn runs the tool, and in workflow mode the same script calls none
        """
        # GIVEN
        call = AIMessage(
            content="",
            tool_calls=[{"name": "list_my_projects", "args": {}, "id": "c1", "type": "tool_call"}],
        )
        model = ScriptedToolCallingModel(responses=[call, AIMessage(content="You have two.")])
        fixtures = _setup(client, model)
        question = [{"id": "q1", "question": "Which projects are mine?"}]
        agent_out = tmp_path / "agent.jsonl"
        workflow_out = tmp_path / "workflow.jsonl"

        # WHEN
        _run(client, fixtures, question, agent_out, mode="agent")
        flow_model = _scripted("Tools were never offered.")
        client.app.dependency_overrides[deps.get_answer_model] = lambda: flow_model
        _run(client, fixtures, question, workflow_out, mode="workflow")

        # THEN
        agent_row = _rows(agent_out)[0]
        assert agent_row["mode"] == "agent"
        assert agent_row["tool_calls"] == ["list_my_projects"]
        assert _rows(workflow_out)[0]["tool_calls"] == []

    def test_the_settings_override_is_removed_after_the_run(
        self, assistant_settings, client, tmp_path
    ):
        """
        GIVEN an app without a settings override
        WHEN the runner has run
        THEN the app is left as it was found
        """
        # GIVEN
        fixtures = _setup(client, _scripted("Fine."))

        # WHEN
        _run(client, fixtures, [{"id": "q1", "question": "Hi?"}], tmp_path / "out.jsonl")

        # THEN
        assert get_settings not in client.app.dependency_overrides


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
    """Reading the questions and the fixtures."""

    def test_questions_are_validated_against_the_fixtures(self, tmp_path):
        """
        GIVEN a questions file whose second record names a project key the fixtures lack
        WHEN it is loaded
        THEN loading fails before any turn, naming the key and not the question
        """
        # GIVEN
        path = tmp_path / "q.jsonl"
        records = [{"id": "q1", "question": "A?"}, {"id": "q2", "question": "B?", "project": "x"}]
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

        # WHEN / THEN
        with pytest.raises(ValueError, match="'x'") as raised:
            ea._load_questions(path, {"own"}, None)
        assert "B?" not in str(raised.value)

    def test_a_record_without_an_id_is_refused(self, tmp_path):
        """
        GIVEN a record with no id
        WHEN the questions are loaded
        THEN loading fails
        """
        # GIVEN
        path = tmp_path / "q.jsonl"
        path.write_text(json.dumps({"question": "A?"}) + "\n", encoding="utf-8")

        # WHEN / THEN
        with pytest.raises(ValueError, match="id"):
            ea._load_questions(path, set(), None)

    def test_limit_keeps_the_first_questions(self, tmp_path):
        """
        GIVEN three questions
        WHEN they are loaded with a limit of two
        THEN the first two come back
        """
        # GIVEN
        path = tmp_path / "q.jsonl"
        lines = [json.dumps({"id": f"q{i}", "question": "A?"}) for i in range(3)]
        path.write_text("\n".join(lines) + "\n\n", encoding="utf-8")

        # WHEN
        loaded = ea._load_questions(path, set(), 2)

        # THEN
        assert [record["id"] for record in loaded] == ["q0", "q1"]


class TestCollectionVersions:
    """The versions of the collection, read from the registry when it can be reached."""

    def test_no_database_url_gives_no_versions(self):
        """
        GIVEN settings with no vector database URL
        WHEN the versions are asked for
        THEN both are None and no connection is tried
        """
        # WHEN
        with patch.object(psycopg, "connect") as connect:
            versions = ea._collection_versions(get_settings())

        # THEN
        assert versions == (None, None)
        connect.assert_not_called()

    def test_an_unreachable_database_gives_no_versions(self, monkeypatch):
        """
        GIVEN a vector database URL nothing answers on
        WHEN the versions are asked for
        THEN both are None instead of an error
        """
        # GIVEN
        monkeypatch.setenv("ASSISTANT_VECTOR_DB_URL", "postgresql+psycopg://u:p@127.0.0.1:9/db")
        _reset()

        # WHEN
        with patch.object(psycopg, "connect", side_effect=psycopg.OperationalError("down")):
            versions = ea._collection_versions(get_settings())

        # THEN
        assert versions == (None, None)

    def test_the_registry_row_gives_both_versions(self, monkeypatch):
        """
        GIVEN a registry row for the configured collection
        WHEN the versions are asked for
        THEN the app and the corpus version come back, read with the psycopg DSN
        """
        # GIVEN
        monkeypatch.setenv("ASSISTANT_VECTOR_DB_URL", "postgresql+psycopg://u:p@127.0.0.1:9/db")
        _reset()

        class _Connection:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return None

            def execute(self, *_args):
                return SimpleNamespace(fetchone=lambda: ("app-1", "corpus-2"))

        # WHEN
        with patch.object(psycopg, "connect", return_value=_Connection()) as connect:
            versions = ea._collection_versions(get_settings())

        # THEN
        assert versions == ("app-1", "corpus-2")
        assert connect.call_args.args[0] == "postgresql://u:p@127.0.0.1:9/db"


class TestMain:
    """The command line, end to end over the test application."""

    def test_main_writes_the_rows_and_prints_the_summary(
        self, assistant_settings, client, tmp_path, capsys
    ):
        """
        GIVEN a questions file, a fixtures file and an app that serves the chat
        WHEN main runs with a limit of one
        THEN it exits 0, appends one row, and prints counts and the median without any text
        """
        # GIVEN
        fixtures = _setup(client, _scripted("Secret-free answer."))
        fixtures_path = tmp_path / "fixtures.json"
        fixtures_path.write_text(json.dumps(fixtures), encoding="utf-8")
        questions_path = tmp_path / "q.jsonl"
        records = [{"id": "q1", "question": "Plum?"}, {"id": "q2", "question": "Pear?"}]
        questions_path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        output = tmp_path / "out.jsonl"
        argv = [
            "--questions", str(questions_path),
            "--fixtures", str(fixtures_path),
            "--mode", "workflow",
            "--arm", "cli",
            "--output", str(output),
            "--limit", "1",
        ]  # fmt: skip

        # WHEN
        with patch.object(ea, "create_app", return_value=client.app):
            code = ea.main(argv)

        # THEN
        shown = capsys.readouterr().out
        assert code == 0
        assert [row["id"] for row in _rows(output)] == ["q1"]
        assert "rows=1 ok=1 failed=0 median_latency_s=" in shown
        assert "Plum" not in shown
        assert "Secret-free" not in shown

    def test_main_refuses_when_the_assistant_is_off(self, client, tmp_path, capsys):
        """
        GIVEN settings with the assistant switched off
        WHEN main runs
        THEN it exits 2 and says which setting to raise
        """
        # GIVEN
        questions_path = tmp_path / "q.jsonl"
        questions_path.write_text(json.dumps({"id": "q1", "question": "A?"}), encoding="utf-8")
        argv = [
            "--questions", str(questions_path),
            "--fixtures", str(tmp_path / "fixtures.json"),
            "--mode", "agent",
            "--arm", "cli",
            "--output", str(tmp_path / "out.jsonl"),
        ]  # fmt: skip

        # WHEN
        code = ea.main(argv)

        # THEN
        assert code == 2
        assert "ASSISTANT_ENABLED" in capsys.readouterr().err


class TestSealGuard:
    """A sealed question set is refused unless a written registration comes with it."""

    @staticmethod
    def _args(registration: Path | None, sealed_run: bool) -> argparse.Namespace:
        return argparse.Namespace(sealed_run=sealed_run, registration=registration)

    def test_a_sealed_file_is_refused_without_the_flag(self, tmp_path):
        """
        GIVEN a questions file whose hash is on the sealed list
        WHEN the guard looks at a run without --sealed-run
        THEN it names the problem
        """
        # GIVEN
        digest = "ab" * 32

        # WHEN
        with patch.object(ea, "SEALED_SHA256", frozenset({digest})):
            problem = ea._seal_problem(digest, self._args(None, False))

        # THEN
        assert problem is not None
        assert "--sealed-run" in problem

    def test_the_flag_without_a_registration_is_refused(self):
        """
        GIVEN a sealed file and --sealed-run but no registration
        WHEN the guard looks at it
        THEN it asks for the registration
        """
        # GIVEN
        digest = "ab" * 32

        # WHEN
        with patch.object(ea, "SEALED_SHA256", frozenset({digest})):
            problem = ea._seal_problem(digest, self._args(None, True))

        # THEN
        assert problem is not None
        assert "--registration" in problem

    def test_an_empty_or_missing_registration_is_refused(self, tmp_path):
        """
        GIVEN --sealed-run with a registration that is empty, and with one that does not exist
        WHEN the guard looks at each
        THEN both are refused
        """
        # GIVEN
        digest = "ab" * 32
        empty = tmp_path / "empty.md"
        empty.write_text("", encoding="utf-8")

        # WHEN
        with patch.object(ea, "SEALED_SHA256", frozenset({digest})):
            empty_problem = ea._seal_problem(digest, self._args(empty, True))
            missing_problem = ea._seal_problem(digest, self._args(tmp_path / "none.md", True))

        # THEN
        assert empty_problem is not None
        assert missing_problem is not None

    def test_a_registration_lets_a_sealed_run_through(self, tmp_path):
        """
        GIVEN a sealed file, --sealed-run and a non-empty registration
        WHEN the guard looks at it
        THEN there is no problem
        """
        # GIVEN
        digest = "ab" * 32
        registration = tmp_path / "registration.md"
        registration.write_text("Pre-registered: arms, metrics, rules.\n", encoding="utf-8")

        # WHEN
        with patch.object(ea, "SEALED_SHA256", frozenset({digest})):
            problem = ea._seal_problem(digest, self._args(registration, True))

        # THEN
        assert problem is None

    def test_an_ordinary_file_needs_nothing(self):
        """
        GIVEN a questions file whose hash is not sealed
        WHEN the guard looks at a plain run
        THEN there is no problem
        """
        # WHEN
        problem = ea._seal_problem("cd" * 32, self._args(None, False))

        # THEN
        assert problem is None

    def test_the_real_constant_lists_one_hash(self):
        """
        GIVEN the module's own constant
        WHEN it is read
        THEN it is a frozenset of one 64-character hex digest
        """
        assert isinstance(ea.SEALED_SHA256, frozenset)
        assert len(ea.SEALED_SHA256) == 1
        assert all(len(digest) == 64 for digest in ea.SEALED_SHA256)

    def test_main_exits_2_before_doing_anything_on_a_sealed_file(
        self, tmp_path, monkeypatch, capsys
    ):
        """
        GIVEN a questions file whose hash is on the sealed list
        WHEN main runs without --sealed-run
        THEN it exits 2 with a message, and creates no output file
        """
        # GIVEN
        questions = tmp_path / "q.jsonl"
        questions.write_text(json.dumps({"id": "q1", "question": "A?"}) + "\n", encoding="utf-8")
        digest = hashlib.sha256(questions.read_bytes()).hexdigest()
        output = tmp_path / "out.jsonl"
        argv = [
            "--questions", str(questions),
            "--fixtures", str(tmp_path / "fixtures.json"),
            "--mode", "workflow",
            "--arm", "a",
            "--output", str(output),
        ]  # fmt: skip

        # WHEN
        with patch.object(ea, "SEALED_SHA256", frozenset({digest})):
            code = ea.main(argv)

        # THEN
        assert code == 2
        assert "sealed" in capsys.readouterr().err
        assert not output.exists()
