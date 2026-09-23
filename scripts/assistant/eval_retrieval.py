#!/usr/bin/env python3
"""Retrieval-quality eval: hit@1/3/5, MRR, and nDCG@5 over the golden set.

Answers the retrieval-only half of the golden set (scripts/assistant/golden_set.jsonl):
does search find a chunk from the right document at all, regardless of what an LLM
would eventually say about it. The answer evaluation adds the answer-quality half
(fact/citation grading, LangSmith experiments) on top of a running assistant.

    uv run python scripts/assistant/eval_retrieval.py --collection docs_default

Needs the "assistant" extra and a running embedding llama-server.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.assistant.rag.corpus import build_manifest
from api.assistant.rag.models import make_embeddings
from api.assistant.rag.retrieval import DocsRetriever, RetrievalConfig, RetrievedChunk
from api.assistant.rag.store import make_engine, open_store
from api.config import get_settings


def _title_to_path(repo_root: Path) -> dict[str, str]:
    """Map each public corpus source's title to its repo-relative path.

    RetrievedChunk carries a title, not a path (contract, retrieval.py); this is the
    one place that resolves a chunk back to the file a golden-set entry names.

    :param repo_root: Repository root.
    :return: {title: repo-relative path}, public layer only (the golden set's
        questions are all answerable from public docs).
    """
    sources = build_manifest(repo_root=repo_root, private_dirs=[])
    return {
        source.title: source.path.relative_to(repo_root).as_posix()
        for source in sources
        if source.layer == "public"
    }


def _load_golden_set(path: Path) -> list[dict[str, Any]]:
    """Read the golden set JSONL into plain dicts (one per non-blank line).

    :param path: Path to golden_set.jsonl.
    :return: One dict per entry, in file order.
    """
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _dcg(relevances: list[int]) -> float:
    """Discounted cumulative gain over a binary relevance sequence, rank 1 first.

    :param relevances: 1 where a result is relevant, 0 otherwise, in rank order.
    :return: The DCG value.
    """
    return sum(rel / math.log2(rank + 2) for rank, rel in enumerate(relevances))


def _ndcg_at_5(relevances: list[int]) -> float:
    """Normalized DCG at 5: DCG divided by the best possible DCG for this many hits.

    :param relevances: 1 where a result is relevant, 0 otherwise, in rank order.
    :return: 0.0 if there are no relevant results at all (no ideal DCG to divide by).
    """
    top5 = relevances[:5]
    ideal = _dcg(sorted(top5, reverse=True))
    return _dcg(top5) / ideal if ideal > 0 else 0.0


def _evaluate_query(
    chunks: list[RetrievedChunk], gold_paths: frozenset[str], title_to_path: dict[str, str]
) -> dict[str, bool | float]:
    """Score one query's retrieved chunks against its gold sources.

    A chunk counts as relevant when the path its title resolves to is one of the
    query's gold sources - section-level precision is for a human reading the golden
    set, not a criterion this scoring enforces.

    :param chunks: DocsRetriever.search()'s result, most relevant first.
    :param gold_paths: The repo-relative paths this query should have retrieved.
    :param title_to_path: _title_to_path()'s mapping, for resolving chunk.title.
    :return: hit_at_1/3/5 (bool), reciprocal_rank and ndcg_at_5 (float).
    """
    relevances = [1 if title_to_path.get(chunk.title) in gold_paths else 0 for chunk in chunks]
    first_hit_rank = next((rank + 1 for rank, rel in enumerate(relevances) if rel), None)
    return {
        "hit_at_1": bool(relevances[:1] and relevances[0]),
        "hit_at_3": any(relevances[:3]),
        "hit_at_5": any(relevances[:5]),
        "reciprocal_rank": 1.0 / first_hit_rank if first_hit_rank else 0.0,
        "ndcg_at_5": _ndcg_at_5(relevances),
    }


async def _evaluate(
    entries: list[dict[str, Any]], retriever: DocsRetriever, title_to_path: dict[str, str]
) -> dict[str, Any]:
    """Run every golden-set entry through the retriever and aggregate the metrics.

    :param entries: Parsed golden-set rows (_load_golden_set).
    :param retriever: The DocsRetriever to evaluate.
    :param title_to_path: _title_to_path()'s mapping.
    :return: {"per_query": [...], "hit_at_1": ..., "hit_at_3": ..., "hit_at_5": ...,
        "mrr": ..., "ndcg_at_5": ...} - the last five averaged over all entries.
    """
    per_query = []
    for entry in entries:
        gold_paths = frozenset(source["path"] for source in entry["gold_sources"])
        chunks = await retriever.search(entry["question"])
        row = _evaluate_query(chunks, gold_paths, title_to_path)
        per_query.append(
            {"id": entry["id"], "category": entry["category"], "lang": entry["lang"], **row}
        )
    count = len(per_query)
    return {
        "per_query": per_query,
        "hit_at_1": sum(row["hit_at_1"] for row in per_query) / count,
        "hit_at_3": sum(row["hit_at_3"] for row in per_query) / count,
        "hit_at_5": sum(row["hit_at_5"] for row in per_query) / count,
        "mrr": sum(row["reciprocal_rank"] for row in per_query) / count,
        "ndcg_at_5": sum(row["ndcg_at_5"] for row in per_query) / count,
    }


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for one retrieval eval run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", required=True, help="Collection table name to evaluate")
    parser.add_argument(
        "--golden-set",
        default=None,
        help="Path to the golden set JSONL (default: scripts/assistant/golden_set.jsonl)",
    )
    return parser.parse_args()


async def _main() -> None:
    """Evaluate one collection against the golden set and write a JSON report."""
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    golden_set_path = (
        Path(args.golden_set)
        if args.golden_set
        else repo_root / "scripts" / "assistant" / "golden_set.jsonl"
    )
    entries = _load_golden_set(golden_set_path)
    title_to_path = _title_to_path(repo_root)

    settings = get_settings()
    embeddings = make_embeddings(settings)
    engine = make_engine(settings.assistant_vector_db_url)
    try:
        store = open_store(engine, table=args.collection, embeddings=embeddings)
        retriever = DocsRetriever(
            store=store, config=RetrievalConfig(mode="dense", k=5), reranker=None, llm=None
        )
        report = await _evaluate(entries, retriever, title_to_path)
    finally:
        await engine.close()

    report["collection"] = args.collection
    report["generated_at"] = datetime.now(UTC).isoformat()
    out_dir = repo_root / "supplementary" / "assistant-eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.collection}-{report['generated_at'].replace(':', '-')}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"hit@1={report['hit_at_1']:.2f} hit@3={report['hit_at_3']:.2f} "
        f"hit@5={report['hit_at_5']:.2f} MRR={report['mrr']:.2f} nDCG@5={report['ndcg_at_5']:.2f}"
    )
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    asyncio.run(_main())
