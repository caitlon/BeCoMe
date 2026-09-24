"""The corpus manifest: which files feed the assistant's document index.

build_manifest() is the single source of truth for "what gets indexed" - the ingest
CLI (scripts/assistant/ingest.py) and the retrieval eval script both call it rather
than walking the filesystem themselves, so the public and local layers are defined in
exactly one place.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Layer = Literal["public", "local"]
Kind = Literal["markdown", "i18n_json", "text", "pdf", "latex"]

#: Public documents that intentionally never ship to any reader, this assistant
#: included: both discuss what the project deliberately does not publish.
EXCLUDED_PUBLIC = ("docs/security.md", "docs/environments.md")

#: Suffix -> Kind. A file whose suffix is not here is not part of the corpus at all
#: (images, stylesheets, .puml diagrams under docs/uml-diagrams/ and similar).
_KIND_BY_SUFFIX: dict[str, Kind] = {
    ".md": "markdown",
    ".json": "i18n_json",
    ".txt": "text",
    ".pdf": "pdf",
    ".tex": "latex",
}

#: The two i18n files the corpus wants; the other files in the same locale
#: directories (about.json, auth.json, ...) are UI strings with no method or
#: interpretation content and are not part of any corpus wave.
_I18N_TARGETS = ("docs.json", "faq.json")

#: Not private: loaders.py matches the same pattern to resolve a docs/dev/*.md
#: snippet's content at load time, and shares this one definition rather than a
#: second copy of the same syntax.
SNIPPET_INCLUDE = re.compile(r'--8<--\s+"([^"]+)"')

_H1_HEADING = re.compile(r"^#\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class CorpusSource:
    """One file the assistant's corpus indexes, with its provenance.

    :param path: Absolute filesystem path to the file: repo_root joined with the
        relative path for a public source, or already resolved against the local
        manifest's own folder for a local one (see build_manifest and _walk_local).
        Never a bare relative path: loaders.py opens it directly, with no repository
        root of its own to resolve one against.
    :param layer: "public" (repository-tracked) or "local" (private, never in git).
    :param kind: Which loader (loaders.py) reads this file.
    :param title: Human-readable title, shown in citations.
    :param lang: BCP-47-ish language tag, "en" or "cs".
    :param url: Public documentation URL, or None for sources with no public page.
    :param wave: Corpus wave this source belongs to (1 or 2).
    """

    path: Path
    layer: Layer
    kind: Kind
    title: str
    lang: str
    url: str | None
    wave: int


def _markdown_title(text: str, fallback: str) -> str:
    """Take the first H1 heading as a title, falling back to a prettified filename.

    :param text: The markdown file's raw content.
    :param fallback: Stem to prettify (e.g. "what-it-does") if there is no H1.
    :return: A human-readable title.
    """
    match = _H1_HEADING.search(text)
    if match:
        return match.group(1).strip()
    return fallback.replace("-", " ").replace("_", " ").title()


def _snippet_targets(docs_dir: Path) -> set[str]:
    """Find every file that a docs/**/*.md page pulls in via a `--8<--` snippet include.

    Used to keep the "module READMEs" pass from re-adding a README that docs/** has
    already contributed to the manifest with its own path and URL (docs/dev/api.md IS
    api/README.md's text, plus two lines of HTML comment; docs/index.md IS the root
    README.md's text the same way) - so the scan walks the whole docs/ tree, not only
    docs/dev/, or the index.md case would be missed.

    :param docs_dir: The docs directory (may not exist).
    :return: Repository-root-relative paths named by a `--8<--` include.
    """
    if not docs_dir.is_dir():
        return set()
    targets: set[str] = set()
    for md_file in docs_dir.rglob("*.md"):
        match = SNIPPET_INCLUDE.search(md_file.read_text(encoding="utf-8"))
        if match:
            targets.add(match.group(1))
    return targets


def is_excluded_public(path: Path, repo_root: Path) -> bool:
    """Report whether a resolved path is one of the EXCLUDED_PUBLIC pages.

    Compared by file identity as well as by spelling: on a case-insensitive filesystem
    (the macOS default) "DOCS/SECURITY.MD" opens docs/security.md while comparing
    unequal as a string, and a hard link opens it under any name at all.

    :param path: The candidate path, already resolved.
    :param repo_root: The repository root, already resolved.
    :return: True when the path is an excluded page or the same file as one.
    """
    if path.relative_to(repo_root).as_posix() in EXCLUDED_PUBLIC:
        return True
    if not path.exists():
        return False
    return any(
        (repo_root / excluded).exists() and path.samefile(repo_root / excluded)
        for excluded in EXCLUDED_PUBLIC
    )


def _walk_docs(repo_root: Path, wave: int) -> list[CorpusSource]:
    """Walk docs/** for markdown, skipping EXCLUDED_PUBLIC under any name.

    :param repo_root: Repository root.
    :param wave: Wave number stamped on every source this call produces.
    :return: One CorpusSource per markdown file under docs/, EXCLUDED_PUBLIC omitted.
    :raises ValueError: If a walked file's resolved path is outside repo_root - a
        symlink pointing out of the repository would otherwise pull an arbitrary file
        into the public layer.
    """
    docs_dir = repo_root / "docs"
    if not docs_dir.is_dir():
        return []
    resolved_root = repo_root.resolve()
    sources = []
    for md_file in sorted(docs_dir.rglob("*.md")):
        resolved = md_file.resolve()
        # Compared after resolve(), the same way loaders.py's snippet-include guard
        # does: Path.is_relative_to only compares path parts, so a symlink climbing
        # out of the repository would otherwise pass as being inside repo_root.
        if not resolved.is_relative_to(resolved_root):
            raise ValueError(
                f"{md_file}: resolves to {resolved}, which is outside the repository root"
            )
        if is_excluded_public(resolved, resolved_root):
            continue
        text = md_file.read_text(encoding="utf-8")
        sources.append(
            CorpusSource(
                path=md_file,
                layer="public",
                kind="markdown",
                title=_markdown_title(text, md_file.stem),
                lang="en",
                url=None,
                wave=wave,
            )
        )
    return sources


# The repository's own READMEs that docs/dev/*.md does not already snippet-include.
# An explicit list, not a walk: rglob("README.md") from the repository root reaches
# frontend/node_modules and .venv (thousands of third-party READMEs) and, in a
# worktree, the supplementary symlink with private files. api/assistant/README.md is
# deliberately absent: it is the assistant's own setup guide, not documentation of
# the method or the app.
PUBLIC_EXTRA_READMES = (
    "README.md",
    "examples/data/README.md",
    "examples/visualizations/README.md",
)


def _walk_module_readmes(
    repo_root: Path, already_covered: set[str], wave: int
) -> list[CorpusSource]:
    """Return the allowlisted READMEs not already pulled in via a docs/dev/*.md snippet.

    :param repo_root: Repository root.
    :param already_covered: Repository-root-relative paths a docs/dev/*.md snippet
        already targets (see _snippet_targets); these are skipped here to avoid
        indexing the same text twice under two different sources.
    :param wave: Wave number stamped on every source this call produces.
    :return: One CorpusSource per allowlisted README that exists and is not covered.
    """
    sources = []
    for rel in PUBLIC_EXTRA_READMES:
        readme = repo_root / rel
        if rel in already_covered or not readme.is_file():
            continue
        text = readme.read_text(encoding="utf-8")
        sources.append(
            CorpusSource(
                path=readme,
                layer="public",
                kind="markdown",
                title=_markdown_title(text, readme.parent.name or "README"),
                lang="en",
                url=None,
                wave=wave,
            )
        )
    return sources


def _walk_i18n(repo_root: Path, wave: int) -> list[CorpusSource]:
    """Find the two targeted i18n JSON files in each locale.

    :param repo_root: Repository root.
    :param wave: Wave number stamped on every source this call produces.
    :return: One CorpusSource per (locale, target file) pair that exists.
    """
    locales_dir = repo_root / "frontend" / "src" / "i18n" / "locales"
    if not locales_dir.is_dir():
        return []
    sources = []
    for locale_dir in sorted(locales_dir.iterdir()):
        if not locale_dir.is_dir():
            continue
        for name in _I18N_TARGETS:
            json_file = locale_dir / name
            if not json_file.is_file():
                continue
            data = json.loads(json_file.read_text(encoding="utf-8"))
            sources.append(
                CorpusSource(
                    path=json_file,
                    layer="public",
                    kind="i18n_json",
                    title=data.get("title", name),
                    lang=locale_dir.name,
                    url=None,
                    wave=wave,
                )
            )
    return sources


def _resolve(base: Path, raw: str) -> Path:
    """Resolve a manifest- or setting-supplied path against a base directory.

    An absolute path passes through unchanged; anything else is taken as relative to
    base: the repository root for settings, the manifest's own folder for its entries.

    :param base: Directory a relative path is taken from.
    :param raw: The raw string from settings or a manifest entry.
    :return: The joined path, with symlinks and ".." left as written.
    """
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else (base / candidate)


def _walk_local(
    repo_root: Path, private_dirs: list[Path], local_manifest: Path | None
) -> list[CorpusSource]:
    """Read the local-layer JSON manifest, enforcing the private_dirs allowlist.

    The manifest sits at the root of the private corpus repository, so a relative entry
    is taken from the manifest's own folder: one commit of that repository then pins
    both the files and their list, wherever the repository lives.

    :param repo_root: Repository root, for resolving a relative manifest path and
        relative private_dirs.
    :param private_dirs: Allowed roots (Settings.assistant_private_corpus_dirs); every
        entry must resolve, symlinks and ".." included, to one of these or below it.
    :param local_manifest: Path to the manifest JSON file, or None for no local layer.
    :return: One CorpusSource per manifest entry.
    :raises FileNotFoundError: If local_manifest is given but does not exist.
    :raises ValueError: If an entry resolves outside every allowed root, or its
        suffix maps to no known Kind.
    """
    if local_manifest is None:
        return []
    manifest_path = _resolve(repo_root, str(local_manifest))
    if not manifest_path.is_file():
        raise FileNotFoundError(f"local corpus manifest not found: {manifest_path}")
    # Compared after resolve(): Path.is_relative_to only compares path parts, so
    # "wave-1/../../../.ssh/config" would otherwise pass as being under the corpus.
    allowed_roots = [_resolve(repo_root, str(root)).resolve() for root in private_dirs]
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = []
    for entry in entries:
        path = _resolve(manifest_path.parent, entry["path"])
        real_path = path.resolve()
        if not any(real_path.is_relative_to(root) for root in allowed_roots):
            raise ValueError(
                f"local corpus manifest entry {entry['path']!r} resolves to {real_path}, "
                "which is outside every root in assistant_private_corpus_dirs"
            )
        kind = _KIND_BY_SUFFIX.get(path.suffix.lower())
        if kind is None:
            raise ValueError(
                f"local corpus manifest entry {entry['path']!r} has an unsupported "
                f"suffix {path.suffix!r}"
            )
        sources.append(
            CorpusSource(
                # The path already resolved and checked against allowed_roots above,
                # so the file loaders.py later opens is the file that was validated.
                path=real_path,
                layer="local",
                kind=kind,
                title=entry["title"],
                lang=entry["lang"],
                url=None,
                wave=entry.get("wave", 1),
            )
        )
    return sources


def build_manifest(
    repo_root: Path,
    private_dirs: list[Path],
    wave: int = 1,
    local_manifest: Path | None = None,
) -> list[CorpusSource]:
    """Build the full corpus manifest: public layer plus the local layer.

    :param repo_root: Repository root; docs/**, module READMEs, and the two i18n
        files are found relative to it, and it is also the base for a relative
        local_manifest path and relative private_dirs.
    :param private_dirs: Allowed local-layer roots (Settings.assistant_private_corpus_dirs).
        Every local_manifest entry must resolve under one of these.
    :param wave: Highest wave to include (1 or 2); a source is included when its own
        wave is less than or equal to this one.
    :param local_manifest: Path to the local-layer JSON manifest, or None for no
        local layer at all (the default, and always the case in CI).
    :return: Every CorpusSource whose wave qualifies, public layer first.
    """
    already_covered = _snippet_targets(repo_root / "docs")
    sources = [
        *_walk_docs(repo_root, wave=1),
        *_walk_module_readmes(repo_root, already_covered, wave=1),
        *_walk_i18n(repo_root, wave=1),
        *_walk_local(repo_root, private_dirs, local_manifest),
    ]
    return [source for source in sources if source.wave <= wave]
