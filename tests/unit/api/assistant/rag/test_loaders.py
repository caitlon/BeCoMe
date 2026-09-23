"""Unit tests for the document loaders (fakes only, no network)."""

import hashlib
import json
from pathlib import Path

from api.assistant.rag.corpus import CorpusSource
from api.assistant.rag.loaders import load_source


def _touch(path: Path, content: str) -> None:
    """Create a file with its parent directories, so tests read as plain trees."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestMarkdownLoader:
    """Plain markdown loads as one Document with the contracted metadata keys."""

    def test_loads_plain_markdown_with_metadata(self, tmp_path):
        """
        GIVEN a markdown CorpusSource with no snippet include
        WHEN load_source reads it
        THEN one Document carries the raw text and every contracted metadata key
        """
        # GIVEN
        md_path = tmp_path / "docs" / "user" / "what-it-does.md"
        content = "# What BeCoMe does\n\nBeCoMe aggregates expert opinions.\n"
        _touch(md_path, content)
        source = CorpusSource(
            path=md_path,
            layer="public",
            kind="markdown",
            title="What BeCoMe does",
            lang="en",
            url=None,
            wave=1,
        )

        # WHEN
        documents = load_source(source)

        # THEN
        assert len(documents) == 1
        doc = documents[0]
        assert doc.page_content == content
        assert doc.metadata == {
            "source": str(md_path),
            "layer": "public",
            "title": "What BeCoMe does",
            "lang": "en",
            "url": None,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "heading_path": "",
            "wave": 1,
        }

    def test_resolves_a_snippet_include_from_the_repository_root(self, tmp_path):
        """
        GIVEN a docs/dev/*.md file that snippet-includes another repo file
        WHEN load_source reads it
        THEN the resolved Document contains the target file's text, not the directive
        """
        # GIVEN
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "become"\n')
        _touch(tmp_path / "api" / "README.md", "# API\nBackend overview.\n")
        _touch(
            tmp_path / "docs" / "dev" / "api.md",
            '<!-- Included from api/README.md -->\n\n--8<-- "api/README.md"\n',
        )
        source = CorpusSource(
            path=tmp_path / "docs" / "dev" / "api.md",
            layer="public",
            kind="markdown",
            title="API",
            lang="en",
            url=None,
            wave=1,
        )

        # WHEN
        documents = load_source(source)

        # THEN
        assert "--8<--" not in documents[0].page_content
        assert "Backend overview." in documents[0].page_content


class TestI18nJsonLoader:
    """i18n JSON flattens into one Document per leaf section."""

    def test_flattens_nested_sections_with_heading_paths(self, tmp_path):
        """
        GIVEN a two-level nested i18n JSON document
        WHEN load_source reads it
        THEN each leaf section becomes its own Document with a joined heading_path
        """
        # GIVEN
        data = {
            "title": "Documentation",
            "gettingStarted": {
                "title": "Getting Started",
                "intro": "Start here.",
                "createProject": {
                    "title": "Creating a Project",
                    "step1": "Sign up.",
                },
            },
        }
        json_path = tmp_path / "frontend" / "src" / "i18n" / "locales" / "en" / "docs.json"
        _touch(json_path, json.dumps(data))
        source = CorpusSource(
            path=json_path,
            layer="public",
            kind="i18n_json",
            title="Documentation",
            lang="en",
            url=None,
            wave=1,
        )

        # WHEN
        documents = load_source(source)

        # THEN: root's own string field ("title"), gettingStarted's own fields, and
        # createProject's fields each become one section.
        by_heading = {doc.metadata["heading_path"]: doc.page_content for doc in documents}
        assert by_heading[""] == "Title: Documentation"
        assert by_heading["gettingStarted"] == "Title: Getting Started\nIntro: Start here."
        assert by_heading["gettingStarted > createProject"] == (
            "Title: Creating a Project\nStep1: Sign up."
        )
        assert all(doc.metadata["lang"] == "en" for doc in documents)
        assert all(doc.metadata["wave"] == 1 for doc in documents)
