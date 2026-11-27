"""Unit tests for the ingest CLI's argument handling (fakes only, no network)."""

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

from api.assistant.rag.chunkers import ChunkerConfig
from api.assistant.rag.pipeline import BuildReport, CollectionSpec, FlaggedChunksError
from api.assistant.rag.screening import FlaggedChunk

ROOT = Path(__file__).resolve().parents[4]


def _load():
    """Import the script by path, since `scripts/` is not a package.

    :return: The imported `ingest` module.
    """
    spec = importlib.util.spec_from_file_location(
        "ingest", ROOT / "scripts" / "assistant" / "ingest.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest"] = module
    spec.loader.exec_module(module)
    return module


ingest = _load()


class TestBuildSpec:
    """_build_spec turns parsed CLI arguments into a CollectionSpec."""

    def test_builds_a_collection_spec_from_parsed_arguments(self):
        """
        GIVEN parsed arguments for a dense, markdown_headers collection
        WHEN _build_spec converts them
        THEN the resulting CollectionSpec carries every field correctly
        """
        # GIVEN
        args = argparse.Namespace(
            name="docs_default",
            strategy="markdown_headers",
            size=500,
            overlap_pct=10,
            context="none",
            wave=1,
            accept_flagged=["a" * 64],
        )

        # WHEN
        spec = ingest._build_spec(args)

        # THEN
        assert spec == CollectionSpec(
            name="docs_default",
            chunker=ChunkerConfig(strategy="markdown_headers", size=500, overlap_pct=10),
            context="none",
            wave=1,
            accepted_flagged=frozenset({"a" * 64}),
        )


class TestParseArgs:
    """_parse_args accepts every documented --context mode, "captions" included."""

    def test_context_captions_is_parsed_and_reaches_the_collection_spec(self, monkeypatch):
        """
        GIVEN CLI arguments naming --context captions
        WHEN _parse_args parses them and _build_spec converts the result
        THEN the resulting CollectionSpec carries context="captions"
        """
        # GIVEN
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "ingest.py",
                "--name",
                "docs_default",
                "--strategy",
                "markdown_headers",
                "--context",
                "captions",
            ],
        )

        # WHEN
        spec = ingest._build_spec(ingest._parse_args())

        # THEN
        assert spec.context == "captions"

    def test_accept_flagged_is_repeatable_and_reaches_the_collection_spec(self, monkeypatch):
        """
        GIVEN CLI arguments with --accept-flagged twice and one key repeated
        WHEN _parse_args parses them and _build_spec converts the result
        THEN the spec carries each key once, and none by default
        """
        # GIVEN
        base = ["ingest.py", "--name", "docs_default", "--strategy", "fixed"]
        monkeypatch.setattr(
            sys, "argv", [*base, "--accept-flagged", "k1", "--accept-flagged", "k2"]
        )

        # WHEN
        accepted = ingest._build_spec(ingest._parse_args()).accepted_flagged
        monkeypatch.setattr(sys, "argv", base)
        by_default = ingest._build_spec(ingest._parse_args()).accepted_flagged

        # THEN
        assert accepted == frozenset({"k1", "k2"})
        assert by_default == frozenset()


