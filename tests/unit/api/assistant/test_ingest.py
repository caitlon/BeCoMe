"""Unit tests for the ingest CLI's argument handling (fakes only, no network)."""

import argparse
import importlib.util
import sys
from pathlib import Path

from api.assistant.rag.chunkers import ChunkerConfig
from api.assistant.rag.pipeline import CollectionSpec

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
        )

        # WHEN
        spec = ingest._build_spec(args)

        # THEN
        assert spec == CollectionSpec(
            name="docs_default",
            chunker=ChunkerConfig(strategy="markdown_headers", size=500, overlap_pct=10),
            context="none",
            wave=1,
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
