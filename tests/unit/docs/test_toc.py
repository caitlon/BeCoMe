"""Unit tests for the table-of-contents generator.

Every case here is a bug this script actually shipped. It rewrites fourteen documents in
place and gates CI, and it has been wrong twice: once dropping the Greek letters that
carry the method's notation, once eating the `1.` off a heading because a bare render
read it as a numbered list. Neither was caught by reading the code.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("pymdownx", reason="the docs extra supplies the slug function")

ROOT = Path(__file__).resolve().parents[3]


def _load():
    """Import the script by path, since `scripts/` is not a package.

    :return: The imported `toc` module
    """
    spec = importlib.util.spec_from_file_location("toc", ROOT / "scripts" / "docs" / "toc.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["toc"] = module
    spec.loader.exec_module(module)
    return module


toc = _load()


class TestSlug:
    """The anchor a heading gets, which has to satisfy GitHub and MkDocs at once."""

    @pytest.mark.parametrize(
        ("heading", "expected"),
        [
            ("Step 1: calculate the arithmetic mean (Γ)", "step-1-calculate-the-arithmetic-mean-γ"),  # noqa: RUF001, the surviving gamma is the assertion
            (
                "Step 4: calculate the maximum error (Δmax)",
                "step-4-calculate-the-maximum-error-δmax",
            ),
            ("What Δmax is telling you", "what-δmax-is-telling-you"),
        ],
    )
    def test_keeps_non_ascii_letters(self, heading, expected):
        """Greek notation survives, because GitHub keeps it and the site is configured to."""
        assert toc.slug(heading) == expected

    def test_keeps_an_underscore(self):
        """`DATABASE_URL` is a literal identifier, not emphasis; both renderers keep it."""
        assert toc.slug("Configuration via `DATABASE_URL`") == "configuration-via-database_url"

    def test_does_not_read_a_leading_number_as_a_list(self):
        """`1. Fuzzy triangular numbers` is heading text, so the `1.` is not a list marker."""
        assert toc.slug("1. Fuzzy triangular numbers") == "1-fuzzy-triangular-numbers"

    def test_strips_emphasis_and_links(self):
        """The renderers slug the rendered text, so markup is gone before slugging."""
        assert toc.slug("**Bold** and [a link](https://example.com)") == "bold-and-a-link"


class TestFences:
    """A heading inside a code sample is not a heading, whichever delimiter opened it."""

    @pytest.mark.parametrize("delim", ["```", "~~~"])
    def test_heading_inside_a_fence_is_not_collected(self, delim):
        """Both fence syntaxes are live here: `pymdownx.superfences` enables tildes."""
        # GIVEN a document whose only fenced block contains a heading-shaped line
        lines = f"## Real\n\n{delim}markdown\n## Fake\n{delim}\n".splitlines()

        # WHEN the headings are collected
        found = [title for _, title in toc.headings(lines)]

        # THEN the fenced one is absent
        assert found == ["Real"]

    def test_a_backtick_line_does_not_close_a_tilde_fence(self):
        """Closing takes the same character, so the run that opened the block is what counts."""
        lines = "~~~\n```\n## Fake\n~~~\n## Real\n".splitlines()
        assert [title for _, title in toc.headings(lines)] == ["Real"]

    def test_rebuild_leaves_a_tilde_block_intact(self):
        """The cut points are fence-aware too, so the closing delimiter is not orphaned."""
        # GIVEN a tilde block holding a stale-looking Contents example
        source = "# T\n\n## Alpha\n\n~~~markdown\n## Contents\n\n- [old](#old)\n~~~\n\n## Beta\n"

        # WHEN the document is rebuilt
        result = toc.rebuild(source)

        # THEN the block survives whole and the run is stable
        assert result.count("~~~") == 2
        assert "- [old](#old)" in result
        assert toc.rebuild(result) == result


class TestRefusesToDeleteWhatItDidNotWrite:
    """The section is replaced wholesale, so anything else in it would go silently."""

    def test_prose_under_contents(self):
        """A sentence a person wrote is not a generated entry, so the rewrite stops."""
        source = "# T\n\n## Contents\n\nRead the DB section first.\n\n## Alpha\n\nx\n"
        with pytest.raises(toc.NotOursError, match="Read the DB section first"):
            toc.rebuild(source)

    def test_the_tail_when_contents_comes_last(self):
        """With no heading after it the section runs to the end of the file."""
        source = "# T\n\n## Alpha\n\nbody\n\n## Contents\n\n- [Alpha](#alpha)\n\nClosing words.\n"
        with pytest.raises(toc.NotOursError, match="Closing words"):
            toc.rebuild(source)

    def test_a_genuinely_stale_section_still_rewrites(self):
        """The guard must not freeze the normal case it sits next to."""
        source = "# T\n\n## Contents\n\n- [gone](#gone)\n\n## Alpha\n\nx\n"
        assert "- [Alpha](#alpha)" in toc.rebuild(source)


class TestRebuild:
    """Placement and shape of the generated block."""

    def test_h3_is_indented_four_spaces(self):
        """Python-Markdown nests a sub-list from four, not two; GitHub accepts either."""
        result = toc.rebuild("## Alpha\n\n### Beta\n\nx\n")
        assert "    - [Beta](#beta)" in result

    def test_no_leading_blank_line_when_the_heading_starts_the_file(self):
        """`_splice` adds a separator only where there is something to separate from."""
        assert toc.rebuild("## Alpha\n\nx\n").startswith("## Contents\n")

    def test_a_document_without_headings_is_untouched(self):
        """Nothing to map, so nothing to write."""
        source = "# Title\n\njust prose\n"
        assert toc.rebuild(source) == source

    def test_is_idempotent(self):
        """CI runs `--check`, which is only meaningful if a second run changes nothing."""
        once = toc.rebuild("# T\n\nintro\n\n## Alpha\n\n### Beta\n\nx\n")
        assert toc.rebuild(once) == once


class TestDiscover:
    """Which documents the check covers when it is given no paths, as in CI."""

    def test_finds_the_same_set_from_any_directory(self):
        """`git ls-files` resolves against the working directory, so it is anchored to the root."""
        # GIVEN the set found from the repository root
        from_root = {p.resolve() for p in toc.discover()}

        # WHEN the tool runs from a subdirectory instead
        import os

        here = Path.cwd()
        try:
            os.chdir(ROOT / "docs")
            from_subdir = {p.resolve() for p in toc.discover()}
        finally:
            os.chdir(here)

        # THEN it covers the same documents either way
        assert from_root == from_subdir
        assert from_root

    def test_every_discovered_document_is_current(self):
        """The repository state itself: this is what CI asserts."""
        stale = [
            p
            for p in toc.discover()
            if toc.rebuild(p.read_text(encoding="utf-8")) != p.read_text(encoding="utf-8")
        ]
        assert stale == []
