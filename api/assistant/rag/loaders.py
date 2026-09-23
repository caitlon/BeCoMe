"""Turn one CorpusSource into the Document(s) it contributes to the corpus.

Each kind of source has its own extraction logic, dispatched by load_source(); every
Document it returns carries the same eight metadata keys (source, layer, title, lang,
url, sha256, heading_path, wave), which is the provenance the retrieval layer and
citations (SourceRef) are built on.
"""

import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

import pypdf
from langchain_core.documents import Document
from pylatexenc.latex2text import LatexNodes2Text

from api.assistant.rag.corpus import EXCLUDED_PUBLIC, SNIPPET_INCLUDE, CorpusSource

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def _find_repo_root(start: Path) -> Path:
    """Walk upward from a file to the repository root, marked by pyproject.toml.

    Needed only to resolve a docs/dev/*.md snippet include, whose target is written
    relative to the repository root (mkdocs.yml: base_path = !relative $config_dir,
    and $config_dir is the repository root). load_source() otherwise never needs a
    repository root: every CorpusSource.path it receives is already absolute.

    :param start: The markdown file containing the snippet include.
    :return: The repository root.
    :raises FileNotFoundError: If no ancestor directory contains pyproject.toml.
    """
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise FileNotFoundError(f"no pyproject.toml found above {start}; cannot resolve repo root")


def _base_metadata(
    source: CorpusSource, raw: bytes, heading_path: str = ""
) -> dict[str, str | int | None]:
    """Build the eight contracted metadata keys shared by every loaded Document.

    :param source: The manifest entry this content came from.
    :param raw: The source file's raw bytes, hashed for change detection.
    :param heading_path: Structural path within the document, "" when not yet known
        (markdown fills this in later, per chunk, in chunkers.py).
    :return: A JSON-serializable metadata dict.
    """
    return {
        "source": str(source.path),
        "layer": source.layer,
        "title": source.title,
        "lang": source.lang,
        "url": source.url,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "heading_path": heading_path,
        "wave": source.wave,
    }


def _is_excluded_public(target_path: Path, repo_root: Path) -> bool:
    """Report whether a resolved include target is one of the EXCLUDED_PUBLIC pages.

    Compared by file identity as well as by spelling: on a case-insensitive filesystem
    (the macOS default) "DOCS/SECURITY.MD" opens docs/security.md while comparing
    unequal as a string, and a hard link opens it under any name at all.

    :param target_path: The include target, already resolved.
    :param repo_root: The repository root, already resolved.
    :return: True when the target is an excluded page or the same file as one.
    """
    if target_path.relative_to(repo_root).as_posix() in EXCLUDED_PUBLIC:
        return True
    if not target_path.exists():
        return False
    return any(
        (repo_root / excluded).exists() and target_path.samefile(repo_root / excluded)
        for excluded in EXCLUDED_PUBLIC
    )


def _load_markdown(source: CorpusSource) -> list[Document]:
    """Load a markdown file, resolving one `--8<--` snippet include if present.

    :param source: A CorpusSource with kind="markdown".
    :return: A single Document with the file's (resolved) text.
    :raises ValueError: If a snippet include's target resolves outside the repository
        root, or names a file in EXCLUDED_PUBLIC - checked, and refused, before the
        target itself is read.
    """
    raw = source.path.read_bytes()
    text = raw.decode("utf-8")
    match = SNIPPET_INCLUDE.search(text)
    if match:
        target = match.group(1)
        repo_root = _find_repo_root(source.path).resolve()
        # Compared after resolve(), the same way _walk_local compares the local-layer
        # allowlist: Path.is_relative_to only compares path parts, so a target reached
        # through a symlink or a "../.." climb would otherwise pass as being inside
        # repo_root.
        target_path = (repo_root / target).resolve()
        if not target_path.is_relative_to(repo_root):
            raise ValueError(
                f"{source.path}: snippet include {target!r} resolves to {target_path}, "
                "which is outside the repository root"
            )
        if _is_excluded_public(target_path, repo_root):
            raise ValueError(
                f"{source.path}: snippet include {target!r} resolves to {target_path}, "
                "which is in EXCLUDED_PUBLIC and must never be included"
            )
        target_text = target_path.read_text(encoding="utf-8")
        # A function replacement, not a plain string: re.sub treats a string
        # replacement as a backreference template (\1, \g<name>, ...), and target_text
        # is arbitrary file content that may itself contain a literal backslash.
        text = SNIPPET_INCLUDE.sub(lambda _match: target_text, text, count=1)
    return [Document(page_content=text, metadata=_base_metadata(source, raw))]


