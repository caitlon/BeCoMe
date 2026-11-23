#!/usr/bin/env python3
"""Fail when Python code or a comment holds a non-ASCII character.

The project rule is that code and comments stay ASCII. Unicode is allowed in string
literals (including docstrings and the text parts of f-strings, where the Czech case-study
text lives) and in the Markdown cells of notebooks. The source is tokenized, so a string
never raises a false hit; every other token (comment, name, operator) is checked.

With no arguments the script scans every tracked ``.py`` and ``.ipynb`` file. A file that
cannot be tokenized is reported and fails the run, never skipped.

Usage::

    python scripts/ci/check_ascii_comments.py [PATH ...]

Exit status: 0 when every file is clean, 1 on any hit or unreadable file.
"""

import io
import json
import subprocess
import sys
import tokenize
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAX_ASCII = 0x7F


def _skipped_token_types() -> frozenset[int]:
    """Collect the token types whose text may hold Unicode or carries no code.

    String-like tokens are the first group. The f-string and t-string parts exist only on
    newer Python versions, so they are looked up by name.

    :return: The set of token type numbers to skip
    """
    types = {
        tokenize.STRING,
        tokenize.ENCODING,
        tokenize.NEWLINE,
        tokenize.NL,
        tokenize.INDENT,
        tokenize.DEDENT,
    }
    for name in (
        "FSTRING_START",
        "FSTRING_MIDDLE",
        "FSTRING_END",
        "TSTRING_START",
        "TSTRING_MIDDLE",
        "TSTRING_END",
    ):
        token_type = getattr(tokenize, name, None)
        if token_type is not None:
            types.add(token_type)
    return frozenset(types)


SKIPPED_TOKEN_TYPES = _skipped_token_types()


def scan_source(source: str) -> tuple[list[tuple[int, str]], str | None]:
    """Find the non-ASCII characters outside string literals in Python source.

    :param source: The Python source text
    :return: The ``(line, characters)`` hits and, when tokenizing failed part-way, the error
        message (the hits found before the failure are kept)
    """
    hits: list[tuple[int, str]] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type in SKIPPED_TOKEN_TYPES:
                continue
            bad = [char for char in token.string if ord(char) > MAX_ASCII]
            if bad:
                hits.append((token.start[0], "".join(dict.fromkeys(bad))))
    except (tokenize.TokenError, SyntaxError) as exc:
        return hits, str(exc)
    return hits, None


def _notebook_cells(text: str) -> Iterator[tuple[int, str]]:
    """Yield the code cells of a notebook with their one-based cell numbers.

    :param text: The notebook JSON text
    :return: ``(cell number, source)`` pairs for the cells of type ``code``
    """
    notebook = json.loads(text)
    for number, cell in enumerate(notebook.get("cells", []), start=1):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        yield number, source if isinstance(source, str) else "".join(source)


def check_file(path: Path, label: str) -> list[str]:
    """Check one file and describe every problem found in it.

    :param path: The file to read
    :param label: The name to print for the file
    :return: One message per problem, empty when the file is clean
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{label}: could not read: {exc}"]

    messages: list[str] = []
    if path.suffix == ".ipynb":
        try:
            cells = list(_notebook_cells(text))
        except (ValueError, AttributeError) as exc:
            return [f"{label}: could not read notebook: {exc}"]
        for number, source in cells:
            hits, error = scan_source(source)
            messages.extend(
                f"{label}:cell {number}:line {line}: non-ASCII in code or comment: {chars}"
                for line, chars in hits
            )
            if error:
                messages.append(f"{label}:cell {number}: could not tokenize: {error}")
    else:
        hits, error = scan_source(text)
        messages.extend(
            f"{label}:{line}: non-ASCII in code or comment: {chars}" for line, chars in hits
        )
        if error:
            messages.append(f"{label}: could not tokenize: {error}")
    return messages


def tracked_files() -> list[Path]:
    """List the tracked Python files and notebooks of the repository.

    :return: The paths, resolved against the repository root
    """
    result = subprocess.run(
        ["git", "ls-files", "*.py", "*.ipynb"],  # noqa: S607 - git is resolved from PATH
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line]


def main(argv: list[str]) -> int:
    """Run the check over the given files, or over every tracked file.

    :param argv: The file paths; empty means every tracked ``.py`` and ``.ipynb`` file
    :return: The exit status, 1 when any problem was found
    """
    paths = [Path(arg) for arg in argv] if argv else tracked_files()
    messages: list[str] = []
    for path in paths:
        label = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
        messages.extend(check_file(path, label))
    if messages:
        print("\n".join(messages))
        return 1
    print(f"OK: {len(paths)} files scanned, code and comments are ASCII")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
