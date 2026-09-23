"""Unit tests for the public-layer corpus manifest (fakes only, no network)."""

from pathlib import Path

import pytest

from api.assistant.rag.corpus import EXCLUDED_PUBLIC, CorpusSource, build_manifest


def _touch(path: Path, content: str = "content") -> None:
    """Create a file with its parent directories, so tests read as plain trees."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
        # (Task 124.6+) opens source.path directly, with no repo_root of its own to resolve
        # a relative one against.
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
