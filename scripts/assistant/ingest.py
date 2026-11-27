#!/usr/bin/env python3
"""Build one named document collection for the local assistant.

Reads Settings for the vector database URL, embedding model, and local corpus
locations, then builds exactly one collection per invocation - run it once per
chunker/context/wave variant the retrieval experiments want to compare.

    uv run python scripts/assistant/ingest.py \\
        --name docs_markdown_headers_500_o10_captions_bge_m3 --strategy markdown_headers \\
        --size 500 --overlap-pct 10 --context captions

Needs the "assistant" extra (uv sync --extra assistant) and the embedding endpoint the
settings point at: a local llama-server or the hosted API (api/assistant/README.md).
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from api.assistant.rag.chunkers import ChunkerConfig
from api.assistant.rag.pipeline import BuildReport, CollectionSpec, build_collection
from api.config import get_settings
from api.utils.invisible import strip_invisible


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for one collection build.

    :return: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Collection table name, e.g. docs_default")
    parser.add_argument(
        "--strategy",
        required=True,
        choices=["fixed", "recursive", "markdown_headers", "sentences", "semantic", "parent_child"],
        help="Chunking strategy",
    )
    parser.add_argument("--size", type=int, default=500, help="Target chunk size in characters")
    parser.add_argument(
        "--overlap-pct", type=int, default=10, help="Chunk overlap, as a percentage of size"
    )
    parser.add_argument(
        "--context",
        default="none",
        choices=["none", "heading_path", "llm_context", "doc_summary", "captions"],
        help="Per-chunk context mode",
    )
    parser.add_argument("--wave", type=int, default=1, help="Highest corpus wave to include")
    return parser.parse_args()


def _build_spec(args: argparse.Namespace) -> CollectionSpec:
    """Turn parsed CLI arguments into a CollectionSpec.

    :param args: Parsed arguments (see _parse_args).
    :return: The collection spec to build.
    """
    return CollectionSpec(
        name=args.name,
        chunker=ChunkerConfig(strategy=args.strategy, size=args.size, overlap_pct=args.overlap_pct),
        context=args.context,
        wave=args.wave,
    )


def _terminal_safe(text: str) -> str:
    """Make corpus metadata safe to print: no control character, one line.

    A source or section comes from the documents being ingested, so it may carry an escape
    sequence that a terminal would act on, or a line break that forges another line.

    :param text: A field of a flagged chunk.
    :return: The text without invisible or control characters, on one line.
    """
    return " ".join(strip_invisible(text).split())


async def _main() -> BuildReport:
    """Build the collection named on the command line.

    Prints the chunk count and, one line per chunk, the chunks that look like planted
    instructions (layer | source | section | reason). They are written to the collection
    all the same: the ingest reports them and never stops.

    :return: The build's report.
    """
    spec = _build_spec(_parse_args())
    settings = get_settings()
    repo_root = Path(__file__).resolve().parents[2]
    report = await build_collection(spec, settings, repo_root=repo_root)
    print(f"Built collection {spec.name!r}: {report.chunk_count} chunks")
    for item in report.flagged:
        fields = (item.layer, item.source, item.section, item.reason)
        print("flagged: " + " | ".join(_terminal_safe(field) for field in fields))
    return report


if __name__ == "__main__":
    asyncio.run(_main())
