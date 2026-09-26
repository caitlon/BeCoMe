"""Unit tests for the captions-refresh CLI's commands (fakes only, no network, no
database - captions.py itself never needs either for "missing", and "merge" needs
neither for any strategy)."""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from langchain_core.documents import Document

from api.assistant.rag.enrich import chunk_key
from api.config import Settings

ROOT = Path(__file__).resolve().parents[4]


def _load():
    """Import the script by path, since `scripts/` is not a package.

    :return: The imported `captions` module.
    """
    spec = importlib.util.spec_from_file_location(
        "captions", ROOT / "scripts" / "assistant" / "captions.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["captions"] = module
    spec.loader.exec_module(module)
    return module


captions_cli = _load()


@pytest.fixture(autouse=True)
def _isolated_from_dotenv(tmp_path, monkeypatch):
    """Run each test where no .env exists, so Settings never sees a developer's real corpus."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ASSISTANT_PRIVATE_CORPUS_MANIFEST", raising=False)
    monkeypatch.delenv("ASSISTANT_PRIVATE_CORPUS_DIRS", raising=False)
    monkeypatch.delenv("ASSISTANT_CAPTIONS_FILE", raising=False)


class TestReadCaptionsOrEmpty:
    """_read_captions_or_empty treats a not-yet-written captions file as the first run."""

    def test_returns_empty_when_the_file_does_not_exist(self, tmp_path):
        """
        GIVEN a configured captions file that has never been written
        WHEN _read_captions_or_empty runs
        THEN it returns {} instead of raising FileNotFoundError
        """
        settings = Settings(
            secret_key="test-secret-key",  # pragma: allowlist secret
            assistant_captions_file=str(tmp_path / "does-not-exist.json"),
        )

        assert captions_cli._read_captions_or_empty(settings, repo_root=tmp_path) == {}

    def test_returns_the_files_contents_when_it_exists(self, tmp_path):
        """
        GIVEN a captions file that already holds an entry
        WHEN _read_captions_or_empty runs
        THEN it returns that entry, same as load_captions would
        """
        captions_path = tmp_path / "captions.json"
        captions_path.write_text(json.dumps({"a" * 64: "A caption."}), encoding="utf-8")
        settings = Settings(
            secret_key="test-secret-key", assistant_captions_file=str(captions_path)
        )

        captions = captions_cli._read_captions_or_empty(settings, repo_root=tmp_path)

        assert captions == {"a" * 64: "A caption."}


class TestCaptionsPayload:
    """_captions_payload validates a merge FILE: a JSON object of non-empty strings."""

    def test_parses_a_valid_object(self, tmp_path):
        """
        GIVEN a file holding a JSON object of non-empty strings
        WHEN _captions_payload parses it
        THEN it returns that mapping unchanged
        """
        path = tmp_path / "batch.json"
        path.write_text(json.dumps({"a" * 64: "A caption."}), encoding="utf-8")

        assert captions_cli._captions_payload(str(path)) == {"a" * 64: "A caption."}

    def test_rejects_a_json_array(self, tmp_path):
        """
        GIVEN a file holding a JSON array instead of an object
        WHEN _captions_payload parses it
        THEN it raises ArgumentTypeError, so argparse stops with a usage error
        """
        path = tmp_path / "batch.json"
        path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

        with pytest.raises(argparse.ArgumentTypeError, match="JSON object"):
            captions_cli._captions_payload(str(path))

    def test_rejects_an_empty_caption(self, tmp_path):
        """
        GIVEN a file whose object holds an empty-string caption
        WHEN _captions_payload parses it
        THEN it raises ArgumentTypeError naming that key
        """
        path = tmp_path / "batch.json"
        path.write_text(json.dumps({"a" * 64: ""}), encoding="utf-8")

        with pytest.raises(argparse.ArgumentTypeError, match="non-empty string"):
            captions_cli._captions_payload(str(path))

    def test_rejects_a_non_string_caption(self, tmp_path):
        """
        GIVEN a file whose object holds a non-string caption value
        WHEN _captions_payload parses it
        THEN it raises ArgumentTypeError naming that key
        """
        path = tmp_path / "batch.json"
        path.write_text(json.dumps({"a" * 64: 42}), encoding="utf-8")

        with pytest.raises(argparse.ArgumentTypeError, match="non-empty string"):
            captions_cli._captions_payload(str(path))

    def test_rejects_invalid_json(self, tmp_path):
        """
        GIVEN a file that is not valid JSON at all
        WHEN _captions_payload parses it
        THEN it raises ArgumentTypeError instead of letting json.JSONDecodeError escape
        """
        path = tmp_path / "batch.json"
        path.write_text("not json at all", encoding="utf-8")

        with pytest.raises(argparse.ArgumentTypeError):
            captions_cli._captions_payload(str(path))


class TestMergeCaptions:
    """_merge_captions folds new captions into the existing mapping, counting each."""

    def test_adds_a_new_key(self):
        """
        GIVEN one new caption and no existing captions
        WHEN _merge_captions merges them
        THEN the key is added, counted as added rather than replaced
        """
        merged, added, replaced = captions_cli._merge_captions({"new-key": "A caption."}, {})

        assert merged == {"new-key": "A caption."}
        assert (added, replaced) == (1, 0)

    def test_replaces_an_existing_key(self):
        """
        GIVEN a new caption for a key that already has one
        WHEN _merge_captions merges them
        THEN the value is overwritten, counted as replaced rather than added
        """
        merged, added, replaced = captions_cli._merge_captions(
            {"key": "New caption."}, {"key": "Old caption."}
        )

        assert merged == {"key": "New caption."}
        assert (added, replaced) == (0, 1)

    def test_counts_additions_and_replacements_separately_in_one_merge(self):
        """
        GIVEN a merge with one new key and one key that already exists
        WHEN _merge_captions merges them
        THEN added and replaced are counted separately, and an untouched key survives
        """
        merged, added, replaced = captions_cli._merge_captions(
            {"existing": "New.", "fresh": "Brand new."},
            {"existing": "Old.", "untouched": "Kept."},
        )

        assert merged == {"existing": "New.", "fresh": "Brand new.", "untouched": "Kept."}
        assert (added, replaced) == (1, 1)


class TestRunMerge:
    """_run_merge writes the merged captions file and reports the counts."""

    def test_creates_the_file_when_it_does_not_exist_yet(self, tmp_path, capsys):
        """
        GIVEN a configured captions file that has never been written
        WHEN _run_merge runs with one new caption
        THEN it creates the file holding that caption and reports added=1, replaced=0
        """
        captions_path = tmp_path / "captions.json"
        settings = Settings(
            secret_key="test-secret-key", assistant_captions_file=str(captions_path)
        )

        captions_cli._run_merge({"a" * 64: "First caption."}, settings, repo_root=tmp_path)

        assert json.loads(captions_path.read_text(encoding="utf-8")) == {"a" * 64: "First caption."}
        assert capsys.readouterr().out.strip() == "added 1, replaced 0, total 1"

    def test_merges_into_an_existing_file_sorted_with_diacritics_preserved(self, tmp_path, capsys):
        """
        GIVEN an existing captions file, and a merge that both replaces one of its
             entries and adds a new one with non-ASCII text
        WHEN _run_merge runs
        THEN the file ends up sorted by key, with the diacritics left as literal
             characters rather than \\uXXXX escapes, and the counts are reported
        """
        captions_path = tmp_path / "captions.json"
        captions_path.write_text(json.dumps({"b" * 64: "Existing caption."}), encoding="utf-8")
        settings = Settings(
            secret_key="test-secret-key", assistant_captions_file=str(captions_path)
        )

        captions_cli._run_merge(
            {"b" * 64: "Updated caption.", "a" * 64: "Nová caption s háčky."},
            settings,
            repo_root=tmp_path,
        )

        raw = captions_path.read_text(encoding="utf-8")
        assert json.loads(raw) == {
            "a" * 64: "Nová caption s háčky.",
            "b" * 64: "Updated caption.",
        }
        assert "\\u" not in raw
        assert raw.startswith('{\n "')
        assert raw.index(f'"{"a" * 64}"') < raw.index(f'"{"b" * 64}"')
        assert capsys.readouterr().out.strip() == "added 1, replaced 1, total 2"


class TestRunMissing:
    """_run_missing reports the count and exports only documents with a caption gap."""

    def test_prints_the_count_and_exports_only_the_document_with_a_gap(
        self, tmp_path, capsys, monkeypatch
    ):
        """
        GIVEN load_corpus substituted for two documents, one of which is fully captioned
        WHEN _run_missing runs with --out set
        THEN it prints the overall count and writes only the uncaptioned document's
             entry, holding only its uncaptioned chunk
        """
        # GIVEN
        doc_a = Document(
            page_content="First document text, all captioned.",
            metadata={"title": "Doc A", "layer": "public"},
        )
        doc_b = Document(
            page_content="Second document text, still needs a caption.",
            metadata={"title": "Doc B", "layer": "local"},
        )
        monkeypatch.setattr(
            captions_cli, "load_corpus", lambda settings, repo_root, wave: [doc_a, doc_b]
        )
        captions_path = tmp_path / "captions.json"
        captions_path.write_text(
            json.dumps({chunk_key(doc_a.page_content): "Caption for A."}), encoding="utf-8"
        )
        settings = Settings(
            secret_key="test-secret-key", assistant_captions_file=str(captions_path)
        )
        out_path = tmp_path / "batch.json"
        args = argparse.Namespace(
            strategy="fixed", size=500, overlap_pct=10, wave=1, out=str(out_path)
        )

        # WHEN
        captions_cli._run_missing(args, settings, repo_root=tmp_path)

        # THEN
        assert (
            capsys.readouterr().out.strip()
            == "1 of 2 chunks have no caption; 0 captions match no chunk"
        )
        batch = json.loads(out_path.read_text(encoding="utf-8"))
        assert batch == [
            {
                "title": "Doc B",
                "layer": "local",
                "document": doc_b.page_content,
                "chunks": [{"sha": chunk_key(doc_b.page_content), "text": doc_b.page_content}],
            }
        ]

    def test_without_out_writes_nothing(self, tmp_path, capsys, monkeypatch):
        """
        GIVEN the same kind of substituted load_corpus, but no --out given
        WHEN _run_missing runs
        THEN it only prints the count; no file is written
        """
        # GIVEN
        doc = Document(page_content="Solo document.", metadata={"title": "Doc", "layer": "public"})
        monkeypatch.setattr(captions_cli, "load_corpus", lambda settings, repo_root, wave: [doc])
        captions_path = tmp_path / "captions.json"
        captions_path.write_text(json.dumps({}), encoding="utf-8")
        settings = Settings(
            secret_key="test-secret-key", assistant_captions_file=str(captions_path)
        )
        args = argparse.Namespace(strategy="fixed", size=500, overlap_pct=10, wave=1, out=None)

        # WHEN
        captions_cli._run_missing(args, settings, repo_root=tmp_path)

        # THEN
        assert (
            capsys.readouterr().out.strip()
            == "1 of 1 chunks have no caption; 0 captions match no chunk"
        )
        assert list(tmp_path.iterdir()) == [captions_path]

    def test_does_not_build_an_embeddings_client_for_a_non_semantic_strategy(
        self, tmp_path, capsys, monkeypatch
    ):
        """
        GIVEN a non-semantic strategy and load_corpus substituted for one document
        WHEN _run_missing runs
        THEN it never calls make_embeddings, so no embedding server is required
        """
        # GIVEN
        doc = Document(page_content="Solo document.", metadata={"title": "Doc", "layer": "public"})
        monkeypatch.setattr(captions_cli, "load_corpus", lambda settings, repo_root, wave: [doc])

        def _fail_if_called(settings):
            raise AssertionError("make_embeddings must not be called for strategy='fixed'")

        monkeypatch.setattr(captions_cli, "make_embeddings", _fail_if_called)
        captions_path = tmp_path / "captions.json"
        captions_path.write_text(json.dumps({}), encoding="utf-8")
        settings = Settings(
            secret_key="test-secret-key", assistant_captions_file=str(captions_path)
        )
        args = argparse.Namespace(strategy="fixed", size=500, overlap_pct=10, wave=1, out=None)

        # WHEN / THEN: no AssertionError means make_embeddings was never called
        captions_cli._run_missing(args, settings, repo_root=tmp_path)
        assert (
            capsys.readouterr().out.strip()
            == "1 of 1 chunks have no caption; 0 captions match no chunk"
        )

    def test_prints_how_many_captions_match_no_chunk(self, tmp_path, capsys, monkeypatch):
        """
        GIVEN a captions file with one entry for the corpus's only chunk and one entry
             that matches no chunk at all
        WHEN _run_missing runs
        THEN it reports that stale count alongside the missing/total counts
        """
        # GIVEN
        doc = Document(page_content="Solo document.", metadata={"title": "Doc", "layer": "public"})
        monkeypatch.setattr(captions_cli, "load_corpus", lambda settings, repo_root, wave: [doc])
        captions_path = tmp_path / "captions.json"
        captions_path.write_text(
            json.dumps(
                {chunk_key(doc.page_content): "Current caption.", "stale-key": "Orphan caption."}
            ),
            encoding="utf-8",
        )
        settings = Settings(
            secret_key="test-secret-key", assistant_captions_file=str(captions_path)
        )
        args = argparse.Namespace(strategy="fixed", size=500, overlap_pct=10, wave=1, out=None)

        # WHEN
        captions_cli._run_missing(args, settings, repo_root=tmp_path)

        # THEN
        assert (
            capsys.readouterr().out.strip()
            == "0 of 1 chunks have no caption; 1 captions match no chunk"
        )


class TestRunPrune:
    """_run_prune drops captions whose chunk no longer exists in the corpus."""

    def test_removes_the_stale_key_and_keeps_the_current_one(self, tmp_path, capsys, monkeypatch):
        """
        GIVEN a captions file with one entry matching the corpus's only chunk and one
             entry that matches no chunk
        WHEN _run_prune runs
        THEN it rewrites the file holding only the matching entry, in merge's format,
             and reports removed 1, kept 1
        """
        # GIVEN
        doc = Document(page_content="Solo document.", metadata={"title": "Doc", "layer": "public"})
        monkeypatch.setattr(captions_cli, "load_corpus", lambda settings, repo_root, wave: [doc])
        current_key = chunk_key(doc.page_content)
        captions_path = tmp_path / "captions.json"
        captions_path.write_text(
            json.dumps({current_key: "Current caption.", "stale-key": "Orphan caption."}),
            encoding="utf-8",
        )
        settings = Settings(
            secret_key="test-secret-key", assistant_captions_file=str(captions_path)
        )
        args = argparse.Namespace(strategy="fixed", size=500, overlap_pct=10, wave=1)

        # WHEN
        captions_cli._run_prune(args, settings, repo_root=tmp_path)

        # THEN
        assert capsys.readouterr().out.strip() == "removed 1, kept 1"
        raw = captions_path.read_text(encoding="utf-8")
        assert json.loads(raw) == {current_key: "Current caption."}
        assert raw == json.dumps(
            {current_key: "Current caption."}, sort_keys=True, ensure_ascii=False, indent=1
        )

    def test_writes_nothing_when_no_caption_is_stale(self, tmp_path, capsys, monkeypatch):
        """
        GIVEN a captions file whose only entry matches the corpus's only chunk
        WHEN _run_prune runs
        THEN it reports removed 0, kept 1 and leaves the file's bytes untouched
        """
        # GIVEN
        doc = Document(page_content="Solo document.", metadata={"title": "Doc", "layer": "public"})
        monkeypatch.setattr(captions_cli, "load_corpus", lambda settings, repo_root, wave: [doc])
        current_key = chunk_key(doc.page_content)
        captions_path = tmp_path / "captions.json"
        original = json.dumps({current_key: "Current caption."})
        captions_path.write_text(original, encoding="utf-8")
        settings = Settings(
            secret_key="test-secret-key", assistant_captions_file=str(captions_path)
        )
        args = argparse.Namespace(strategy="fixed", size=500, overlap_pct=10, wave=1)

        # WHEN
        captions_cli._run_prune(args, settings, repo_root=tmp_path)

        # THEN
        assert capsys.readouterr().out.strip() == "removed 0, kept 1"
        assert captions_path.read_text(encoding="utf-8") == original


class TestMain:
    """_main resolves the captions path before any corpus work, for every command."""

    def test_missing_exits_before_the_corpus_loads_when_unset(self, monkeypatch):
        """
        GIVEN no ASSISTANT_CAPTIONS_FILE configured
        WHEN _main runs the `missing` command
        THEN it raises SystemExit naming ASSISTANT_CAPTIONS_FILE, and load_corpus is
             never called
        """
        # GIVEN
        monkeypatch.setattr(
            captions_cli,
            "_parse_args",
            lambda: argparse.Namespace(
                command="missing", strategy="fixed", size=500, overlap_pct=10, wave=1, out=None
            ),
        )
        monkeypatch.setattr(
            captions_cli, "get_settings", lambda: Settings(secret_key="test-secret-key")
        )

        def _fail_if_called(settings, repo_root, wave):
            raise AssertionError("load_corpus must not run before the captions setting is checked")

        monkeypatch.setattr(captions_cli, "load_corpus", _fail_if_called)

        # WHEN / THEN
        with pytest.raises(SystemExit, match="ASSISTANT_CAPTIONS_FILE"):
            captions_cli._main()

    def test_merge_exits_before_touching_the_file_when_unset(self, monkeypatch):
        """
        GIVEN no ASSISTANT_CAPTIONS_FILE configured
        WHEN _main runs the `merge` command
        THEN it raises SystemExit naming ASSISTANT_CAPTIONS_FILE
        """
        # GIVEN
        monkeypatch.setattr(
            captions_cli, "_parse_args", lambda: argparse.Namespace(command="merge", file={})
        )
        monkeypatch.setattr(
            captions_cli, "get_settings", lambda: Settings(secret_key="test-secret-key")
        )

        # WHEN / THEN
        with pytest.raises(SystemExit, match="ASSISTANT_CAPTIONS_FILE"):
            captions_cli._main()
