"""Unit tests for the retrieval eval's metrics (fakes only, no network)."""

import importlib.util
import sys
from pathlib import Path

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
