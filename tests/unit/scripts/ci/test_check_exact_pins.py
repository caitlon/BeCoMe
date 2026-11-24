"""Unit tests for the exact-pin check: every form that widens an install fails."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]


def _load():
    """Import the script by path, since `scripts/` is not a package."""
    spec = importlib.util.spec_from_file_location(
        "check_exact_pins", ROOT / "scripts" / "ci" / "check_exact_pins.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_exact_pins"] = module
    spec.loader.exec_module(module)
    return module


check = _load()


def _run(tmp_path: Path, name: str, content) -> tuple[list[str], int]:
    """Write a manifest (TOML text or a JSON-able object) and check it."""
    path = tmp_path / name
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return check.check_file(path, name)


def _toml(body: str) -> str:
    """Prefix a pyproject body with the `[project]` header."""
    return f"[project]\nname = 'x'\n{body}"


def _words(text: str) -> list[str]:
    """Split a double-space separated list of specs, which may hold single spaces."""
    return text.split("  ")


PYTHON_EXACT = _words(
    "fastapi==0.115.0  fastapi[standard]==0.115.0  uvicorn[standard, extra]==0.30.1  "
    "pywin32==306 ; sys_platform == 'win32'  pywin32==306; sys_platform == 'win32'  "
    "uvloop[x]==0.21.0; python_version >= '3.12' and sys_platform != 'win32'  "
    "Pillow==11.0.0  typing_extensions==4.12.2  zope.interface==7.1.1  pkg==1.0.0rc1  "
    "pkg==2024.1.1.post2  pkg==1.0.0+local.1  pkg==1!2.0  httpx==1.2.3  httpx==1.2.4"
)
PYTHON_LOOSE = [
    *_words(
        "fastapi>=0.115.0  fastapi~=0.115.0  fastapi!=0.115.0  fastapi<1  fastapi>1  fastapi<=1  "
        "fastapi===0.115.0  fastapi==0.115.*  fastapi==1.*  fastapi  fastapi[standard]  "
        "fastapi @ https://example.com/fastapi-0.115.0.tar.gz  fastapi==1,<2  fastapi>=1,<2  "
        "fastapi==  fastapi==latest  fastapi>=1 ; python_version >= '3.12'"
    ),
    "fastapi==0.115.0\n",
]
NPM_EXACT = _words(
    "1.2.3  0.0.0  10.20.30  5.1.0  5.2.0  1.2.3-rc.1  1.2.3-beta  2.0.0-alpha.1+build.5  "
    "1.2.3+20260101"
)
NPM_LOOSE = [
    *_words(
        "^1.2.3  ~1.2.3  =1.2.3  v1.2.3  >=1.2.3  >1.2.3  <2.0.0  1.x  1.2.x  1.2  1  *  latest  "
        "next  beta  1.2.3 - 2.0.0  1.2.3 || 2.0.0  ^1.2.3 || ^2.0.0  https://example.com/p.tgz  "
        "git+https://github.com/org/pkg.git  git://github.com/org/pkg.git#v1.2.3  github:org/pkg  "
        "org/pkg  file:../pkg  link:../pkg  workspace:*  npm:other@1.2.3  $left-pad  01.2.3"
    ),
    "",
    "1.2.3\n",
]


# One lost double-space separator would merge two specs into a single case without a failure.
assert (len(PYTHON_EXACT), len(PYTHON_LOOSE), len(NPM_EXACT), len(NPM_LOOSE)) == (15, 18, 9, 31), (
    "a double-space separator was lost"
)


class TestPythonPins:
    """Requirement strings in `pyproject.toml`."""

    @pytest.mark.parametrize("spec", PYTHON_EXACT)
    def test_exact_pin_passes(self, tmp_path, spec):
        found, count = _run(
            tmp_path, "pyproject.toml", _toml(f"dependencies = {json.dumps([spec])}\n")
        )

        assert (found, count) == ([], 1)

    @pytest.mark.parametrize("spec", PYTHON_LOOSE)
    def test_loose_requirement_fails(self, tmp_path, spec):
        offenders, _ = _run(
            tmp_path, "pyproject.toml", _toml(f"dependencies = {json.dumps([spec])}\n")
        )

        assert offenders == [f"pyproject.toml: project.dependencies: fastapi: {json.dumps(spec)}"]

    @pytest.mark.parametrize(
        ("body", "offenders", "checked"),
        [
            pytest.param(
                "dependencies = ['a==1.0.0']\n[project.optional-dependencies]\n"
                "dev = ['pytest==8.0.0', 'ruff>=0.5']\ndocs = ['mkdocs==1.6.0']\n",
                ['project.optional-dependencies.dev: ruff: "ruff>=0.5"'],
                4,
                id="optional-dependencies",
            ),
            pytest.param(
                "[dependency-groups]\nlint = ['ruff==0.5.0']\n"
                "dev = [{include-group = 'lint'}, 'pytest~=8.0']\n",
                ['dependency-groups.dev: pytest: "pytest~=8.0"'],
                2,
                id="groups-skip-include",
            ),
            pytest.param(
                "dependencies = [{include-group = 'lint'}, {a = 'b'}]\n",
                [
                    "project.dependencies: {'include-group': 'lint'}: "
                    '{"include-group": "lint"}',
                    "project.dependencies: {'a': 'b'}: {\"a\": \"b\"}",
                ],
                2,
                id="dict-in-project-dependencies",
            ),
            pytest.param(
                "[dependency-groups]\n"
                "dev = [{include-group = 'lint'}, {include-group = 'a', extra = 1}, {a = 'b'}]\n",
                [
                    "dependency-groups.dev: {'include-group': 'a', 'extra': 1}: "
                    '{"include-group": "a", "extra": 1}',
                    "dependency-groups.dev: {'a': 'b'}: {\"a\": \"b\"}",
                ],
                2,
                id="other-dict-in-group",
            ),
            pytest.param(
                "dependencies = [1979-05-27, 3]\n",
                ['project.dependencies: 1979-05-27: "1979-05-27"', "project.dependencies: 3: 3"],
                2,
                id="non-string-entries",
            ),
            *(
                pytest.param(
                    f"[tool.uv]\n{key} = ['a==1.0.0', 'b>=2.0.0']\n",
                    [f'tool.uv.{key}: b: "b>=2.0.0"'],
                    2,
                    id=key,
                )
                for key in ("dev-dependencies", "override-dependencies", "constraint-dependencies")
            ),
            pytest.param(
                "dependencies = ['a==1.0.0']\n[build-system]\nrequires = ['hatchling>=1.0']\n",
                [],
                1,
                id="build-system-not-checked",
            ),
            pytest.param(
                "requires-python = '>=3.13'\ndependencies = ['a==1.0.0']\n", [], 1, id="python"
            ),
            pytest.param(
                "dependencies = ['a==1.0.0']\n[tool.uv.sources]\na = { git = 'https://x.test/a' }\n"
                "b = { path = '../b' }\nc = [{ url = 'https://x.test/c', marker = 'os_name == \"nt\"' }]\n",
                [
                    'tool.uv.sources: a: {"git": "https://x.test/a"}',
                    'tool.uv.sources: b: {"path": "../b"}',
                    'tool.uv.sources: c: [{"url": "https://x.test/c", "marker": "os_name == \\"nt\\""}]',
                ],
                4,
                id="uv-sources-git-path-list",
            ),
            pytest.param(
                "[tool.uv.sources]\na = 'a==1.0.0'\n",
                ['tool.uv.sources: a: "a==1.0.0"'],
                1,
                id="uv-source-that-looks-like-a-pin",
            ),
            pytest.param(
                "dependencies = ['a==1.0.0']\n[tool.uv]\ndev-dependencies = ['b==2.0.0']\n",
                [],
                2,
                id="uv-without-sources",
            ),
        ],
    )
    def test_structure(self, tmp_path, body, offenders, checked):
        found, count = _run(tmp_path, "pyproject.toml", _toml(body))

        assert found == [f"pyproject.toml: {line}" for line in offenders]
        assert count == checked

    @pytest.mark.parametrize(
        ("body", "reason"),
        [
            ("dependencies = 1\n", "project.dependencies is not a list"),
            ("[tool.uv]\nsources = 1\n", "tool.uv.sources is not a table"),
        ],
    )
    def test_malformed_table_reports_instead_of_raising(self, tmp_path, body, reason):
        found, count = _run(tmp_path, "pyproject.toml", _toml(body))

        assert found == [f"pyproject.toml: could not read: {reason}"]
        assert count == 0


class TestNpmPins:
    """Version specs in `package.json`."""

    @pytest.mark.parametrize("spec", NPM_EXACT)
    def test_exact_version_passes(self, tmp_path, spec):
        assert _run(tmp_path, "package.json", {"dependencies": {"left-pad": spec}}) == ([], 1)

    @pytest.mark.parametrize("spec", NPM_LOOSE)
    def test_loose_version_fails(self, tmp_path, spec):
        found, count = _run(tmp_path, "package.json", {"dependencies": {"left-pad": spec}})

        assert found == [f"package.json: dependencies: left-pad: {json.dumps(spec)}"]
        assert count == 1

    @pytest.mark.parametrize(
        ("content", "offenders", "checked"),
        [
            *(
                pytest.param(
                    {section: {"a": "1.0.0", "b": "^2.0.0"}},
                    [f'{section}: b: "^2.0.0"'],
                    2,
                    id=section,
                )
                for section in (
                    "dependencies",
                    "devDependencies",
                    "optionalDependencies",
                    "peerDependencies",
                )
            ),
            pytest.param(
                {"name": "x", "version": "^1.0.0", "engines": {"node": ">=20"}}, [], 0, id="ignored"
            ),
            pytest.param(
                {"overrides": {"a": "1.0.0", "b": "^2.0.0"}},
                ['overrides: b: "^2.0.0"'],
                2,
                id="flat-override",
            ),
            pytest.param(
                {"overrides": {"a": {"b": {"c": "~1.0.0"}, "d": "2.0.0"}}},
                ['overrides: a > b > c: "~1.0.0"'],
                2,
                id="nested-override",
            ),
            pytest.param(
                {"overrides": {"a": {".": "^1.0.0", "b": "2.0.0"}}},
                ['overrides: a > .: "^1.0.0"'],
                2,
                id="dot-key-override",
            ),
            pytest.param(
                {"dependencies": {"a": 1, "b": None}},
                ["dependencies: a: 1", "dependencies: b: null"],
                2,
                id="non-string",
            ),
        ],
    )
    def test_structure(self, tmp_path, content, offenders, checked):
        found, count = _run(tmp_path, "package.json", content)

        assert found == [f"package.json: {line}" for line in offenders]
        assert count == checked

    @pytest.mark.parametrize(
        ("name", "text"), [("package.json", "{not json"), ("pyproject.toml", "[project\n")]
    )
    def test_unparsable_file_fails(self, tmp_path, name, text):
        found, count = _run(tmp_path, name, text)

        assert len(found) == 1 and found[0].startswith(f"{name}: could not read:")
        assert count == 0

    def test_non_object_section_fails(self, tmp_path):
        found, _ = _run(tmp_path, "package.json", {"dependencies": ["a"]})

        assert len(found) == 1 and found[0].startswith("package.json: could not read:")


class TestRun:
    """The command line behaviour."""

    def test_clean_run_prints_the_count_per_file(self, tmp_path, capsys):
        py = tmp_path / "pyproject.toml"
        py.write_text(_toml("dependencies = ['a==1.0.0', 'b==2.0.0']\n"), encoding="utf-8")
        npm = tmp_path / "package.json"
        npm.write_text('{"dependencies": {"c": "3.0.0"}}', encoding="utf-8")

        assert check.main([str(py), str(npm)]) == 0
        assert (
            capsys.readouterr().out
            == f"OK: all dependencies are pinned exactly ({py} 2, {npm} 1)\n"
        )

    def test_offenders_fail_with_one_line_each(self, tmp_path, capsys):
        npm = tmp_path / "package.json"
        npm.write_text('{"dependencies": {"a": "^1.0.0", "b": "latest"}}', encoding="utf-8")

        assert check.main([str(npm)]) == 1
        assert capsys.readouterr().out.splitlines() == [
            f'{npm}: dependencies: a: "^1.0.0"',
            f'{npm}: dependencies: b: "latest"',
        ]

    def test_missing_file_is_an_error_not_a_skip(self, tmp_path, capsys):
        assert check.main([str(tmp_path / "package.json")]) == 1
        assert "file not found" in capsys.readouterr().out

    def test_default_files_pass_and_are_all_named(self, capsys):
        status = check.main([])

        out = capsys.readouterr().out
        assert status == 0, out
        assert out.startswith("OK:")
        for name in check.DEFAULT_FILES:
            assert f"{name} " in out
