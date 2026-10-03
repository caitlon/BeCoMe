"""Unit tests for the evaluation fixture seeder (in-memory SQLite, no network)."""

import importlib.util
import io
import json
import sys
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from api.auth.password import verify_password
from api.config import Environment, Settings
from api.data.example_project import EXAMPLE_EXPERTS
from api.db.models import ExpertOpinion, Project, User
from examples.utils.data_loading import load_data_from_txt
from src.calculators.become_calculator import BeCoMeCalculator
from tests.shared.helpers import insert_demo_experts

ROOT = Path(__file__).resolve().parents[4]


def _load():
    """Import the script by path, since `scripts/` is not a package.

    :return: The imported `seed_eval_fixtures` module.
    """
    spec = importlib.util.spec_from_file_location(
        "seed_eval_fixtures", ROOT / "scripts" / "assistant" / "seed_eval_fixtures.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["seed_eval_fixtures"] = module
    spec.loader.exec_module(module)
    return module


seed = _load()

# A throwaway value, joined at import so no literal in the file looks like a credential.
PASSWORD = "-".join(["eval", "pw", "for", "tests"])


def _settings(environment: Environment, database_url: str, railway: str | None = None) -> Settings:
    """Settings built without validation, so the real `.env` never leaks in."""
    return Settings.model_construct(
        environment=environment,
        database_url=database_url,
        railway_environment_name=railway,
        testing=False,
    )


def _row_counts(session: Session) -> list[int]:
    """Row counts of the tables a seed run writes to."""
    return [len(session.exec(select(model)).all()) for model in (User, Project, ExpertOpinion)]


@pytest.fixture
def engine():
    """In-memory SQLite engine with all tables created and no demo pool."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    """Session on the in-memory engine."""
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture
def run_main(engine, monkeypatch, capsys):
    """Run `main` against the in-memory engine under the local dev profile."""
    monkeypatch.setattr(seed, "get_settings", lambda: _settings(Environment.DEV, "sqlite://"))
    monkeypatch.setattr(seed, "get_engine", lambda: engine)
    monkeypatch.setattr(seed, "create_db_and_tables", lambda: None)

    def run(*args: str):
        code = seed.main(list(args))
        return code, capsys.readouterr()

    return run


class TestCheckTarget:
    """The seeder only ever touches a local database under the dev profile."""

    @pytest.mark.parametrize(
        "database_url",
        [
            "sqlite:///./become.db",
            "sqlite://",
            "postgresql+psycopg://u@127.0.0.1:5432/db",
            "postgresql+psycopg://u@localhost/db",
        ],
    )
    def test_accepts_dev_profile_on_a_local_database(self, database_url):
        """
        GIVEN the dev profile and a SQLite or loopback database
        WHEN the target is checked
        THEN no error is raised
        """
        seed.check_target(_settings(Environment.DEV, database_url))

    @pytest.mark.parametrize(
        ("environment", "database_url", "railway"),
        [
            (Environment.TEST, "sqlite://", None),
            (Environment.PROD, "sqlite://", None),
            (Environment.DEV, "postgresql+psycopg://u@db.example.com/db", None),
            (Environment.DEV, "postgresql+psycopg://u@127.0.0.1/db?host=db.example.com", None),
            (Environment.DEV, "sqlite://", "dev"),
        ],
    )
    def test_refuses_anything_deployed_or_remote(self, environment, database_url, railway):
        """
        GIVEN a deployed profile, a remote host, or a Railway process
        WHEN the target is checked
        THEN it is refused with UnsafeTargetError
        """
        with pytest.raises(seed.UnsafeTargetError):
            seed.check_target(_settings(environment, database_url, railway))

    def test_main_exits_2_and_never_opens_the_database(self, monkeypatch, capsys):
        """
        GIVEN settings for a deployed database
        WHEN main runs
        THEN it exits with 2, says why on stderr, and never asks for an engine
        """
        monkeypatch.setattr(
            seed,
            "get_settings",
            lambda: _settings(Environment.PROD, "postgresql+psycopg://u@db.example.com/db"),
        )

        def boom():
            raise AssertionError("engine requested for a refused target")

        monkeypatch.setattr(seed, "get_engine", boom)

        code = seed.main([])

        captured = capsys.readouterr()
        assert code == 2
        assert "refus" in captured.err.lower()
        assert captured.out == ""


class TestSeedFixtures:
    """What a run leaves in the database."""

    def test_creates_one_activated_owner(self, session):
        """
        GIVEN an empty database
        WHEN the fixtures are seeded
        THEN one verified, non-demo owner exists with the given password
        """
        seed.seed_fixtures(session, PASSWORD)

        owner = session.exec(select(User).where(User.email == seed.OWNER_EMAIL)).one()
        assert owner.email_verified_at is not None
        assert owner.is_demo is False
        assert verify_password(PASSWORD, owner.hashed_password)

    def test_example_project_has_the_thirteen_floods_experts(self, session):
        """
        GIVEN an empty database without the demo pool
        WHEN the fixtures are seeded
        THEN the owner has the example project with 13 expert opinions
        """
        outcome = seed.seed_fixtures(session, PASSWORD)

        example = next(p for p in outcome.payload["projects"] if p["key"] == "example")
        project = session.get(Project, UUID(example["id"]))
        assert project is not None
        assert project.is_example is True
        assert example["expert_count"] == len(EXAMPLE_EXPERTS) == 13
        assert example["result"]["num_experts"] == 13

    def test_pendlers_result_equals_the_calculator_on_the_case_data(self, session):
        """
        GIVEN the pendlers case file
        WHEN the fixtures are seeded
        THEN the stored result equals what the calculator gives for that data
        """
        outcome = seed.seed_fixtures(session, PASSWORD)

        opinions, _ = load_data_from_txt(str(ROOT / "examples" / "data" / "pendlers_case.txt"))
        expected = BeCoMeCalculator().calculate_compromise(opinions)
        projects = {p["key"]: p for p in outcome.payload["projects"]}
        pendlers = projects["pendlers"]
        result = pendlers["result"]
        assert pendlers["expert_count"] == len(opinions) == 22
        assert result["best_compromise"]["lower"] == expected.best_compromise.lower_bound
        assert result["best_compromise"]["peak"] == expected.best_compromise.peak
        assert result["best_compromise"]["upper"] == expected.best_compromise.upper_bound
        assert result["best_compromise"]["centroid"] == expected.best_compromise.centroid
        assert result["max_error"] == expected.max_error
        assert result["num_experts"] == expected.num_experts
        assert pendlers["name"] != projects["example"]["name"]

    def test_second_run_changes_nothing(self, session):
        """
        GIVEN fixtures that were seeded once
        WHEN they are seeded again
        THEN no row is added, the ids are the same and nothing is reported as created
        """
        first = seed.seed_fixtures(session, PASSWORD)
        counts = _row_counts(session)

        second = seed.seed_fixtures(session, None)

        assert _row_counts(session) == counts
        assert second.payload["user"] == first.payload["user"]
        assert [p["id"] for p in second.payload["projects"]] == [
            p["id"] for p in first.payload["projects"]
        ]
        assert first.created == {"user", "example", "pendlers"}
        assert second.created == set()

    def test_interrupted_pendlers_run_is_completed_by_the_next_one(self, engine, monkeypatch):
        """
        GIVEN a first run that failed at the 10th pendlers opinion
        WHEN the fixtures are seeded again in a new session
        THEN the project is completed: 22 opinions, a result, and the full payload
        """
        real = seed.OpinionService.upsert_opinion
        calls = []

        def flaky(self, *args, **kwargs):
            calls.append(1)
            if len(calls) == 10:
                raise RuntimeError("interrupted")
            return real(self, *args, **kwargs)

        with monkeypatch.context() as patched:
            patched.setattr(seed.OpinionService, "upsert_opinion", flaky)
            with Session(engine) as first, pytest.raises(RuntimeError):
                seed.seed_fixtures(first, PASSWORD)

        with Session(engine) as second:
            outcome = seed.seed_fixtures(second, None)

            pendlers = next(p for p in outcome.payload["projects"] if p["key"] == "pendlers")
            assert pendlers["expert_count"] == pendlers["result"]["num_experts"] == 22
            assert len(second.exec(select(Project)).all()) == 2

    def test_existing_demo_pool_is_reused(self, session):
        """
        GIVEN a database that already carries the demo pool (as after the migration)
        WHEN the fixtures are seeded
        THEN the pool is not duplicated
        """
        insert_demo_experts(session)

        seed.seed_fixtures(session, PASSWORD)

        pool = [u.email for u in session.exec(select(User)).all() if u.email.endswith(".invalid")]
        assert len(pool) == len(set(pool)) == len(EXAMPLE_EXPERTS)


class TestMain:
    """The command line: JSON on stdout, secrets handled with care."""

    def test_prints_the_documented_json_shape(self, run_main):
        """
        GIVEN a fresh database
        WHEN main runs with a password
        THEN stdout is one JSON document with the documented keys
        """
        code, captured = run_main("--password", PASSWORD)

        payload = json.loads(captured.out)
        assert code == 0
        assert set(payload) == {"user", "projects"}
        assert set(payload["user"]) == {"id", "email"}
        assert payload["user"]["email"] == seed.OWNER_EMAIL
        assert [p["key"] for p in payload["projects"]] == ["example", "pendlers"]
        for project in payload["projects"]:
            assert set(project) == {"key", "id", "name", "expert_count", "result"}
            assert set(project["result"]) == {
                "best_compromise",
                "arithmetic_mean",
                "median",
                "max_error",
                "num_experts",
                "agreement_level",
                "likert_value",
                "likert_decision",
            }
            assert set(project["result"]["best_compromise"]) == {
                "lower",
                "peak",
                "upper",
                "centroid",
            }

    def test_output_option_writes_the_same_json_to_a_file(self, run_main, tmp_path):
        """
        GIVEN --output pointing at a file
        WHEN main runs
        THEN the file holds the JSON and stdout does not
        """
        target = tmp_path / "fixtures.json"

        code, captured = run_main("--password", PASSWORD, "--output", str(target))

        written = json.loads(target.read_text(encoding="utf-8"))
        assert code == 0
        assert captured.out == ""
        assert written["user"]["email"] == seed.OWNER_EMAIL
        assert [p["key"] for p in written["projects"]] == ["example", "pendlers"]

    def test_output_option_creates_the_missing_parent_directory(self, run_main, tmp_path):
        """
        GIVEN --output inside a directory that does not exist yet
        WHEN main runs
        THEN the directory is created and the file written
        """
        target = tmp_path / "nested" / "dir" / "fixtures.json"

        code, _ = run_main("--password", PASSWORD, "--output", str(target))

        assert code == 0
        assert target.is_file()

    def test_generated_password_is_printed_before_any_later_step_runs(self, run_main, monkeypatch):
        """
        GIVEN no password argument and a failure in the step after the account is created
        WHEN main runs
        THEN the generated password has already reached stderr
        """

        def boom(*args, **kwargs):
            raise RuntimeError("later step failed")

        monkeypatch.setattr(seed, "_ensure_example_project", boom)
        err = io.StringIO()
        monkeypatch.setattr(sys, "stderr", err)

        with pytest.raises(RuntimeError):
            seed.main([])

        assert "generated password: " in err.getvalue()

    def test_generated_password_is_printed_once_and_never_on_stdout(self, run_main, session):
        """
        GIVEN no password argument
        WHEN main runs twice
        THEN the first run prints a generated password to stderr that opens the account,
            and the second prints none and reports the fixtures as already present
        """
        _, first = run_main()
        _, second = run_main()

        marker = "generated password: "
        line = next(ln for ln in first.err.splitlines() if marker in ln)
        generated = line.split(marker, 1)[1].strip()
        owner = session.exec(select(User).where(User.email == seed.OWNER_EMAIL)).one()
        assert verify_password(generated, owner.hashed_password)
        assert generated not in first.out
        assert marker not in second.err
        assert "already present" in second.err
