"""Unit tests for the evaluation fixture seeder's target check (no database is opened)."""

import importlib.util
import sys
from pathlib import Path

import pytest

from api.config import Environment, Settings

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


def _settings(environment: Environment, database_url: str, railway: str | None = None) -> Settings:
    """Settings built without validation, so the real `.env` never leaks in."""
    return Settings.model_construct(
        environment=environment,
        database_url=database_url,
        railway_environment_name=railway,
        testing=False,
    )


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
