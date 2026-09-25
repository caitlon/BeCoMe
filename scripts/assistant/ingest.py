#!/usr/bin/env python3
"""Build one named document collection for the local assistant.

Reads Settings for the vector database URL, embedding model, and local corpus
locations, then builds exactly one collection per invocation - run it once per
chunker/context/wave variant the retrieval experiments want to compare.

    uv run python scripts/assistant/ingest.py \\
        --name docs_default --strategy markdown_headers --size 500 --overlap-pct 10

Needs the "assistant" extra (uv sync --extra assistant) and a running embedding
llama-server (api/assistant/README.md).
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from api.assistant.rag.chunkers import ChunkerConfig
from api.assistant.rag.pipeline import CollectionSpec, build_collection
from api.config import get_settings


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


async def _main() -> None:
    """Build the collection named on the command line."""
    spec = _build_spec(_parse_args())
    settings = get_settings()
    repo_root = Path(__file__).resolve().parents[2]
    chunk_count = await build_collection(spec, settings, repo_root=repo_root)
    print(f"Built collection {spec.name!r}: {chunk_count} chunks")


if __name__ == "__main__":
    asyncio.run(_main())
