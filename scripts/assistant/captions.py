#!/usr/bin/env python3
"""Report which of the assistant's corpus chunks still need a caption, export them for
captioning, merge freshly written captions back into the captions file the "captions"
context mode reads, and drop captions whose chunk no longer exists.

    uv run python scripts/assistant/captions.py missing --strategy markdown_headers \\
        --size 500 --overlap-pct 10 --out batch.json
    uv run python scripts/assistant/captions.py merge batch-captions.json
    uv run python scripts/assistant/captions.py prune --strategy markdown_headers \\
        --size 500 --overlap-pct 10

Reads only the corpus and the captions file: no chat model, no embedding server (for
every chunking strategy but "semantic"), and no database. See api/assistant/README.md
for the full caption-writing workflow.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from api.assistant.rag.chunkers import ChunkerConfig, split
from api.assistant.rag.enrich import chunk_key
from api.assistant.rag.models import make_embeddings
from api.assistant.rag.pipeline import load_captions, load_corpus
from api.config import Settings, get_settings


def _read_captions_or_empty(settings: Settings, repo_root: Path) -> dict[str, str]:
    """Read the configured captions file, treating a missing file as the first run.

    :param settings: Application settings; assistant_captions_file names the file.
    :param repo_root: Repository root a relative assistant_captions_file resolves from.
    :return: load_captions()'s mapping, or {} when the file has not been written yet.
    :raises ValueError: If assistant_captions_file is not set, or its content is not a
        JSON object mapping strings to strings (see load_captions).
    """
    try:
        return load_captions(settings, repo_root)
    except FileNotFoundError:
        return {}


def _resolve_captions_path(settings: Settings, repo_root: Path) -> Path:
    """Resolve settings.assistant_captions_file, the same way load_captions() does.

    :param settings: Application settings; assistant_captions_file names the file.
    :param repo_root: Repository root a relative assistant_captions_file resolves from.
    :return: The path `merge` writes to, whether or not it exists yet.
    :raises ValueError: If assistant_captions_file is not set.
    """
    if not settings.assistant_captions_file:
        raise ValueError("no captions file configured: set ASSISTANT_CAPTIONS_FILE")
    return repo_root / settings.assistant_captions_file


def _batch_entry(
    document: Document, chunks: list[Document], captions: dict[str, str]
) -> dict[str, Any] | None:
    """Build one --out entry for a document, or None if all its chunks are captioned.

    :param document: One of load_corpus()'s pre-split Documents.
    :param chunks: That document's own chunks (split() applied to [document] alone).
    :param captions: chunk_key(chunk text) -> caption, as read from the captions file.
    :return: {"title", "layer", "document", "chunks": [{"sha", "text"}, ...]}, holding
        only the chunks with no matching caption, in document order - or None when
        every chunk of this document already has one.
    """
    uncaptioned = []
    for chunk in chunks:
        key = chunk_key(chunk.page_content)
        if key not in captions:
            uncaptioned.append({"sha": key, "text": chunk.page_content})
    if not uncaptioned:
        return None
    return {
        "title": document.metadata["title"],
        "layer": document.metadata["layer"],
        "document": document.page_content,
        "chunks": uncaptioned,
    }


def _find_missing(
    documents: list[Document],
    config: ChunkerConfig,
    captions: dict[str, str],
    embeddings: Embeddings | None,
) -> tuple[int, int, list[dict[str, Any]], set[str]]:
    """Chunk every document and collect those with at least one uncaptioned chunk.

    Splits one document at a time instead of the whole corpus in one split() call, so
    each resulting chunk can be attributed back to the document it came from. Every
    chunking strategy processes documents independently (chunkers.py), so this yields
    exactly the chunks build_collection's own split(documents, ...) call would, in the
    same order.

    :param documents: load_corpus()'s output.
    :param config: The chunking strategy and size to check, matching a real ingest run.
    :param captions: chunk_key(chunk text) -> caption, as read from the captions file.
    :param embeddings: Required for strategy="semantic"; ignored, and not needed, for
        every other strategy.
    :return: (missing, total, batch, keys): the total chunk count, how many have no
        caption, one entry per document with at least one uncaptioned chunk in
        document order (see _batch_entry), and chunk_key of every chunk this corpus
        split into, captioned or not - a caption is stale when its key falls outside
        this set.
    """
    total = 0
    missing = 0
    batch: list[dict[str, Any]] = []
    keys: set[str] = set()
    for document in documents:
        chunks = split([document], config, embeddings=embeddings)
        total += len(chunks)
        keys.update(chunk_key(chunk.page_content) for chunk in chunks)
        entry = _batch_entry(document, chunks, captions)
        if entry is not None:
            missing += len(entry["chunks"])
            batch.append(entry)
    return missing, total, batch, keys


def _merge_captions(
    new_captions: dict[str, str], existing: dict[str, str]
) -> tuple[dict[str, str], int, int]:
    """Merge freshly written captions into the existing mapping.

    :param new_captions: chunk_key -> caption pairs to add or replace.
    :param existing: The captions file's current mapping.
    :return: (merged, added, replaced): the merged mapping, and how many keys in
        new_captions were new versus already present in existing.
    """
    merged = dict(existing)
    added = 0
    replaced = 0
    for key, caption in new_captions.items():
        if key in merged:
            replaced += 1
        else:
            added += 1
        merged[key] = caption
    return merged, added, replaced


def _write_captions(path: Path, captions: dict[str, str]) -> None:
    """Write the captions file, the one place its on-disk format is defined.

    :param path: The captions file to write.
    :param captions: chunk_key -> caption mapping to write.
    """
    path.write_text(
        json.dumps(captions, sort_keys=True, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def _captions_payload(text: str) -> dict[str, str]:
    """Parse and validate a merge FILE argument: a JSON object of non-empty strings.

    An argparse `type=` callable, so an invalid FILE stops the command with a plain
    usage error instead of a traceback (the same pattern eval_retrieval.py's
    _positive_int uses) - merging an empty caption or a non-object would silently
    write a caption nobody actually wrote.

    :param text: The FILE path given on the command line.
    :return: The parsed key -> caption mapping.
    :raises argparse.ArgumentTypeError: If the path cannot be read as JSON, is not a
        JSON object, or holds a non-string or empty-string value for some key.
    """
    try:
        data = json.loads(Path(text).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise argparse.ArgumentTypeError(f"{text}: {exc}") from None
    if not isinstance(data, dict):
        raise argparse.ArgumentTypeError(f"{text}: must contain a JSON object")
    for key, value in data.items():
        if not isinstance(value, str) or not value:
            raise argparse.ArgumentTypeError(
                f"{text}: caption for {key!r} must be a non-empty string"
            )
    return data


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for one captions-refresh command.

    :return: The parsed arguments; args.command is "missing", "merge" or "prune".
    """
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    corpus_parser = argparse.ArgumentParser(add_help=False)
    corpus_parser.add_argument(
        "--strategy",
        required=True,
        choices=["fixed", "recursive", "markdown_headers", "sentences", "semantic", "parent_child"],
        help="Chunking strategy",
    )
    corpus_parser.add_argument(
        "--size", type=int, default=500, help="Target chunk size in characters"
    )
    corpus_parser.add_argument(
        "--overlap-pct", type=int, default=10, help="Chunk overlap, as a percentage of size"
    )
    corpus_parser.add_argument("--wave", type=int, default=1, help="Highest corpus wave to include")

    missing_parser = subparsers.add_parser(
        "missing",
        parents=[corpus_parser],
        help="Report chunks with no caption, and export them for captioning",
    )
    missing_parser.add_argument(
        "--out", default=None, help="Write the documents with uncaptioned chunks to this JSON file"
    )

    merge_parser = subparsers.add_parser(
        "merge", help="Merge a freshly captioned batch into the captions file"
    )
    merge_parser.add_argument(
        "file", type=_captions_payload, help="JSON object mapping each chunk's sha to its caption"
    )

    subparsers.add_parser(
        "prune",
        parents=[corpus_parser],
        help="Drop captions whose chunk no longer exists in the corpus",
    )

    return parser.parse_args()