class TestMain:
    """_main prints the build's chunk count and one line per flagged chunk, or the stop."""

    @pytest.mark.asyncio
    async def test_prints_the_count_and_a_line_per_flagged_chunk(self, monkeypatch, capsys):
        """
        GIVEN a build that wrote 5 chunks and flagged two of them
        WHEN _main runs
        THEN it prints the count line, then a flagged line per chunk, and returns the report
        """
        # GIVEN
        report = BuildReport(
            chunk_count=5,
            flagged=[
                FlaggedChunk("public", "/repo/docs/a.md", "Intro", "assistant tag <docs>", "k1"),
                FlaggedChunk("local", "/priv/b.pdf", "", "role marker [inst]", "k2"),
            ],
        )

        async def _fake_build(spec, settings, repo_root):
            return report

        monkeypatch.setattr(ingest, "build_collection", _fake_build)
        monkeypatch.setattr(sys, "argv", ["ingest.py", "--name", "docs_x", "--strategy", "fixed"])

        # WHEN
        returned = await ingest._main()

        # THEN
        assert returned == report
        assert capsys.readouterr().out.splitlines() == [
            "Built collection 'docs_x': 5 chunks",
            "flagged: public | /repo/docs/a.md | Intro | assistant tag <docs> | k1",
            "flagged: local | /priv/b.pdf |  | role marker [inst] | k2",
        ]

    @pytest.mark.asyncio
    async def test_a_flagged_line_carries_no_control_character(self, monkeypatch, capsys):
        """
        GIVEN a flagged chunk whose section holds a terminal escape and a line break
        WHEN _main runs
        THEN the printed line has neither, and stays one line
        """
        # GIVEN
        report = BuildReport(
            chunk_count=1,
            flagged=[
                FlaggedChunk("local", "/priv/b.pdf", "A\x1b[2Jb\nflagged: x", "r", "k\x1b[2J")
            ],
        )

        async def _fake_build(spec, settings, repo_root):
            return report

        monkeypatch.setattr(ingest, "build_collection", _fake_build)
        monkeypatch.setattr(sys, "argv", ["ingest.py", "--name", "docs_x", "--strategy", "fixed"])

        # WHEN
        await ingest._main()

        # THEN
        lines = capsys.readouterr().out.splitlines()
        assert lines[1:] == ["flagged: local | /priv/b.pdf | A[2Jb flagged: x | r | k[2J"]

    @pytest.mark.asyncio
    async def test_prints_only_the_count_when_nothing_is_flagged(self, monkeypatch, capsys):
        """
        GIVEN a build that flagged nothing
        WHEN _main runs
        THEN it prints the count line and no flagged line
        """

        # GIVEN
        async def _fake_build(spec, settings, repo_root):
            return BuildReport(chunk_count=3, flagged=[])

        monkeypatch.setattr(ingest, "build_collection", _fake_build)
        monkeypatch.setattr(sys, "argv", ["ingest.py", "--name", "docs_x", "--strategy", "fixed"])

        # WHEN
        await ingest._main()

        # THEN
        assert capsys.readouterr().out == "Built collection 'docs_x': 3 chunks\n"

    @pytest.mark.asyncio
    async def test_a_stop_prints_every_flagged_line_and_exits_with_status_1(
        self, monkeypatch, capsys
    ):
        """
        GIVEN a build that stopped on an unaccepted private chunk next to a public one
        WHEN _main runs
        THEN it prints every flagged line with its key, then one stop line saying nothing was
             written and how to proceed, no "Built" line, and exits with status 1
        """
        # GIVEN
        public = FlaggedChunk("public", "/repo/docs/a.md", "Intro", "assistant tag <docs>", "k1")
        private = FlaggedChunk("local", "/priv/b.pdf", "", "role marker [inst]", "k2")

        async def _fake_build(spec, settings, repo_root):
            raise FlaggedChunksError([public, private], [private])

        monkeypatch.setattr(ingest, "build_collection", _fake_build)
        monkeypatch.setattr(sys, "argv", ["ingest.py", "--name", "docs_x", "--strategy", "fixed"])

        # WHEN
        with pytest.raises(SystemExit) as caught:
            await ingest._main()

        # THEN
        assert caught.value.code == 1
        lines = capsys.readouterr().out.splitlines()
        assert lines[:2] == [
            "flagged: public | /repo/docs/a.md | Intro | assistant tag <docs> | k1",
            "flagged: local | /priv/b.pdf |  | role marker [inst] | k2",
        ]
        assert len(lines) == 3
        assert lines[2].startswith("Build of 'docs_x' stopped: 1 flagged chunk(s)")
        assert "Nothing was written and the live collection is unchanged" in lines[2]
        assert "--accept-flagged <key>" in lines[2]

    @pytest.mark.asyncio
    async def test_an_accepted_key_reaches_the_build_and_a_stale_one_is_noted(
        self, monkeypatch, capsys
    ):
        """
        GIVEN --accept-flagged for a key that matches a flagged chunk and one that matches none
        WHEN _main runs and the build goes on
        THEN the spec handed to the build carries both keys, the flagged line prints, and a
             note names the key that matched no flagged chunk, without stopping
        """
        # GIVEN
        seen = {}
        report = BuildReport(
            chunk_count=2, flagged=[FlaggedChunk("local", "/priv/b.pdf", "", "r", "k2")]
        )

        async def _fake_build(spec, settings, repo_root):
            seen["accepted"] = spec.accepted_flagged
            return report

        monkeypatch.setattr(ingest, "build_collection", _fake_build)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "ingest.py",
                "--name",
                "docs_x",
                "--strategy",
                "fixed",
                "--accept-flagged",
                "k2",
                "--accept-flagged",
                "gone",
            ],
        )

        # WHEN
        returned = await ingest._main()

        # THEN
        assert returned == report
        assert seen["accepted"] == frozenset({"k2", "gone"})
        assert capsys.readouterr().out.splitlines() == [
            "Built collection 'docs_x': 2 chunks",
            "flagged: local | /priv/b.pdf |  | r | k2",
            "note: --accept-flagged gone matches no flagged chunk",
        ]
