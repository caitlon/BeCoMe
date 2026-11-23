"""Unit tests for the retrieval eval's metrics (fakes only, no network)."""

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

from api.assistant.rag.retrieval import RetrievalConfig, RetrievedChunk

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
    return RetrievedChunk(
        text="x", title=title, section="", url=None, layer="public", score=1.0, chunk_text="x"
    )


class TestNdcgAt5:
    """nDCG@5 with binary relevance, verified against hand-computed values."""

    def test_all_gold_sources_at_the_top_is_perfect(self):
        """
        GIVEN five gold sources, each retrieved at its own rank 1-5
        WHEN nDCG@5 scores them
        THEN it is exactly 1.0
        """
        assert ev._ndcg_at_5([1, 1, 1, 1, 1], 5) == 1.0

    def test_none_relevant_is_zero(self):
        """
        GIVEN no relevant results
        WHEN nDCG@5 scores them
        THEN it is exactly 0.0
        """
        assert ev._ndcg_at_5([0, 0, 0, 0, 0], 2) == 0.0

    def test_no_gold_sources_is_zero(self):
        """
        GIVEN a query with no gold sources
        WHEN nDCG@5 scores it
        THEN it is exactly 0.0 (avoids dividing by zero)
        """
        assert ev._ndcg_at_5([0, 0, 0, 0, 0], 0) == 0.0

    def test_single_gold_source_at_the_top_is_perfect(self):
        """
        GIVEN the only gold source retrieved at rank 1
        WHEN nDCG@5 scores it
        THEN it is exactly 1.0 - rank 1 is where a single hit belongs
        """
        assert ev._ndcg_at_5([1, 0, 0, 0, 0], 1) == 1.0

    def test_hits_out_of_ideal_order_score_between_zero_and_one(self):
        """
        GIVEN two gold sources retrieved at ranks 2 and 4
        WHEN nDCG@5 scores them
        THEN it matches the hand-computed (1/log2(3) + 1/log2(5)) / (1 + 1/log2(3))
        """
        assert round(ev._ndcg_at_5([0, 1, 0, 1, 0], 2), 4) == 0.6509

    def test_ideal_is_capped_at_five_results(self):
        """
        GIVEN seven gold sources and five of them retrieved at ranks 1-5
        WHEN nDCG@5 scores them
        THEN it is 1.0, because only five results fit in the top five
        """
        assert ev._ndcg_at_5([1, 1, 1, 1, 1], 7) == 1.0


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

    def test_one_of_two_gold_sources_at_rank_one_is_not_perfect(self):
        """
        GIVEN a query with two gold sources of which only one is retrieved, at rank 1
        WHEN _evaluate_query scores it
        THEN nDCG@5 is 1 / (1 + 1/log2(3)) = 0.6131, not 1.0
        """
        # GIVEN
        title_to_path = {"A": "docs/a.md", "B": "docs/b.md", "Other": "docs/other.md"}
        chunks = [_chunk("A"), _chunk("Other")]
        gold_paths = frozenset({"docs/a.md", "docs/b.md"})

        # WHEN
        row = ev._evaluate_query(chunks, gold_paths, title_to_path)

        # THEN
        assert round(row["ndcg_at_5"], 4) == 0.6131

    def test_repeated_chunks_of_one_gold_source_are_credited_once(self):
        """
        GIVEN three gold sources and five retrieved chunks that all come from one of them
        WHEN _evaluate_query scores it
        THEN nDCG@5 is 1 / (1 + 1/log2(3) + 1/log2(4)) = 0.4693, and hit@k and
            reciprocal_rank are unchanged by the deduplication
        """
        # GIVEN
        title_to_path = {
            "A": "docs/a.md",
            "B": "docs/b.md",
            "C": "docs/c.md",
        }
        chunks = [_chunk("A")] * 5
        gold_paths = frozenset({"docs/a.md", "docs/b.md", "docs/c.md"})

        # WHEN
        row = ev._evaluate_query(chunks, gold_paths, title_to_path)

        # THEN
        assert round(row["ndcg_at_5"], 4) == 0.4693
        assert row["hit_at_1"] is True
        assert row["hit_at_3"] is True
        assert row["hit_at_5"] is True
        assert row["reciprocal_rank"] == 1.0

    def test_two_titles_of_one_gold_source_are_credited_once(self):
        """
        GIVEN two gold sources and two chunks with different titles that map to the
            same gold path, followed by three chunks from a non-gold path
        WHEN _evaluate_query scores it
        THEN only the first chunk counts: nDCG@5 is 1 / (1 + 1/log2(3)) = 0.6131,
            hit@1 is True and reciprocal_rank is 1.0
        """
        # GIVEN
        title_to_path = {"A1": "docs/a.md", "A2": "docs/a.md", "X": "docs/x.md"}
        chunks = [_chunk("A1"), _chunk("A2"), _chunk("X"), _chunk("X"), _chunk("X")]
        gold_paths = frozenset({"docs/a.md", "docs/b.md"})

        # WHEN
        row = ev._evaluate_query(chunks, gold_paths, title_to_path)

        # THEN
        assert round(row["ndcg_at_5"], 4) == 0.6131
        assert row["hit_at_1"] is True
        assert row["reciprocal_rank"] == 1.0

    def test_a_gold_source_below_rank_five_does_not_count(self):
        """
        GIVEN one gold source retrieved only at rank 6, after five non-gold chunks
        WHEN _evaluate_query scores it
        THEN nDCG@5 is 0.0 and hit@5 is False
        """
        # GIVEN
        title_to_path = {f"X{i}": f"docs/x{i}.md" for i in range(5)} | {"A": "docs/a.md"}
        chunks = [_chunk(f"X{i}") for i in range(5)] + [_chunk("A")]
        gold_paths = frozenset({"docs/a.md"})

        # WHEN
        row = ev._evaluate_query(chunks, gold_paths, title_to_path)

        # THEN
        assert row["ndcg_at_5"] == 0.0
        assert row["hit_at_5"] is False

    def test_a_second_gold_source_never_lowers_the_score(self):
        """
        GIVEN two gold sources, one run retrieving only A at rank 1 and another
            retrieving A at rank 1 and B at rank 3
        WHEN _evaluate_query scores both
        THEN the run that also finds B scores (1 + 1/log2(4)) / (1 + 1/log2(3)) = 0.9197,
            above the single-hit run at 0.6131
        """
        # GIVEN
        title_to_path = {"A": "docs/a.md", "B": "docs/b.md", "Other": "docs/other.md"}
        gold_paths = frozenset({"docs/a.md", "docs/b.md"})
        single = [_chunk("A"), _chunk("Other"), _chunk("Other")]
        both = [_chunk("A"), _chunk("Other"), _chunk("B")]

        # WHEN
        single_row = ev._evaluate_query(single, gold_paths, title_to_path)
        both_row = ev._evaluate_query(both, gold_paths, title_to_path)

        # THEN
        assert round(single_row["ndcg_at_5"], 4) == 0.6131
        assert round(both_row["ndcg_at_5"], 4) == 0.9197
        assert both_row["ndcg_at_5"] > single_row["ndcg_at_5"]


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
    """_finalize_report attaches the collection, its versions, and the retrieval settings."""

    def test_attaches_collection_name_and_versions(self):
        """
        GIVEN aggregated metrics, a collection name, its registry versions, and the
             retrieval config that produced them
        WHEN _finalize_report merges them
        THEN the result carries the metrics plus collection/app_version/corpus_version
        """
        # GIVEN
        metrics = {"per_query": [], "hit_at_1": 1.0, "mrr": 1.0, "ndcg_at_5": 1.0}
        config = RetrievalConfig(mode="dense", k=5, rerank=False, query_transform="none")

        # WHEN
        report = ev._finalize_report(metrics, "docs_default", "v1.2.3", "wave-1-dirty", config)

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
        config = RetrievalConfig(mode="dense", k=5, rerank=False, query_transform="none")
        report = ev._finalize_report({}, "docs_default", "v1.2.3", None, config)
        assert report["corpus_version"] is None

    def test_records_the_retrieval_settings_next_to_the_versions(self):
        """
        GIVEN a retrieval config with a non-default mode, rerank, query_transform, and k
        WHEN _finalize_report merges it into the report
        THEN the report carries all four settings, so two reports of the same
             collection measured under different settings can be told apart
        """
        config = RetrievalConfig(mode="bm25", k=3, rerank=True, query_transform="hyde")

        report = ev._finalize_report({}, "docs_default", "v1.2.3", "wave-1", config)

        assert report["mode"] == "bm25"
        assert report["rerank"] is True
        assert report["query_transform"] == "hyde"
        assert report["k"] == 3


