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
from api.assistant.rag.pipeline import (
    BuildReport,
    CollectionSpec,
    FlaggedChunksError,
    build_collection,
)
from api.assistant.rag.screening import FlaggedChunk
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
    parser.add_argument(
        "--accept-flagged",
        action="append",
        default=[],
        metavar="KEY",
        help=(
            "Let a flagged chunk outside the public layer through, by the key printed on its "
            "flagged line; repeat for each chunk. The key covers the text, title and section, plus "
            "the URL when the chunk has one, so chunks with the same fields share a key, and "
            "editing any of them or changing the chunker flags changes it."
        ),
    )
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
        accepted_flagged=frozenset(key.strip().lower() for key in args.accept_flagged),
    )


def _terminal_safe(text: str) -> str:
    """Make corpus metadata safe to print: no control character, one line.

    A source or section comes from the documents being ingested, so it may carry an escape
    sequence that a terminal would act on, or a line break that forges another line.

    :param text: A field of a flagged chunk.
    :return: The text without invisible or control characters, on one line.
    """
    return " ".join(strip_invisible(text).split())


def _flagged_line(item: FlaggedChunk) -> str:
    """Format one flagged chunk as a line that is safe to print.

    :param item: A chunk screening.py flagged.
    :return: "flagged: layer | source | section | reason | key".
    """
    fields = (item.layer, item.source, item.section, item.reason, item.key)
    return "flagged: " + " | ".join(_terminal_safe(field) for field in fields)


def _print_flagged(flagged: list[FlaggedChunk], accepted: frozenset[str]) -> None:
    """Print the flagged lines, then a note for each accepted key that matched nothing.

    :param flagged: The chunks screening.py flagged.
    :param accepted: The keys given with --accept-flagged.
    """
    for item in flagged:
        print(_flagged_line(item))
    for key in sorted(accepted - {item.key for item in flagged}):
        print(f"note: --accept-flagged {_terminal_safe(key)} matches no flagged chunk")


async def _main() -> BuildReport:
    """Build the collection named on the command line.

    Prints the chunk count and, one line per chunk, the chunks that look like planted
    instructions (layer | source | section | reason | key). Public-layer chunks and the
    ones outside it accepted with --accept-flagged are written all the same. A
    chunk outside the public layer that is flagged and not accepted stops the build:
    nothing is written, the live collection stays, and the process exits with status 1 after
    printing every flagged line and how to proceed.

    :return: The build's report.
    :raises SystemExit: With status 1 when the build stopped on flagged chunks.
    """
    spec = _build_spec(_parse_args())
    settings = get_settings()
    repo_root = Path(__file__).resolve().parents[2]
    try:
        report = await build_collection(spec, settings, repo_root=repo_root)
    except FlaggedChunksError as error:
        _print_flagged(error.flagged, spec.accepted_flagged)
        print(
            f"Build of {spec.name!r} stopped: {len(error.blocking)} flagged chunk(s) "
            "outside the public layer. Nothing was written and the live collection is "
            "unchanged. Edit or remove the source, or read each chunk and, if it is harmless, "
            "rerun with --accept-flagged <key> for it."
        )
        raise SystemExit(1) from error
    print(f"Built collection {spec.name!r}: {report.chunk_count} chunks")
    _print_flagged(report.flagged, spec.accepted_flagged)
    return report


if __name__ == "__main__":
    asyncio.run(_main())