def _prettify_key(key: str) -> str:
    """Turn a camelCase JSON key into a title-cased label ("whatIsBecome" -> "What Is Become").

    :param key: The JSON object key.
    :return: A human-readable label.
    """
    spaced = _CAMEL_BOUNDARY.sub(" ", key)
    return spaced[:1].upper() + spaced[1:]


def _flatten_i18n_json(data: dict[str, Any], path: list[str]) -> list[tuple[list[str], str]]:
    """Recursively flatten a nested i18n JSON object into (heading_path, text) sections.

    A dict's own string-valued fields become one section's text at its current path;
    each nested dict recurses with the path extended by its key. Non-string,
    non-dict values (there are none in docs.json/faq.json today) are ignored.

    :param data: The JSON object (or sub-object) to flatten.
    :param path: Key path from the document root to this object.
    :return: (heading_path, text) pairs, root-level section first.
    """
    strings = {key: value for key, value in data.items() if isinstance(value, str)}
    nested = {key: value for key, value in data.items() if isinstance(value, dict)}
    sections = []
    if strings:
        lines = [f"{_prettify_key(key)}: {value}" for key, value in strings.items()]
        sections.append((path, "\n".join(lines)))
    for key, value in nested.items():
        sections.extend(_flatten_i18n_json(value, path=[*path, key]))
    return sections


def _load_i18n_json(source: CorpusSource) -> list[Document]:
    """Load an i18n JSON file as one Document per leaf section.

    :param source: A CorpusSource with kind="i18n_json".
    :return: One Document per section produced by _flatten_i18n_json.
    """
    raw = source.path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    return [
        Document(
            page_content=text,
            metadata=_base_metadata(source, raw, heading_path=" > ".join(heading_path)),
        )
        for heading_path, text in _flatten_i18n_json(data, path=[])
    ]


def _load_text(source: CorpusSource) -> list[Document]:
    """Load a plain-text file as a single Document.

    :param source: A CorpusSource with kind="text".
    :return: A single Document with the file's text.
    """
    raw = source.path.read_bytes()
    return [Document(page_content=raw.decode("utf-8"), metadata=_base_metadata(source, raw))]


def _load_pdf(source: CorpusSource) -> list[Document]:
    """Extract a PDF's text page by page and join it into a single Document.

    :param source: A CorpusSource with kind="pdf".
    :return: A single Document with the concatenated per-page text.
    """
    raw = source.path.read_bytes()
    reader = pypdf.PdfReader(io.BytesIO(raw))
    text = "\n\n".join(page.extract_text() for page in reader.pages)
    return [Document(page_content=text, metadata=_base_metadata(source, raw))]


def _load_latex(source: CorpusSource) -> list[Document]:
    """Convert a LaTeX chapter to plain text with pylatexenc's default macro handling.

    Unknown macros - biblatex's \\textcite/\\autocite, and this corpus's own custom
    environments and source-attribution commands among them - degrade to their
    mandatory argument's text rather than raising, which is enough fidelity for
    retrieval (verified directly against the real thesis chapters' constructs,
    2026-09-14); no custom latex_context is registered.

    :param source: A CorpusSource with kind="latex".
    :return: A single Document with the extracted plain text.
    """
    raw = source.path.read_bytes()
    text = LatexNodes2Text().latex_to_text(raw.decode("utf-8"))
    return [Document(page_content=text, metadata=_base_metadata(source, raw))]


def load_source(source: CorpusSource) -> list[Document]:
    """Turn one manifest entry into the Document(s) it contributes to the corpus.

    :param source: The manifest entry to load.
    :return: One or more Documents, each carrying the contracted metadata keys.
    :raises ValueError: If source.kind names a kind this function does not handle.
    """
    if source.kind == "markdown":
        return _load_markdown(source)
    if source.kind == "i18n_json":
        return _load_i18n_json(source)
    if source.kind == "text":
        return _load_text(source)
    if source.kind == "pdf":
        return _load_pdf(source)
    if source.kind == "latex":
        return _load_latex(source)
    raise ValueError(f"load_source does not handle kind {source.kind!r} yet")
