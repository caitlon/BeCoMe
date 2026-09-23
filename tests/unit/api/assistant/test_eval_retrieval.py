"""Unit tests for the retrieval eval's metrics (fakes only, no network)."""

import importlib.util
import sys
from pathlib import Path

import pytest

from api.assistant.rag.retrieval import RetrievedChunk

ROOT = Path(__file__).resolve().parents[4]


def _load():
    """Import the script by path, since `scripts/` is not a package.

    :return: The imported `eval_retrieval` module.
    """
    spec = importlib.util.spec_from_file_location(
        "eval_retrieval", ROOT / "scripts" / "assistant" / "eval_retrieval.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_retrieval"] = module
    spec.loader.exec_module(module)
    return module


ev = _load()


def _chunk(title: str) -> RetrievedChunk:
    """A RetrievedChunk with only the field the metrics care about (title)."""
    return RetrievedChunk(text="x", title=title, section="", url=None, layer="public", score=1.0)


class TestNdcgAt5:
    """nDCG@5 with binary relevance, verified against hand-computed values."""

    def test_all_relevant_is_perfect(self):
        """
        GIVEN five relevant results
        WHEN nDCG@5 scores them
        THEN it is exactly 1.0
        """
        assert ev._ndcg_at_5([1, 1, 1, 1, 1]) == 1.0

    def test_none_relevant_is_zero(self):
        """
        GIVEN no relevant results
        WHEN nDCG@5 scores them
        THEN it is exactly 0.0 (avoids dividing by zero)
        """
        assert ev._ndcg_at_5([0, 0, 0, 0, 0]) == 0.0

    def test_hit_at_the_top_is_perfect_regardless_of_the_rest(self):
        """
        GIVEN the only relevant result at rank 1
        WHEN nDCG@5 scores them
        THEN it is exactly 1.0 - rank 1 is where a single hit belongs
        """
        assert ev._ndcg_at_5([1, 0, 0, 0, 0]) == 1.0

    def test_hits_out_of_ideal_order_score_between_zero_and_one(self):
        """
        GIVEN hits at ranks 2 and 4 (0-indexed: 1 and 3)
        WHEN nDCG@5 scores them
        THEN it matches the hand-computed value for this exact relevance pattern
        """
        assert round(ev._ndcg_at_5([0, 1, 0, 1, 0]), 4) == 0.6509


class TestEvaluateQuery:
    """_evaluate_query turns one query's retrieved chunks into its metrics row."""

    def test_scores_a_query_whose_only_gold_source_is_the_top_result(self):
        """
        GIVEN a query whose top-ranked chunk is the gold source
        WHEN _evaluate_query scores it
        THEN hit@1/3/5 are all True, reciprocal_rank is 1.0, and nDCG@5 is 1.0
        """
        # GIVEN
        title_to_path = {"Reading the result": "docs/user/reading-the-result.md"}
        chunks = [_chunk("Reading the result"), _chunk("Getting started")]
        gold_paths = frozenset({"docs/user/reading-the-result.md"})

        # WHEN
        row = ev._evaluate_query(chunks, gold_paths, title_to_path)

        # THEN
        assert row["hit_at_1"] is True
        assert row["hit_at_3"] is True
        assert row["hit_at_5"] is True
        assert row["reciprocal_rank"] == 1.0
        assert row["ndcg_at_5"] == 1.0

    def test_scores_a_query_with_no_gold_source_retrieved(self):
        """
        GIVEN a query whose retrieved chunks never match its gold sources
        WHEN _evaluate_query scores it
        THEN every metric for that query is its zero value
        """
        # GIVEN
        title_to_path = {"Getting started": "docs/user/getting-started.md"}
        chunks = [_chunk("Getting started")]
        gold_paths = frozenset({"docs/user/reading-the-result.md"})

        # WHEN
        row = ev._evaluate_query(chunks, gold_paths, title_to_path)

        # THEN
        assert row["hit_at_1"] is False
        assert row["hit_at_3"] is False
        assert row["hit_at_5"] is False
        assert row["reciprocal_rank"] == 0.0
        assert row["ndcg_at_5"] == 0.0


class TestTitleToPath:
    """_title_to_path resolves a chunk's title back to the repo-relative path it came from."""

    def test_raises_on_a_duplicate_title_across_two_public_sources(self, tmp_path):
        """
        GIVEN two public markdown files under docs/ that share the same H1 title
        WHEN _title_to_path builds its title -> path mapping
        THEN it raises ValueError naming the duplicated title, rather than silently
             letting the second source's path overwrite the first's
        """
        # GIVEN
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "one.md").write_text("# Same Title\n\nFirst file.\n", encoding="utf-8")
        (docs_dir / "two.md").write_text("# Same Title\n\nSecond file.\n", encoding="utf-8")

        # WHEN / THEN
        with pytest.raises(ValueError, match="Same Title"):
            ev._title_to_path(tmp_path)


class TestEvaluateGuardsEmptyGoldenSet:
    """_evaluate refuses an empty golden set instead of dividing by zero."""

    @pytest.mark.asyncio
    async def test_raises_on_an_empty_golden_set(self):
        """
        GIVEN no golden-set entries
        WHEN _evaluate runs
        THEN it raises ValueError instead of dividing the per-query totals by zero
        """
        with pytest.raises(ValueError, match="empty"):
            await ev._evaluate([], None, {})


class TestRequireCollectionVersions:
    """_require_collection_versions turns a missing registry row into a clear failure."""

    def test_returns_the_row_when_one_exists(self):
        """
        GIVEN a registry row for the collection
        WHEN _require_collection_versions checks it
        THEN it returns the row unchanged
        """
        assert ev._require_collection_versions(("v1", "wave-1"), "docs_default") == (
            "v1",
            "wave-1",
        )

    def test_raises_a_clear_error_when_the_collection_has_no_registry_row(self):
        """
        GIVEN no registry row for the collection (row is None)
        WHEN _require_collection_versions checks it
        THEN it raises ValueError naming the collection, so a report is never written
             without a way to trace what corpus and app version produced it
        """
        with pytest.raises(ValueError, match="docs_default"):
            ev._require_collection_versions(None, "docs_default")


class TestFinalizeReport:
    """_finalize_report attaches the collection name and its registry versions."""

    def test_attaches_collection_name_and_versions(self):
        """
        GIVEN aggregated metrics, a collection name, and its registry versions
        WHEN _finalize_report merges them
        THEN the result carries the metrics plus collection/app_version/corpus_version
        """
        # GIVEN
        metrics = {"per_query": [], "hit_at_1": 1.0, "mrr": 1.0, "ndcg_at_5": 1.0}

        # WHEN
        report = ev._finalize_report(metrics, "docs_default", "v1.2.3", "wave-1-dirty")

        # THEN
        assert report["collection"] == "docs_default"
        assert report["app_version"] == "v1.2.3"
        assert report["corpus_version"] == "wave-1-dirty"
        assert report["hit_at_1"] == 1.0

    def test_keeps_a_none_corpus_version_as_none(self):
        """
        GIVEN a registry row where corpus_version is None (its corpus dir is not a git repo)
        WHEN _finalize_report merges it
        THEN corpus_version stays None in the report rather than being coerced
        """
        report = ev._finalize_report({}, "docs_default", "v1.2.3", None)
        assert report["corpus_version"] is None
