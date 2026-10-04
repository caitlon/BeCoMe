"""Unit tests for the public-layer corpus manifest (fakes only, no network)."""

import json
import re
from pathlib import Path

import pytest

from api.assistant.rag.corpus import EXCLUDED_PUBLIC, CorpusSource, build_manifest


def _touch(path: Path, content: str = "content") -> None:
    """Create a file with its parent directories, so tests read as plain trees."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _hardlink_or_skip(link: Path, target: Path) -> None:
    """Hard-link link -> target, or skip the test when the filesystem cannot do it."""
    try:
        link.hardlink_to(target)
    except OSError as exc:
        pytest.skip(f"filesystem cannot create hard links: {exc}")


def _symlink_or_skip(link: Path, target: Path, target_is_directory: bool = False) -> None:
    """Symlink link -> target, or skip the test when the filesystem cannot do it."""
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as exc:
        pytest.skip(f"filesystem cannot create symlinks: {exc}")


class TestExcludedPublic:
    """The two internal-only documents never enter the manifest."""

    def test_excluded_public_lists_security_and_environments(self):
        """
        GIVEN the EXCLUDED_PUBLIC tuple
        WHEN inspected
        THEN it names exactly the two documents the contract fixes
        """
        assert EXCLUDED_PUBLIC == ("docs/security.md", "docs/environments.md")


class TestPublicDocsWalk:
    """build_manifest walks docs/** for markdown, skipping EXCLUDED_PUBLIC."""

    def test_walks_docs_tree_and_skips_excluded(self, tmp_path):
        """
        GIVEN a docs/ tree with a security.md and an ordinary page
        WHEN build_manifest walks it
        THEN the ordinary page is a public CorpusSource and security.md is absent
        """
        # GIVEN
        _touch(tmp_path / "docs" / "security.md", "# Security\nInternal only.")
        _touch(tmp_path / "docs" / "user" / "what-it-does.md", "# What BeCoMe does\nText.")

        # WHEN
        manifest = build_manifest(repo_root=tmp_path, private_dirs=[])

        # THEN: path is the resolved absolute file, not a repo-relative string - loaders.py
        # opens source.path directly, with no repo_root of its own to resolve a relative
        # one against.
        target = tmp_path / "docs" / "user" / "what-it-does.md"
        excluded = tmp_path / "docs" / "security.md"
        paths = {source.path for source in manifest}
        assert target in paths
        assert excluded not in paths
        source = next(s for s in manifest if s.path == target)
        assert source.layer == "public"
        assert source.kind == "markdown"
        assert source.title == "What BeCoMe does"
        assert source.wave == 1
        assert source.url is None

    def test_resolves_dev_snippet_include_and_skips_its_readme_separately(self, tmp_path):
        """
        GIVEN docs/dev/api.md that snippet-includes api/README.md
        WHEN build_manifest walks the tree
        THEN docs/dev/api.md is one source, and api/README.md is not added again
        """
        # GIVEN
        _touch(
            tmp_path / "docs" / "dev" / "api.md",
            '<!-- Included from api/README.md -->\n\n--8<-- "api/README.md"\n',
        )
        _touch(tmp_path / "api" / "README.md", "# API\nBackend overview.")
        _touch(tmp_path / "README.md", "# BeCoMe\nRoot readme.")

        # WHEN
        manifest = build_manifest(repo_root=tmp_path, private_dirs=[])

        # THEN
        paths = [source.path for source in manifest]
        assert paths.count(tmp_path / "docs" / "dev" / "api.md") == 1
        assert (tmp_path / "api" / "README.md") not in paths
        assert (tmp_path / "README.md") in paths  # not a snippet target anywhere, kept

    def test_resolves_index_snippet_include_and_skips_readme_separately(self, tmp_path):
        """
        GIVEN docs/index.md that snippet-includes the root README.md
        WHEN build_manifest walks the tree
        THEN docs/index.md is one source, and README.md is not added again
        """
        # GIVEN
        _touch(
            tmp_path / "docs" / "index.md",
            '<!-- Included from README.md -->\n\n--8<-- "README.md"\n',
        )
        _touch(tmp_path / "README.md", "# BeCoMe\nRoot readme.")

        # WHEN
        manifest = build_manifest(repo_root=tmp_path, private_dirs=[])

        # THEN
        paths = [source.path for source in manifest]
        assert paths.count(tmp_path / "docs" / "index.md") == 1
        assert (tmp_path / "README.md") not in paths

    def test_never_walks_into_dependency_trees_or_the_assistant_readme(self, tmp_path):
        """
        GIVEN READMEs under node_modules, .venv, supplementary and api/assistant
        WHEN build_manifest builds the public layer
        THEN none of them is picked up: only the allowlisted READMEs are
        """
        # GIVEN
        _touch(tmp_path / "README.md", "# BeCoMe\nRoot readme.")
        _touch(tmp_path / "frontend" / "node_modules" / "pkg" / "README.md", "# pkg")
        _touch(tmp_path / ".venv" / "lib" / "site" / "README.md", "# site")
        _touch(tmp_path / "supplementary" / "private" / "README.md", "# private")
        _touch(tmp_path / "api" / "assistant" / "README.md", "# Local assistant")

        # WHEN
        manifest = build_manifest(repo_root=tmp_path, private_dirs=[])

        # THEN
        paths = {source.path for source in manifest}
        assert paths == {tmp_path / "README.md"}

    def test_hard_link_to_an_excluded_page_is_not_in_the_manifest(self, tmp_path):
        """
        GIVEN docs/notes.md hard-linked to docs/security.md
        WHEN build_manifest walks docs/
        THEN the link is excluded too - it is the same file as the excluded page,
             which a string comparison of the walked path against EXCLUDED_PUBLIC
             would miss
        """
        # GIVEN
        _touch(tmp_path / "docs" / "security.md", "# Security\nInternal only.")
        _touch(tmp_path / "docs" / "user" / "what-it-does.md", "# What BeCoMe does\nText.")
        link = tmp_path / "docs" / "notes.md"
        _hardlink_or_skip(link, tmp_path / "docs" / "security.md")

        # WHEN
        manifest = build_manifest(repo_root=tmp_path, private_dirs=[])

        # THEN
        paths = {source.path for source in manifest}
        assert link not in paths
        assert (tmp_path / "docs" / "security.md") not in paths
        assert (tmp_path / "docs" / "user" / "what-it-does.md") in paths

    def test_symlink_to_an_excluded_page_is_not_in_the_manifest(self, tmp_path):
        """
        GIVEN docs/notes.md symlinked to docs/environments.md
        WHEN build_manifest walks docs/
        THEN the link is excluded too - it resolves to the excluded page, which a
             string comparison of the walked path against EXCLUDED_PUBLIC would miss
        """
        # GIVEN
        _touch(tmp_path / "docs" / "environments.md", "# Environments\nInternal only.")
        _touch(tmp_path / "docs" / "user" / "what-it-does.md", "# What BeCoMe does\nText.")
        link = tmp_path / "docs" / "notes.md"
        _symlink_or_skip(link, tmp_path / "docs" / "environments.md")

        # WHEN
        manifest = build_manifest(repo_root=tmp_path, private_dirs=[])

        # THEN
        paths = {source.path for source in manifest}
        assert link not in paths
        assert (tmp_path / "docs" / "environments.md") not in paths
        assert (tmp_path / "docs" / "user" / "what-it-does.md") in paths

    def test_symlink_escaping_the_repository_root_raises(self, tmp_path):
        """
        GIVEN docs/escape.md symlinked to a file outside the repository root
        WHEN build_manifest walks docs/
        THEN it raises ValueError naming the link, before the outside file is read
        """
        # GIVEN
        repo_root = tmp_path / "repo"
        _touch(tmp_path / "outside.md", "# Outside\nNot part of the repository.\n")
        link = repo_root / "docs" / "escape.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        _symlink_or_skip(link, tmp_path / "outside.md")

        # WHEN/THEN
        with pytest.raises(ValueError, match="outside the repository root"):
            build_manifest(repo_root=repo_root, private_dirs=[])


class TestI18nWalk:
    """build_manifest discovers the two targeted i18n JSON files in each locale."""

    def test_discovers_docs_and_faq_json_per_locale(self, tmp_path):
        """
        GIVEN docs.json (with its own "title") and faq.json (without one) under two
             locale directories
        WHEN build_manifest walks the i18n tree
        THEN each becomes an i18n_json CorpusSource with lang taken from the locale
             directory, title from the JSON's own "title" key, and a fallback to the
             bare file name when that key is absent
        """
        # GIVEN
        locales = tmp_path / "frontend" / "src" / "i18n" / "locales"
        _touch(
            locales / "en" / "docs.json",
            json.dumps({"title": "Documentation", "intro": "Start here."}),
        )
        _touch(
            locales / "cs" / "faq.json",
            json.dumps({"question": "Co je BeCoMe?"}),
        )

        # WHEN
        manifest = build_manifest(repo_root=tmp_path, private_dirs=[])

        # THEN
        by_path = {source.path: source for source in manifest}
        en_docs = by_path[locales / "en" / "docs.json"]
        assert en_docs.kind == "i18n_json"
        assert en_docs.layer == "public"
        assert en_docs.lang == "en"
        assert en_docs.title == "Documentation"
        assert en_docs.url is None

        cs_faq = by_path[locales / "cs" / "faq.json"]
        assert cs_faq.kind == "i18n_json"
        assert cs_faq.lang == "cs"
        assert cs_faq.title == "faq.json"


class TestCorpusSourceShape:
    """CorpusSource is the frozen dataclass the contract fixes."""

    def test_is_frozen(self, tmp_path):
        """
        GIVEN a constructed CorpusSource
        WHEN a field is assigned after construction
        THEN it raises, since sources are immutable manifest entries
        """
        import dataclasses

        source = CorpusSource(
            path=Path("docs/index.md"),
            layer="public",
            kind="markdown",
            title="Index",
            lang="en",
            url=None,
            wave=1,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            source.title = "Changed"


class TestLocalLayer:
    """The local layer is read from a JSON manifest at the root of the private corpus."""

    def test_no_manifest_means_no_local_sources(self, tmp_path):
        """
        GIVEN private_dirs but no local_manifest
        WHEN build_manifest runs
        THEN no local-layer sources appear, and nothing raises
        """
        # GIVEN/WHEN
        manifest = build_manifest(
            repo_root=tmp_path, private_dirs=[tmp_path / "corpus"], local_manifest=None
        )

        # THEN
        assert all(source.layer != "local" for source in manifest)

    def test_entries_resolve_from_the_manifest_directory(self, tmp_path):
        """
        GIVEN a manifest at the corpus root with an entry relative to it
        WHEN build_manifest runs
        THEN the entry becomes a local-layer CorpusSource under the corpus, kind from suffix
        """
        # GIVEN
        corpus = tmp_path / "supplementary" / "assistant" / "corpus"
        _touch(corpus / "wave-1" / "clanek.txt", "obsah")
        manifest_file = corpus / "manifest.json"
        _touch(
            manifest_file,
            json.dumps([{"path": "wave-1/clanek.txt", "title": "Clanek", "lang": "cs", "wave": 1}]),
        )

        # WHEN
        manifest = build_manifest(
            repo_root=tmp_path, private_dirs=[corpus], local_manifest=manifest_file
        )

        # THEN
        local_sources = [s for s in manifest if s.layer == "local"]
        assert len(local_sources) == 1
        source = local_sources[0]
        assert source.path == corpus / "wave-1" / "clanek.txt"
        assert source.kind == "text"
        assert source.title == "Clanek"
        assert source.lang == "cs"
        assert source.url is None

    def test_entry_reached_through_a_symlinked_folder_is_stored_resolved(self, tmp_path):
        """
        GIVEN a manifest entry reached through a symlinked directory component
        WHEN build_manifest runs
        THEN the local-layer CorpusSource stores the resolved path, not the symlinked
             one - the file loaders.py later opens is then the file that was checked
             against the private_dirs allowlist
        """
        # GIVEN
        corpus = tmp_path / "supplementary" / "assistant" / "corpus"
        _touch(corpus / "wave-1" / "clanek.txt", "obsah")
        link = corpus / "links"
        _symlink_or_skip(link, corpus / "wave-1", target_is_directory=True)
        manifest_file = corpus / "manifest.json"
        _touch(
            manifest_file,
            json.dumps([{"path": "links/clanek.txt", "title": "Clanek", "lang": "cs", "wave": 1}]),
        )

        # WHEN
        manifest = build_manifest(
            repo_root=tmp_path, private_dirs=[corpus], local_manifest=manifest_file
        )

        # THEN
        local_sources = [s for s in manifest if s.layer == "local"]
        assert len(local_sources) == 1
        assert local_sources[0].path == corpus / "wave-1" / "clanek.txt"

    def test_relative_settings_resolve_against_repo_root_not_cwd(self, tmp_path, monkeypatch):
        """
        GIVEN the manifest path and allowlist root as relative paths, the way Settings gives them
        WHEN build_manifest runs from an unrelated working directory
        THEN both resolve against repo_root and the entry is found
        """
        # GIVEN
        corpus = tmp_path / "supplementary" / "assistant" / "corpus"
        _touch(corpus / "wave-1" / "clanek.txt", "obsah")
        _touch(
            corpus / "manifest.json",
            json.dumps([{"path": "wave-1/clanek.txt", "title": "Clanek", "lang": "cs", "wave": 1}]),
        )
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        # WHEN
        manifest = build_manifest(
            repo_root=tmp_path,
            private_dirs=[Path("supplementary/assistant/corpus")],
            local_manifest=Path("supplementary/assistant/corpus/manifest.json"),
        )

        # THEN
        assert [s.path for s in manifest if s.layer == "local"] == [
            corpus / "wave-1" / "clanek.txt"
        ]

    def test_rejects_an_entry_outside_every_allowed_root(self, tmp_path):
        """
        GIVEN a manifest entry with an absolute path outside every private_dirs root
        WHEN build_manifest runs
        THEN it raises ValueError naming the offending entry, before any indexing
        """
        # GIVEN
        corpus = tmp_path / "corpus"
        outside = tmp_path / "elsewhere" / "secret.txt"
        _touch(outside, "not corpus content")
        manifest_file = corpus / "manifest.json"
        _touch(
            manifest_file,
            json.dumps([{"path": str(outside), "title": "X", "lang": "en", "wave": 1}]),
        )

        # WHEN/THEN
        with pytest.raises(ValueError, match=re.escape(str(outside))):
            build_manifest(repo_root=tmp_path, private_dirs=[corpus], local_manifest=manifest_file)

    def test_rejects_a_dotdot_escape_from_the_allowed_root(self, tmp_path):
        """
        GIVEN an entry that starts inside the corpus and climbs out of it with ".."
        WHEN build_manifest runs
        THEN it raises ValueError: the allowlist compares resolved paths, not path strings
        """
        # GIVEN
        corpus = tmp_path / "corpus"
        _touch(tmp_path / "elsewhere" / "secret.txt", "not corpus content")
        manifest_file = corpus / "manifest.json"
        _touch(
            manifest_file,
            json.dumps(
                [
                    {
                        "path": "wave-1/../../elsewhere/secret.txt",
                        "title": "X",
                        "lang": "en",
                        "wave": 1,
                    }
                ]
            ),
        )

        # WHEN/THEN
        with pytest.raises(ValueError, match="outside every root"):
            build_manifest(repo_root=tmp_path, private_dirs=[corpus], local_manifest=manifest_file)

    def test_rejects_an_entry_with_an_unsupported_suffix(self, tmp_path):
        """
        GIVEN a manifest entry naming a file whose suffix maps to no known Kind
        WHEN build_manifest runs
        THEN it raises ValueError naming the offending entry and suffix
        """
        # GIVEN
        corpus = tmp_path / "corpus"
        _touch(corpus / "wave-1" / "report.docx", "not a supported corpus format")
        manifest_file = corpus / "manifest.json"
        _touch(
            manifest_file,
            json.dumps(
                [{"path": "wave-1/report.docx", "title": "Report", "lang": "en", "wave": 1}]
            ),
        )

        # WHEN/THEN
        with pytest.raises(ValueError, match="unsupported"):
            build_manifest(repo_root=tmp_path, private_dirs=[corpus], local_manifest=manifest_file)

    def test_missing_manifest_file_raises(self, tmp_path):
        """
        GIVEN a local_manifest path that does not exist
        WHEN build_manifest runs
        THEN it raises FileNotFoundError rather than silently skipping the local layer
        """
        # GIVEN
        missing = tmp_path / "corpus" / "manifest.json"

        # WHEN/THEN
        with pytest.raises(FileNotFoundError):
            build_manifest(repo_root=tmp_path, private_dirs=[], local_manifest=missing)

    def test_wave_2_entry_is_excluded_from_a_wave_1_build(self, tmp_path):
        """
        GIVEN one wave-1 and one wave-2 manifest entry
        WHEN build_manifest runs with wave=1
        THEN only the wave-1 entry is included; wave=2 includes both
        """
        # GIVEN
        corpus = tmp_path / "corpus"
        _touch(corpus / "wave-1" / "a.txt", "a")
        _touch(corpus / "wave-2" / "b.txt", "b")
        manifest_file = corpus / "manifest.json"
        _touch(
            manifest_file,
            json.dumps(
                [
                    {"path": "wave-1/a.txt", "title": "Wave 1", "lang": "en", "wave": 1},
                    {"path": "wave-2/b.txt", "title": "Wave 2", "lang": "en", "wave": 2},
                ]
            ),
        )

        # WHEN
        only_wave_1 = build_manifest(
            repo_root=tmp_path, private_dirs=[corpus], local_manifest=manifest_file, wave=1
        )
        both_waves = build_manifest(
            repo_root=tmp_path, private_dirs=[corpus], local_manifest=manifest_file, wave=2
        )

        # THEN
        assert [s.title for s in only_wave_1 if s.layer == "local"] == ["Wave 1"]
        assert sorted(s.title for s in both_waves if s.layer == "local") == ["Wave 1", "Wave 2"]
