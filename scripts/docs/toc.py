#!/usr/bin/env python3
"""Generate the `## Contents` section of a Markdown document from its headings.

Written as a script rather than done by hand because a hand-kept table of contents
drifts the moment somebody renames a heading, and the drift is silent: the link still
looks like a link and simply lands nowhere. Running this again is the fix, and
`--check` is what tells you it is needed.

Two levels only. Three is a map of a map, and every document here that would need one
is a document that should have been split.

These files are read by two renderers, GitHub and MkDocs, and the anchors have to work
in both. That is not free, because the two disagree: MkDocs' stock slug function drops
every non-ASCII letter, so the anchor for `### Step 1: calculate the arithmetic mean (Γ)`
stops at `mean` there while GitHub keeps the gamma on the end, and no single link reaches
both. So the site is configured to use GitHub's rule instead, in `mkdocs.yml`, and this
script imports the same function rather than reimplementing it. One algorithm, two
renderers, nothing to keep in step by hand. A hand-written version was wrong on five
links, on exactly the headings that carry the method's Greek notation.

One thing this deliberately does not do is disambiguate repeated headings. GitHub appends
`-1`, `-2` to the second and later occurrences of the same text, and matching that would
be guesswork about which renderer numbered what. No document here repeats an h2 or h3,
and the check verified it; if one ever does, the link will point at the first occurrence
and this comment is where to start.

    uv run python scripts/docs/toc.py --check   # exit 1 if any is stale
    uv run python scripts/docs/toc.py --write   # rewrite in place

With no paths it works on every tracked document long enough to want a map, which is
what CI runs; `discover` is where that means something. Naming paths overrides it. Run
it from the repository root, and with the `docs` extra, which is where `markdown` and
`pymdown-extensions` live.
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from pathlib import Path

import markdown
from pymdownx.slugs import slugify as _github_slugify

HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*$")
FENCE = re.compile(r"^\s*```")
CONTENTS_TITLE = re.compile(r"^##\s+(Contents|Table of contents)\s*$", re.IGNORECASE)
TAG = re.compile(r"<[^>]+>")

_slug = _github_slugify(case="lower")


def slug(text: str) -> str:
    """The anchor a heading gets, in both renderers.

    Both of them slug the heading's *rendered* text, so `` `DATABASE_URL` `` arrives
    without its backticks and `**Bold**` without its asterisks. Rendering the line and
    stripping the tags is how you get that text; filtering the punctuation out by hand
    is how you lose the underscore in `DATABASE_URL`, which is a literal character that
    survives both renderers and which the first version of this function deleted.

    The `## ` matters. Render `1. Fuzzy triangular numbers` on its own and Markdown reads
    it as a numbered list and eats the `1.`; inside a heading, which is where this text
    actually lives, the same characters are ordinary text. The strict build caught that
    one, which is the second time it has caught this function.
    """
    rendered = TAG.sub("", markdown.markdown("## " + text))
    return _slug(html.unescape(rendered).strip(), "-")


def _fenced(lines: list[str]) -> list[bool]:
    """True for every line a fenced code block owns, its delimiters included.

    Needed three times over, and the reason is that `## Contents` inside a fenced
    example is not a heading. Miss that in the two places `rebuild` cuts the document
    and it cuts inside the fence, orphaning the closing delimiter and promoting the
    example's text into live headings.
    """
    mask: list[bool] = []
    in_fence = False
    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence
            mask.append(True)
            continue
        mask.append(in_fence)
    return mask


def headings(lines: list[str]) -> list[tuple[int, str]]:
    """Every h2 and h3 outside fenced code, in order, skipping the Contents section."""
    out: list[tuple[int, str]] = []
    for line, fenced in zip(lines, _fenced(lines), strict=True):
        if fenced:
            continue
        m = HEADING.match(line)
        if m and not CONTENTS_TITLE.match(line):
            out.append((len(m.group(1)), m.group(2)))
    return out


def render(items: list[tuple[int, str]]) -> list[str]:
    """The Contents block itself, without the blank lines that separate it.

    Four spaces for an h3, not two. Python-Markdown nests a sub-list only from the
    parent marker's content column, which is two, plus its own indent; at two spaces it
    emits a flat list and the site shows one level where the document has two. GitHub
    accepts either, so four is the one that works in both.
    """
    body = ["## Contents", ""]
    for level, title in items:
        indent = "    " if level == 3 else ""
        body.append(f"{indent}- [{title}](#{slug(title)})")
    return body


def _splice(before: list[str], block: list[str], after: list[str]) -> str:
    """Put the block between the two halves, separated by exactly one blank line.

    Deliberately narrow. The first version normalised blank lines across the whole
    document, which reached into a code sample in `api/db/README.md` and closed up the
    gap between two statements. A tool that rewrites a table of contents has no business
    touching a line it did not write.
    """
    before = list(before)
    while before and not before[-1].strip():
        before.pop()
    after = list(after)
    while after and not after[0].strip():
        after.pop(0)

    out = [*before, ""] if before else []
    out += block
    if after:
        out += ["", *after]
    return "\n".join(out) + "\n"


def rebuild(text: str) -> str:
    lines = text.splitlines()
    items = headings(lines)
    if not items:
        return text

    fenced = _fenced(lines)
    is_heading = [
        bool(HEADING.match(line)) and not f for line, f in zip(lines, fenced, strict=True)
    ]

    start = next(
        (i for i, line in enumerate(lines) if CONTENTS_TITLE.match(line) and not fenced[i]),
        None,
    )
    if start is None:
        # Before the first heading, after the title and whatever intro follows it.
        first = is_heading.index(True)
        return _splice(lines[:first], render(items), lines[first:])

    end = start + 1
    while end < len(lines) and not is_heading[end]:
        end += 1
    return _splice(lines[:start], render(items), lines[end:])


LONG_ENOUGH_LINES = 100
LONG_ENOUGH_SECTIONS = 6


def discover() -> list[Path]:
    """Every tracked Markdown file long enough that a reader would want a map of it.

    Long enough means over a hundred lines or more than six sections. Both, because
    either alone lets a document through that plainly needs one: `examples/data` is
    short and densely sectioned, `development.md` is the reverse.

    This lives here rather than as a list of filenames in the CI workflow so that the
    fifteenth document to cross the line gets checked without anyone remembering to add
    it. A list would stay green while quietly covering less each month.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "*.md"],  # noqa: S607, fixed argv, no shell, no input
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    out = []
    for name in filter(None, tracked):
        path = Path(name)
        lines = path.read_text(encoding="utf-8").splitlines()
        sections = sum(1 for level, _ in headings(lines) if level == 2)
        if len(lines) > LONG_ENOUGH_LINES or sections > LONG_ENOUGH_SECTIONS:
            out.append(path)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report staleness, change nothing")
    ap.add_argument("--write", action="store_true", help="rewrite in place")
    ap.add_argument("paths", nargs="*", type=Path, help="default: every long tracked document")
    args = ap.parse_args()
    if args.check == args.write:
        ap.error("pass exactly one of --check or --write")
    paths = args.paths or discover()

    stale: list[Path] = []
    for path in paths:
        original = path.read_text(encoding="utf-8")
        updated = rebuild(original)
        if updated == original:
            continue
        stale.append(path)
        if args.write:
            path.write_text(updated, encoding="utf-8")

    if args.write:
        print(f"rewrote {len(stale)} of {len(paths)}")
        return 0
    if stale:
        print("table of contents is stale in:")
        for p in stale:
            print(f"  {p}")
        print("fix with: uv run python scripts/docs/toc.py --write <path>...")
        return 1
    print(f"{len(paths)} checked, all current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
