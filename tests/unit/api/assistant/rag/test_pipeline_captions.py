"""Unit tests for pipeline.py's captions handling: load_captions() (the captions-file
reader the "captions" context mode needs) and build_collection()'s guard against a
captions file that matches none of the corpus's chunks (fakes only, no network, no
database)."""

import json
import re

import pytest

from api.assistant.rag.chunkers import ChunkerConfig
from api.assistant.rag.pipeline import CollectionSpec, build_collection, load_captions
from api.config import Settings


class TestLoadCaptions:
    """load_captions reads the chunk_key -> caption mapping the "captions" mode needs."""

    def test_requires_the_captions_file_setting(self, tmp_path):
        """
        GIVEN Settings with no assistant_captions_file configured
        WHEN load_captions runs
        THEN it raises ValueError naming ASSISTANT_CAPTIONS_FILE
        """
        # GIVEN
        settings = Settings(secret_key="test-secret-key")

        # WHEN / THEN
        with pytest.raises(ValueError, match="ASSISTANT_CAPTIONS_FILE"):
            load_captions(settings, repo_root=tmp_path)

    def test_reads_a_relative_path_from_repo_root(self, tmp_path):
        """
        GIVEN a captions file named by a path relative to repo_root
        WHEN load_captions runs
        THEN it reads that file, resolved against repo_root
        """
        # GIVEN
        (tmp_path / "captions.json").write_text(
            json.dumps({"a" * 64: "Caption text."}), encoding="utf-8"
        )
        settings = Settings(secret_key="test-secret-key", assistant_captions_file="captions.json")

        # WHEN
        captions = load_captions(settings, repo_root=tmp_path)

        # THEN
        assert captions == {"a" * 64: "Caption text."}

    def test_reads_an_absolute_path(self, tmp_path):
        """
        GIVEN a captions file named by an absolute path outside repo_root
        WHEN load_captions runs
        THEN it reads that file directly, ignoring repo_root - the absolute path
             wins the join
        """
        # GIVEN
        outside = tmp_path.parent / f"{tmp_path.name}-captions.json"
        outside.write_text(json.dumps({"b" * 64: "Another caption."}), encoding="utf-8")
        settings = Settings(secret_key="test-secret-key", assistant_captions_file=str(outside))

        # WHEN
        captions = load_captions(settings, repo_root=tmp_path / "repo")

        # THEN
        assert captions == {"b" * 64: "Another caption."}

    def test_rejects_a_json_array(self, tmp_path):
        """
        GIVEN a captions file holding a JSON array instead of an object
        WHEN load_captions runs
        THEN it raises ValueError naming the file's path
        """
        # GIVEN
        captions_file = tmp_path / "captions.json"
        captions_file.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
        settings = Settings(
            secret_key="test-secret-key", assistant_captions_file=str(captions_file)
        )

        # WHEN / THEN
        with pytest.raises(ValueError, match=re.escape(str(captions_file))):
            load_captions(settings, repo_root=tmp_path)

    def test_rejects_a_non_string_value(self, tmp_path):
        """
        GIVEN a captions file whose object holds a non-string value
        WHEN load_captions runs
        THEN it raises ValueError naming the file's path
        """
        # GIVEN
        captions_file = tmp_path / "captions.json"
        captions_file.write_text(json.dumps({"c" * 64: 42}), encoding="utf-8")
        settings = Settings(
            secret_key="test-secret-key", assistant_captions_file=str(captions_file)
        )

        # WHEN / THEN
        with pytest.raises(ValueError, match=re.escape(str(captions_file))):
            load_captions(settings, repo_root=tmp_path)


class TestBuildCollectionRefusesAnUnmatchedCaptionsFile:
    """build_collection raises when a captions build's chunks match no caption at all.

    A partial miss (some chunks captioned, some not) still only warns - that path is
    unchanged and already covered by
    tests/integration/api/test_assistant_pipeline.py's TestBuildCollectionWithCaptions.
    """

    @pytest.mark.asyncio
    async def test_raises_when_no_chunk_matches_a_caption(self, tmp_path):
        """
        GIVEN a one-chunk corpus and a captions file with no entry for that chunk
        WHEN build_collection runs with context="captions"
        THEN it raises ValueError naming both counts - reached before build_collection
             ever needs an embedding server or a database, so a markdown_headers build
             (no embeddings call in split()) fails here with no network at all
        """
        # GIVEN
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "index.md").write_text(
            "# BeCoMe\n\nBeCoMe combines the arithmetic mean and the median.\n",
            encoding="utf-8",
        )
        captions_file = tmp_path / "captions.json"
        captions_file.write_text(json.dumps({"a" * 64: "Unrelated caption."}), encoding="utf-8")
        settings = Settings(
            secret_key="test-secret-key", assistant_captions_file=str(captions_file)
        )
        spec = CollectionSpec(
            name="docs_test_captions_all_missing",
            chunker=ChunkerConfig(strategy="markdown_headers", size=500, overlap_pct=10),
            context="captions",
            wave=1,
        )

        # WHEN / THEN
        with pytest.raises(ValueError, match="1 of 1 chunks"):
            await build_collection(spec, settings, repo_root=tmp_path)