class TestBuildRetrievalConfig:
    """_build_retrieval_config turns parsed CLI arguments into a RetrievalConfig."""

    def test_builds_a_dense_config_with_defaults(self):
        """
        GIVEN parsed arguments with no rerank flag and query_transform="none"
        WHEN _build_retrieval_config converts them
        THEN the resulting RetrievalConfig matches every field
        """
        args = argparse.Namespace(mode="dense", rerank=False, query_transform="none", k=5)

        config = ev._build_retrieval_config(args)

        assert config == ev.RetrievalConfig(mode="dense", k=5, rerank=False, query_transform="none")

    def test_builds_a_hybrid_reranked_config(self):
        """
        GIVEN parsed arguments requesting hybrid mode with reranking on
        WHEN _build_retrieval_config converts them
        THEN rerank is True and mode is "hybrid" in the resulting RetrievalConfig
        """
        args = argparse.Namespace(mode="hybrid", rerank=True, query_transform="hyde", k=3)

        config = ev._build_retrieval_config(args)

        assert config == ev.RetrievalConfig(mode="hybrid", k=3, rerank=True, query_transform="hyde")


class TestPositiveInt:
    """--k accepts only a whole number of at least one."""

    def test_accepts_a_positive_whole_number(self):
        """
        GIVEN the text "3"
        WHEN _positive_int parses it
        THEN it returns the integer 3
        """
        assert ev._positive_int("3") == 3

    @pytest.mark.parametrize("text", ["0", "-1", "2.5", "five"])
    def test_rejects_anything_else(self, text):
        """
        GIVEN zero, a negative number, a fraction, or a word
        WHEN _positive_int parses it
        THEN it raises ArgumentTypeError, so argparse stops with a usage error instead of
             writing a report in which k=0 made every query look like a miss
        """
        with pytest.raises(argparse.ArgumentTypeError):
            ev._positive_int(text)
