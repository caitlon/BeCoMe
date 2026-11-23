"""Unit tests for the ASCII check of Python code and comments.

The rule is that code and comments stay ASCII while string literals, docstrings and the
Markdown cells of notebooks may hold Unicode (the Czech case-study text). The tests cover
both directions: what must fail and what must pass.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
ARROW = "→"
E_ACUTE = "é"


def _load():
    """Import the script by path, since `scripts/` is not a package.

    :return: The imported `check_ascii_comments` module
    """
    spec = importlib.util.spec_from_file_location(
        "check_ascii_comments", ROOT / "scripts" / "ci" / "check_ascii_comments.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_ascii_comments"] = module
    spec.loader.exec_module(module)
    return module


check = _load()


def _write(tmp_path: Path, name: str, text: str) -> Path:
    """Write a file under ``tmp_path`` as UTF-8.

    :param tmp_path: The test directory
    :param name: The file name
    :param text: The file content
    :return: The path written
    """
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _notebook(*cells: tuple[str, str]) -> str:
    """Build notebook JSON from ``(cell_type, source)`` pairs.

    :param cells: The cells in order
    :return: The notebook JSON text
    """
    return json.dumps(
        {
            "cells": [
                {"cell_type": kind, "source": source.splitlines(keepends=True)}
                for kind, source in cells
            ],
            "nbformat": 4,
            "nbformat_minor": 5,
        }
    )


class TestPythonSource:
    """What a `.py` file may and may not hold."""

    def test_comment_hit_names_file_line_and_characters(self, tmp_path, capsys):
        # GIVEN a comment with a Unicode arrow on line 2
        path = _write(tmp_path, "mod.py", f"x = 1\n# a {ARROW} b\n")

        # WHEN the check runs on it
        status = check.main([str(path)])

        # THEN it fails and says where
        assert status == 1
        assert capsys.readouterr().out.splitlines() == [
            f"{path}:2: non-ASCII in code or comment: {ARROW}"
        ]

    def test_trailing_comment_is_checked(self, tmp_path):
        path = _write(tmp_path, "mod.py", f"x = 1  # caf{E_ACUTE}\n")

        assert check.check_file(path, "mod.py") == [
            f"mod.py:1: non-ASCII in code or comment: {E_ACUTE}"
        ]

    def test_distinct_characters_are_listed_once(self, tmp_path):
        path = _write(tmp_path, "mod.py", f"# {ARROW}{ARROW}{E_ACUTE}{ARROW}\n")

        assert check.check_file(path, "mod.py") == [
            f"mod.py:1: non-ASCII in code or comment: {ARROW}{E_ACUTE}"
        ]

    @pytest.mark.parametrize(
        "source",
        [
            pytest.param(f'x = "caf{E_ACUTE} {ARROW}"\n', id="plain-string"),
            pytest.param(f"x = 'caf{E_ACUTE}'\n", id="single-quoted"),
            pytest.param(f'"""Docstring with {E_ACUTE} and {ARROW}."""\n', id="module-docstring"),
            pytest.param(
                f'def f():\n    """Return caf{E_ACUTE}."""\n    return 1\n', id="function-docstring"
            ),
            pytest.param(f'x = f"caf{E_ACUTE} {{1 + 1}} {ARROW}"\n', id="f-string-text"),
            pytest.param(f'x = f"{{1}} caf{E_ACUTE}"\n', id="f-string-after-field"),
            pytest.param(f'x = b"abc" + "{E_ACUTE}"\n', id="bytes-then-string"),
            pytest.param(f'x = """a\n{E_ACUTE}\nb"""\n', id="multi-line-string"),
        ],
    )
    def test_unicode_in_strings_passes(self, tmp_path, source):
        path = _write(tmp_path, "mod.py", source)

        assert check.check_file(path, "mod.py") == []

    @pytest.mark.parametrize(
        "source",
        [
            pytest.param(f"caf{E_ACUTE} = 1\n", id="identifier"),
            pytest.param(f"def caf{E_ACUTE}():\n    return 1\n", id="function-name"),
            pytest.param(f"x = 1 {ARROW} 2\n", id="stray-symbol"),
            pytest.param(f'x = f"{{caf{E_ACUTE}}}"\n', id="f-string-field-expression"),
        ],
    )
    def test_unicode_in_code_fails(self, tmp_path, source):
        path = _write(tmp_path, "mod.py", source)

        messages = check.check_file(path, "mod.py")

        assert len(messages) == 1
        assert messages[0].startswith("mod.py:") and "non-ASCII" in messages[0]

    def test_untokenizable_file_fails_instead_of_being_skipped(self, tmp_path, capsys):
        path = _write(tmp_path, "broken.py", "x = (1,\n")

        status = check.main([str(path)])

        assert status == 1
        assert f"{path}: could not tokenize:" in capsys.readouterr().out

    def test_hits_before_a_tokenize_error_are_kept(self, tmp_path):
        path = _write(tmp_path, "broken.py", f"# {ARROW}\nx = (1,\n")

        messages = check.check_file(path, "broken.py")

        assert messages[0] == f"broken.py:1: non-ASCII in code or comment: {ARROW}"
        assert messages[1].startswith("broken.py: could not tokenize:")

    def test_unreadable_file_fails(self, tmp_path):
        messages = check.check_file(tmp_path / "missing.py", "missing.py")

        assert len(messages) == 1
        assert messages[0].startswith("missing.py: could not read:")

    def test_clean_run_prints_an_ok_summary(self, tmp_path, capsys):
        first = _write(tmp_path, "a.py", "x = 1  # plain\n")
        second = _write(tmp_path, "b.py", f'y = "{E_ACUTE}"\n')

        status = check.main([str(first), str(second)])

        assert status == 0
        assert capsys.readouterr().out == "OK: 2 files scanned, code and comments are ASCII\n"

    def test_one_bad_file_fails_the_whole_run(self, tmp_path, capsys):
        good = _write(tmp_path, "good.py", "x = 1\n")
        bad = _write(tmp_path, "bad.py", f"# {ARROW}\n")

        status = check.main([str(good), str(bad)])

        assert status == 1
        assert capsys.readouterr().out.count("\n") == 1


class TestNotebook:
    """Only the code cells of a notebook are checked."""

    def test_code_cell_comment_fails_with_cell_and_line(self, tmp_path):
        text = _notebook(
            ("markdown", f"# Title {E_ACUTE}\n"),
            ("code", f"x = 1\n# note {ARROW}\n"),
        )
        path = _write(tmp_path, "nb.ipynb", text)

        assert check.check_file(path, "nb.ipynb") == [
            f"nb.ipynb:cell 2:line 2: non-ASCII in code or comment: {ARROW}"
        ]

    def test_markdown_cell_with_unicode_passes(self, tmp_path):
        text = _notebook(("markdown", f"Caf{E_ACUTE} {ARROW} done\n"), ("code", "x = 1\n"))
        path = _write(tmp_path, "nb.ipynb", text)

        assert check.check_file(path, "nb.ipynb") == []

    def test_unicode_string_in_code_cell_passes(self, tmp_path):
        text = _notebook(("code", f'print("caf{E_ACUTE}")\n'))
        path = _write(tmp_path, "nb.ipynb", text)

        assert check.check_file(path, "nb.ipynb") == []

    def test_untokenizable_code_cell_fails(self, tmp_path):
        text = _notebook(("code", "x = 1\n"), ("code", "y = (1,\n"))
        path = _write(tmp_path, "nb.ipynb", text)

        messages = check.check_file(path, "nb.ipynb")

        assert len(messages) == 1
        assert messages[0].startswith("nb.ipynb:cell 2: could not tokenize:")

    def test_source_stored_as_one_string_is_read(self, tmp_path):
        text = json.dumps(
            {"cells": [{"cell_type": "code", "source": f"# {ARROW}\n"}], "nbformat": 4}
        )
        path = _write(tmp_path, "nb.ipynb", text)

        assert check.check_file(path, "nb.ipynb") == [
            f"nb.ipynb:cell 1:line 1: non-ASCII in code or comment: {ARROW}"
        ]

    def test_invalid_json_fails(self, tmp_path):
        path = _write(tmp_path, "nb.ipynb", "{not json")

        messages = check.check_file(path, "nb.ipynb")

        assert len(messages) == 1
        assert messages[0].startswith("nb.ipynb: could not read notebook:")


class TestRepository:
    """The tracked tree itself."""

    def test_tracked_files_pass(self, capsys):
        # GIVEN the files git tracks, found without arguments
        status = check.main([])

        # THEN none holds non-ASCII code or comments
        assert status == 0, capsys.readouterr().out
