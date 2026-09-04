#!/usr/bin/env python3
"""Generate the `## Contents` section of a Markdown document from its headings.

Written as a script rather than done by hand because a hand-kept table of contents
drifts the moment somebody renames a heading, and the drift is silent: the link still
looks like a link and simply lands nowhere. Running this again is the fix, and
`--check` is what tells you it is needed.

Two levels only. Three is a map of a map, and every document here that would need one
is a document that should have been split.

Anchors follow GitHub's slug rules: lowercase, spaces to hyphens, drop anything that is
not a letter, digit, hyphen or underscore. MkDocs' `toc` extension agrees on everything
this repository actually uses, which was checked against the built site rather than
assumed.

One thing this deliberately does not do is disambiguate repeated headings. GitHub appends
`-1`, `-2` to the second and later occurrences of the same text, and matching that would
be guesswork about which renderer numbered what. No document here repeats a heading, and
the check verified it; if one ever does, the link will point at the first occurrence and
this comment is where to start.

    python3 scripts/docs/toc.py --check  path...   # exit 1 if any is stale
    python3 scripts/docs/toc.py --write  path...   # rewrite in place
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*$")
FENCE = re.compile(r"^\s*```")
CONTENTS_TITLE = re.compile(r"^##\s+(Contents|Table of contents)\s*$", re.IGNORECASE)


def slug(text: str) -> str:
    """The anchor a heading gets.

    The last two lines are the ones that matter and the ones that were wrong first time.
    Dropping a character can leave a hyphen with nothing on one side of it, and both
    renderers collapse runs of hyphens and trim the ends afterwards. Skip that and a
    heading like `### Step 1: calculate the arithmetic mean (Γ)` yields a link ending in
    a stray hyphen, which points at nothing. The strict build caught exactly that.
    """
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links keep their text
    text = re.sub(r"[`*_]", "", text)
    text = text.strip().lower().replace(" ", "-")
    text = re.sub(r"[^a-z0-9\-_]", "", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


def headings(lines: list[str]) -> list[tuple[int, str]]:
    """Every h2 and h3 outside fenced code, in order, skipping the Contents section."""
    out: list[tuple[int, str]] = []
    in_fence = False
    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING.match(line)
        if m and not CONTENTS_TITLE.match(line):
            out.append((len(m.group(1)), m.group(2)))
    return out


def render(items: list[tuple[int, str]]) -> list[str]:
    body = ["## Contents", ""]
    for level, title in items:
        indent = "  " if level == 3 else ""
        body.append(f"{indent}- [{title}](#{slug(title)})")
    body.append("")
    return body


def _tidy(lines: list[str]) -> str:
    """Join, and never leave more than one blank line in a row."""
    text = "\n".join(lines) + "\n"
    return re.sub(r"\n{3,}", "\n\n", text)


def rebuild(text: str) -> str:
    lines = text.splitlines()
    items = headings(lines)
    if not items:
        return text

    start = next((i for i, l in enumerate(lines) if CONTENTS_TITLE.match(l)), None)
    if start is None:
        # Before the first heading, after the title and whatever intro follows it.
        first = next(i for i, l in enumerate(lines) if HEADING.match(l))
        while first > 0 and not lines[first - 1].strip():
            first -= 1
        return _tidy(lines[:first] + [""] + render(items) + lines[first:])

    end = start + 1
    while end < len(lines) and not HEADING.match(lines[end]):
        end += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return _tidy(lines[:start] + render(items) + lines[end:])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report staleness, change nothing")
    ap.add_argument("--write", action="store_true", help="rewrite in place")
    ap.add_argument("paths", nargs="+", type=Path)
    args = ap.parse_args()
    if args.check == args.write:
        ap.error("pass exactly one of --check or --write")

    stale: list[Path] = []
    for path in args.paths:
        original = path.read_text(encoding="utf-8")
        updated = rebuild(original)
        if updated == original:
            continue
        stale.append(path)
        if args.write:
            path.write_text(updated, encoding="utf-8")

    if args.write:
        print(f"rewrote {len(stale)} of {len(args.paths)}")
        return 0
    if stale:
        print("table of contents is stale in:")
        for p in stale:
            print(f"  {p}")
        print("fix with: python3 scripts/docs/toc.py --write <path>...")
        return 1
    print(f"{len(args.paths)} checked, all current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