def _run_missing(args: argparse.Namespace, settings: Settings, repo_root: Path) -> None:
    """Run the `missing` command: report, and optionally export, uncaptioned chunks.

    :param args: Parsed CLI arguments (strategy, size, overlap_pct, wave, out).
    :param settings: Application settings.
    :param repo_root: Repository root.
    """
    config = ChunkerConfig(strategy=args.strategy, size=args.size, overlap_pct=args.overlap_pct)
    documents = load_corpus(settings, repo_root, args.wave)
    captions = _read_captions_or_empty(settings, repo_root)
    embeddings = make_embeddings(settings) if config.strategy == "semantic" else None
    missing, total, batch, keys = _find_missing(documents, config, captions, embeddings)
    stale = len(captions.keys() - keys)
    print(f"{missing} of {total} chunks have no caption; {stale} captions match no chunk")
    if args.out:
        Path(args.out).write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_merge(new_captions: dict[str, str], settings: Settings, repo_root: Path) -> None:
    """Run the `merge` command: fold freshly written captions into the captions file.

    :param new_captions: chunk_key -> caption pairs to merge in (already validated by
        _captions_payload).
    :param settings: Application settings.
    :param repo_root: Repository root.
    """
    path = _resolve_captions_path(settings, repo_root)
    existing = _read_captions_or_empty(settings, repo_root)
    merged, added, replaced = _merge_captions(new_captions, existing)
    _write_captions(path, merged)
    print(f"added {added}, replaced {replaced}, total {len(merged)}")


def _run_prune(args: argparse.Namespace, settings: Settings, repo_root: Path) -> None:
    """Run the `prune` command: drop captions whose chunk no longer exists.

    :param args: Parsed CLI arguments (strategy, size, overlap_pct, wave).
    :param settings: Application settings.
    :param repo_root: Repository root.
    """
    config = ChunkerConfig(strategy=args.strategy, size=args.size, overlap_pct=args.overlap_pct)
    documents = load_corpus(settings, repo_root, args.wave)
    captions = _read_captions_or_empty(settings, repo_root)
    embeddings = make_embeddings(settings) if config.strategy == "semantic" else None
    _, _, _, keys = _find_missing(documents, config, captions, embeddings)
    kept = {key: caption for key, caption in captions.items() if key in keys}
    removed = len(captions) - len(kept)
    if removed:
        _write_captions(_resolve_captions_path(settings, repo_root), kept)
    print(f"removed {removed}, kept {len(kept)}")


def _main() -> None:
    """Run the captions command named on the command line."""
    args = _parse_args()
    settings = get_settings()
    repo_root = Path(__file__).resolve().parents[2]
    try:
        _resolve_captions_path(settings, repo_root)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from None
    if args.command == "missing":
        _run_missing(args, settings, repo_root)
    elif args.command == "prune":
        _run_prune(args, settings, repo_root)
    else:
        _run_merge(args.file, settings, repo_root)


if __name__ == "__main__":
    _main()
