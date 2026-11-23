"""Unit tests for the ASCII check: code and comments fail, strings and Markdown cells pass."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
ARROW = "→"
E_ACUTE = "é"
HIT = "non-ASCII in code or comment:"


def _load():
    """Import the script by path, since `scripts/` is not a package."""
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
    """Write a UTF-8 file under ``tmp_path`` and return its path."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _notebook(*cells: tuple[str, str]) -> str:
    """Build notebook JSON from ``(cell_type, source)`` pairs."""
    return json.dumps(
        {
            "cells": [
                {"cell_type": kind, "source": src.splitlines(keepends=True)} for kind, src in cells
            ],
            "nbformat": 4,
        }
    )


def _assert_messages(messages: list[str], prefixes: list[str]) -> None:
    """Assert one message per prefix, each starting with it."""
    assert len(messages) == len(prefixes), messages
    for message, prefix in zip(messages, prefixes, strict=True):
        assert message.startswith(prefix), message


class TestPythonSource:
    """What a `.py` file may and may not hold."""

    @pytest.mark.parametrize(
        ("source", "prefixes"),
        [
            pytest.param(f"x = 1\n# a {ARROW} b\n", [f"mod.py:2: {HIT} {ARROW}"], id="comment"),
            pytest.param(f"x = 1  # caf{E_ACUTE}\n", [f"mod.py:1: {HIT} {E_ACUTE}"], id="trailing"),
            pytest.param(
                f"# {ARROW}{ARROW}{E_ACUTE}{ARROW}\n",
                [f"mod.py:1: {HIT} {ARROW}{E_ACUTE}"],
                id="distinct-chars-once",
            ),
            pytest.param(f"caf{E_ACUTE} = 1\n", [f"mod.py:1: {HIT} {E_ACUTE}"], id="identifier"),
            pytest.param(
                f"x = 1\ndef caf{E_ACUTE}():\n    return 1\n", [f"mod.py:2: {HIT}"], id="function"
            ),
            pytest.param(f"x = 1 {ARROW} 2\n", [f"mod.py:1: {HIT} {ARROW}"], id="stray-symbol"),
            pytest.param(
                f'x = 1\ny = f"{{caf{E_ACUTE}}}"\n', [f"mod.py:2: {HIT}"], id="f-string-field"
            ),
            pytest.param("x = (1,\n", ["mod.py: could not tokenize:"], id="untokenizable"),
            pytest.param(
                f"# {ARROW}\nx = (1,\n",
                [f"mod.py:1: {HIT} {ARROW}", "mod.py: could not tokenize:"],
                id="hit-kept-before-tokenize-error",
            ),
        ],
    )
    def test_failures(self, tmp_path, source, prefixes):
        messages = check.check_file(_write(tmp_path, "mod.py", source), "mod.py")

        _assert_messages(messages, prefixes)

    @pytest.mark.parametrize(
        "source",
        [
            f'x = "caf{E_ACUTE} {ARROW}"\n',
            f"x = 'caf{E_ACUTE}'\n",
            f'"""Docstring with {E_ACUTE} and {ARROW}."""\n',
            f'def f():\n    """Return caf{E_ACUTE}."""\n    return 1\n',
            f'x = f"caf{E_ACUTE} {{1 + 1}} {ARROW}"\n',
            f'x = f"{{1}} caf{E_ACUTE}"\n',
            f'x = b"abc" + "{E_ACUTE}"\n',
            f'x = """a\n{E_ACUTE}\nb"""\n',
        ],
    )
    def test_unicode_in_strings_passes(self, tmp_path, source):
        assert check.check_file(_write(tmp_path, "mod.py", source), "mod.py") == []

    def test_unreadable_file_fails(self, tmp_path):
        messages = check.check_file(tmp_path / "missing.py", "missing.py")

        _assert_messages(messages, ["missing.py: could not read:"])

    def test_clean_run_prints_an_ok_summary(self, tmp_path, capsys):
        first = _write(tmp_path, "a.py", "x = 1  # plain\n")
        second = _write(tmp_path, "b.py", f'y = "{E_ACUTE}"\n')

        assert check.main([str(first), str(second)]) == 0
        assert capsys.readouterr().out == "OK: 2 files scanned, code and comments are ASCII\n"

    def test_one_bad_file_fails_the_whole_run(self, tmp_path, capsys):
        good = _write(tmp_path, "good.py", "x = 1\n")
        bad = _write(tmp_path, "bad.py", f"# {ARROW}\n")

        assert check.main([str(good), str(bad)]) == 1
        assert capsys.readouterr().out.splitlines() == [f"{bad}:1: {HIT} {ARROW}"]


class TestNotebook:
    """Only the code cells of a notebook are checked."""

    @pytest.mark.parametrize(
        ("text", "prefixes"),
        [
            pytest.param(
                _notebook(("markdown", f"# T {E_ACUTE}\n"), ("code", f"x = 1\n# n {ARROW}\n")),
                [f"nb.ipynb:cell 2:line 2: {HIT} {ARROW}"],
                id="code-cell-comment",
            ),
            pytest.param(
                _notebook(("markdown", f"Caf{E_ACUTE} {ARROW}\n"), ("code", "x = 1\n")),
                [],
                id="markdown-cell",
            ),
            pytest.param(_notebook(("code", f'print("caf{E_ACUTE}")\n')), [], id="string-in-code"),
            pytest.param(
                _notebook(("code", "x = 1\n"), ("code", "y = (1,\n")),
                ["nb.ipynb:cell 2: could not tokenize:"],
                id="untokenizable-cell",
            ),
            pytest.param(
                json.dumps({"cells": [{"cell_type": "code", "source": f"# {ARROW}\n"}]}),
                [f"nb.ipynb:cell 1:line 1: {HIT} {ARROW}"],
                id="source-as-one-string",
            ),
            pytest.param("{not json", ["nb.ipynb: could not read notebook:"], id="invalid-json"),
            pytest.param(
                '{"cells": null}', ["nb.ipynb: could not read notebook:"], id="cells-null"
            ),
            pytest.param(
                '{"cells": [{"cell_type": "code", "source": null}]}',
                ["nb.ipynb: could not read notebook:"],
                id="source-null",
            ),
        ],
    )
    def test_notebook(self, tmp_path, text, prefixes):
        messages = check.check_file(_write(tmp_path, "nb.ipynb", text), "nb.ipynb")

        _assert_messages(messages, prefixes)


class TestRepository:
    """The tracked tree itself."""

    def test_tracked_files_pass(self, capsys):
        assert check.main([]) == 0, capsys.readouterr().out

    def test_default_scan_includes_the_tracked_notebook(self):
        notebook = ROOT / "examples" / "visualizations" / "visualize_become.ipynb"

        assert notebook in check.tracked_files()
