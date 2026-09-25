#!/usr/bin/env python3
"""Retrieval-quality eval: hit@1/3/5, MRR, and nDCG@5 over the golden set.

Answers the retrieval-only half of the golden set (scripts/assistant/golden_set.jsonl):
does search find a chunk from the right document at all, regardless of what an LLM
would eventually say about it. The answer evaluation adds the answer-quality half
(fact/citation grading, LangSmith experiments) on top of a running assistant.

    uv run python scripts/assistant/eval_retrieval.py \\
        --collection docs_markdown_headers_500_o10_captions_bge_m3

Needs the "assistant" extra and a running embedding llama-server. --rerank also needs
the reranker llama-server, and a query transform needs the chat llama-server.
scripts/assistant/run-llama-servers.sh starts all three.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.errors import UndefinedTable

from api.assistant.rag.corpus import build_manifest
from api.assistant.rag.models import LlamaServerReranker, make_chat_model, make_embeddings
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
    :raises ValueError: If two public sources share the same title - this mapping
        could then not tell which path a chunk with that title actually came from.
    """
    sources = build_manifest(repo_root=repo_root, private_dirs=[])
    title_to_path: dict[str, str] = {}
    for source in sources:
        if source.layer != "public":
            continue
        path = source.path.relative_to(repo_root).as_posix()
        if source.title in title_to_path:
            raise ValueError(
                f"two public corpus sources share the title {source.title!r} "
                f"({title_to_path[source.title]} and {path}); give one of them a "
                "distinct heading"
            )
        title_to_path[source.title] = path
    return title_to_path


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
    :raises ValueError: If entries is empty (an empty or blank golden set) - there
        would be nothing to average, and dividing by the query count would otherwise
        raise ZeroDivisionError instead of a message that says what is actually wrong.
    """
    if not entries:
        raise ValueError("the golden set is empty; nothing to evaluate")
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


async def _fetch_collection_row(
    vector_db_url: str, name: str
) -> tuple[str | None, str | None] | None:
    """Read one collection's app/corpus version from the assistant_collections registry.

    Uses its own connection, the same pattern pipeline.py's _record_collection uses,
    rather than the langchain PGEngine pool: assistant_collections is a plain table the
    ingest pipeline manages directly, outside langchain-postgres.

    :param vector_db_url: Settings.assistant_vector_db_url.
    :param name: The collection's table name (assistant_collections.name).
    :return: (app_version, corpus_version) for that collection, or None when there is
        no registry row for it - either the table has never been created (nothing has
        been ingested anywhere yet), or this particular collection was never recorded.
    """
    dsn = vector_db_url.replace("postgresql+psycopg://", "postgresql://")
    async with await psycopg.AsyncConnection.connect(dsn) as conn:
        try:
            cursor = await conn.execute(
                "SELECT app_version, corpus_version FROM assistant_collections WHERE name = %s",
                (name,),
            )
        except UndefinedTable:
            return None
        row = await cursor.fetchone()
    return (row[0], row[1]) if row is not None else None


def _require_collection_versions(
    row: tuple[str | None, str | None] | None, name: str
) -> tuple[str | None, str | None]:
    """Fail loudly on a missing registry row, instead of writing an untraceable report.

    :param row: _fetch_collection_row()'s result.
    :param name: The collection name, for the error message.
    :return: row, unwrapped.
    :raises ValueError: If row is None - a report with no app_version or corpus_version
        cannot be traced back to what corpus and application code produced it, which is
        the reason assistant_collections records them in the first place (pipeline.py).
    """
    if row is None:
        raise ValueError(
            f"no assistant_collections registry row for collection {name!r}; run the "
            "ingest CLI for it first, so this report can be traced to an app and corpus "
            "version"
        )
    return row


def _finalize_report(
    metrics: dict[str, Any],
    collection: str,
    app_version: str | None,
    corpus_version: str | None,
    config: RetrievalConfig,
) -> dict[str, Any]:
    """Attach the collection, its registry versions, and the retrieval settings used.

    Kept pure and separate from _fetch_collection_row, so the report shape (what every
    measured number must carry, per the plan's global constraint) is unit-testable
    without a database connection. Recording the retrieval settings next to the
    versions lets two reports of the same collection, measured under different
    settings, be told apart.

    :param metrics: _evaluate()'s result.
    :param collection: The collection name that was evaluated.
    :param app_version: assistant_collections.app_version for this collection.
    :param corpus_version: assistant_collections.corpus_version for this collection.
    :param config: The retrieval settings this run measured.
    :return: A new dict: metrics plus "collection", "app_version", "corpus_version",
        "mode", "rerank", "query_transform", and "k".
    """
    return {
        **metrics,
        "collection": collection,
        "app_version": app_version,
        "corpus_version": corpus_version,
        "mode": config.mode,
        "rerank": config.rerank,
        "query_transform": config.query_transform,
        "k": config.k,
    }


def _build_retrieval_config(args: argparse.Namespace) -> RetrievalConfig:
    """Turn parsed CLI arguments into a RetrievalConfig.

    :param args: Parsed arguments (see _parse_args).
    :return: The retrieval config to evaluate.
    """
    return RetrievalConfig(
        mode=args.mode, k=args.k, rerank=args.rerank, query_transform=args.query_transform
    )


def _positive_int(text: str) -> int:
    """Parse a whole number of at least one, for --k.

    k=0 would cut every result list to nothing and write a report in which each query
    reads as a miss, so the parser refuses it instead.

    :param text: The raw command-line value.
    :return: The parsed number.
    :raises argparse.ArgumentTypeError: If text is not a whole number of at least one.
    """
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"{value} is less than 1")
    return value


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for one retrieval eval run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", required=True, help="Collection table name to evaluate")
    parser.add_argument(
        "--golden-set",
        default=None,
        help="Path to the golden set JSONL (default: scripts/assistant/golden_set.jsonl)",
    )
    parser.add_argument(
        "--mode",
        default="dense",
        choices=["bm25", "dense", "hybrid"],
        help="Retrieval mode to evaluate",
    )
    parser.add_argument(
        "--rerank", action="store_true", help="Rerank candidates before truncating to k"
    )
    parser.add_argument(
        "--query-transform",
        default="none",
        choices=["none", "translate_en", "multi_query", "hyde"],
        dest="query_transform",
        help="Query transform to apply before retrieval",
    )
    parser.add_argument(
        "--k", type=_positive_int, default=5, help="Number of chunks to return, at least 1"
    )
    return parser.parse_args()


async def _main() -> None:
    """Evaluate one collection against the golden set and write a JSON report.

    :raises ValueError: If the golden set is empty, or the collection has no
        assistant_collections registry row (_evaluate, _require_collection_versions).
    """
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    golden_set_path = (
        Path(args.golden_set)
        if args.golden_set
        else repo_root / "scripts" / "assistant" / "golden_set.jsonl"
    )
    entries = _load_golden_set(golden_set_path)
    title_to_path = _title_to_path(repo_root)
    config = _build_retrieval_config(args)

    settings = get_settings()
    embeddings = make_embeddings(settings)
    reranker = (
        LlamaServerReranker(
            base_url=settings.assistant_rerank_base_url,
            model=settings.assistant_rerank_model,
            timeout=settings.assistant_llm_timeout_seconds,
        )
        if config.rerank
        else None
    )
    llm = make_chat_model(settings) if config.query_transform != "none" else None
    engine = make_engine(settings.assistant_vector_db_url)
    try:
        store = open_store(engine, table=args.collection, embeddings=embeddings)
        row = await _fetch_collection_row(settings.assistant_vector_db_url, args.collection)
        app_version, corpus_version = _require_collection_versions(row, args.collection)
        retriever = DocsRetriever(store=store, config=config, reranker=reranker, llm=llm)
        metrics = await _evaluate(entries, retriever, title_to_path)
    finally:
        await engine.close()

    report = _finalize_report(metrics, args.collection, app_version, corpus_version, config)
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
