"""Unit tests for pipeline.py's load_captions(): the captions-file reader the
"captions" context mode needs (fakes only, no network, no database)."""

import json
import re

import pytest

from api.assistant.rag.pipeline import load_captions
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
