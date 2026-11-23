"""Unit tests for the exact-pin check of Python and npm dependencies.

The project pins every dependency to one exact version. Each form that widens what gets
installed must fail, and the shapes a Dependabot bump produces must pass.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]


def _load():
    """Import the script by path, since `scripts/` is not a package.

    :return: The imported `check_exact_pins` module
    """
    spec = importlib.util.spec_from_file_location(
        "check_exact_pins", ROOT / "scripts" / "ci" / "check_exact_pins.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_exact_pins"] = module
    spec.loader.exec_module(module)
    return module


check = _load()


def _pyproject(tmp_path: Path, body: str) -> Path:
    """Write a ``pyproject.toml`` under ``tmp_path``.

    :param tmp_path: The test directory
    :param body: The TOML text
    :return: The path written
    """
    path = tmp_path / "pyproject.toml"
    path.write_text(body, encoding="utf-8")
    return path


def _package_json(tmp_path: Path, content: dict) -> Path:
    """Write a ``package.json`` under ``tmp_path``.

    :param tmp_path: The test directory
    :param content: The manifest content
    :return: The path written
    """
    path = tmp_path / "package.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def _python_offenders(tmp_path: Path, *specs: str) -> list[str]:
    """Check a ``[project].dependencies`` list made of ``specs``.

    :param tmp_path: The test directory
    :param specs: The requirement strings
    :return: The offender messages
    """
    body = "[project]\nname = 'x'\ndependencies = " + json.dumps(list(specs)) + "\n"
    offenders, _ = check.check_file(_pyproject(tmp_path, body), "pyproject.toml")
    return offenders


class TestPythonPins:
    """Requirement strings in `pyproject.toml`."""

    @pytest.mark.parametrize(
        "spec",
        [
            "fastapi==0.115.0",
            "fastapi[standard]==0.115.0",
            "uvicorn[standard, extra]==0.30.1",
            "pywin32==306 ; sys_platform == 'win32'",
            "pywin32==306; sys_platform == 'win32'",
            "uvloop[x]==0.21.0; python_version >= '3.12' and sys_platform != 'win32'",
            "Pillow==11.0.0",
            "typing_extensions==4.12.2",
            "zope.interface==7.1.1",
            "pkg==1.0.0rc1",
            "pkg==2024.1.1.post2",
            "pkg==1.0.0+local.1",
            "pkg==1!2.0",
        ],
    )
    def test_exact_pin_passes(self, tmp_path, spec):
        assert _python_offenders(tmp_path, spec) == []

    @pytest.mark.parametrize(
        "spec",
        [
            "fastapi>=0.115.0",
            "fastapi~=0.115.0",
            "fastapi!=0.115.0",
            "fastapi<1",
            "fastapi>1",
            "fastapi<=1",
            "fastapi===0.115.0",
            "fastapi==0.115.*",
            "fastapi==1.*",
            "fastapi",
            "fastapi[standard]",
            "fastapi @ https://example.com/fastapi-0.115.0.tar.gz",
            "fastapi==1,<2",
            "fastapi>=1,<2",
            "fastapi==",
            "fastapi==latest",
            "fastapi>=1 ; python_version >= '3.12'",
        ],
    )
    def test_loose_requirement_fails(self, tmp_path, spec):
        offenders = _python_offenders(tmp_path, spec)

        assert offenders == [f"pyproject.toml: project.dependencies: fastapi: {json.dumps(spec)}"]

    def test_trailing_newline_fails(self, tmp_path):
        offenders = _python_offenders(tmp_path, "fastapi==0.115.0\n")

        assert offenders == ['pyproject.toml: project.dependencies: fastapi: "fastapi==0.115.0\\n"']

    def test_dict_in_project_dependencies_fails_even_with_include_group(self, tmp_path):
        body = "[project]\nname = 'x'\ndependencies = [{include-group = 'lint'}, {a = 'b'}]\n"

        offenders, checked = check.check_file(_pyproject(tmp_path, body), "pyproject.toml")

        assert len(offenders) == 2
        assert checked == 2

    def test_dict_other_than_include_group_in_a_group_fails(self, tmp_path):
        body = (
            "[project]\nname = 'x'\n"
            "[dependency-groups]\n"
            "dev = [{include-group = 'lint'}, {include-group = 'a', extra = 1}, {a = 'b'}]\n"
        )

        offenders, checked = check.check_file(_pyproject(tmp_path, body), "pyproject.toml")

        assert [line.split(": ", 2)[1] for line in offenders] == ["dependency-groups.dev"] * 2
        assert checked == 2  # the plain include-group names no package and is not counted

    def test_non_string_entry_reports_without_raising(self, tmp_path):
        body = "[project]\nname = 'x'\ndependencies = [1979-05-27, 3]\n"

        offenders, _ = check.check_file(_pyproject(tmp_path, body), "pyproject.toml")

        assert offenders == [
            'pyproject.toml: project.dependencies: 1979-05-27: "1979-05-27"',
            "pyproject.toml: project.dependencies: 3: 3",
        ]

    def test_dependency_list_that_is_not_a_list_reports_instead_of_raising(self, tmp_path):
        body = "[project]\nname = 'x'\ndependencies = 1\n"

        offenders, checked = check.check_file(_pyproject(tmp_path, body), "pyproject.toml")

        assert offenders == ["pyproject.toml: could not read: project.dependencies is not a list"]
        assert checked == 0

    @pytest.mark.parametrize(
        "key", ["dev-dependencies", "override-dependencies", "constraint-dependencies"]
    )
    def test_uv_lists_are_checked(self, tmp_path, key):
        body = f"[project]\nname = 'x'\n[tool.uv]\n{key} = ['a==1.0.0', 'b>=2.0.0']\n"

        offenders, checked = check.check_file(_pyproject(tmp_path, body), "pyproject.toml")

        assert offenders == [f'pyproject.toml: tool.uv.{key}: b: "b>=2.0.0"']
        assert checked == 2

    def test_only_the_loose_entry_is_reported(self, tmp_path):
        offenders = _python_offenders(tmp_path, "a==1.0.0", "b>=2.0.0", "c==3.0.0")

        assert offenders == ['pyproject.toml: project.dependencies: b: "b>=2.0.0"']

    def test_optional_dependencies_are_checked(self, tmp_path):
        body = (
            "[project]\nname = 'x'\ndependencies = ['a==1.0.0']\n"
            "[project.optional-dependencies]\n"
            "dev = ['pytest==8.0.0', 'ruff>=0.5']\n"
            "docs = ['mkdocs==1.6.0']\n"
        )

        offenders, checked = check.check_file(_pyproject(tmp_path, body), "pyproject.toml")

        assert offenders == ['pyproject.toml: project.optional-dependencies.dev: ruff: "ruff>=0.5"']
        assert checked == 4

    def test_dependency_groups_are_checked_and_includes_skipped(self, tmp_path):
        body = (
            "[project]\nname = 'x'\n"
            "[dependency-groups]\n"
            "lint = ['ruff==0.5.0']\n"
            "dev = [{include-group = 'lint'}, 'pytest~=8.0']\n"
        )

        offenders, checked = check.check_file(_pyproject(tmp_path, body), "pyproject.toml")

        assert offenders == ['pyproject.toml: dependency-groups.dev: pytest: "pytest~=8.0"']
        assert checked == 2

    def test_build_system_and_requires_python_are_not_checked(self, tmp_path):
        body = (
            "[build-system]\nrequires = ['hatchling>=1.0']\nbuild-backend = 'hatchling.build'\n"
            "[project]\nname = 'x'\nrequires-python = '>=3.13'\ndependencies = ['a==1.0.0']\n"
        )

        offenders, checked = check.check_file(_pyproject(tmp_path, body), "pyproject.toml")

        assert offenders == []
        assert checked == 1

    def test_dependabot_bump_passes(self, tmp_path):
        before = _python_offenders(tmp_path, "httpx==1.2.3")
        after = _python_offenders(tmp_path, "httpx==1.2.4")

        assert before == after == []


class TestNpmPins:
    """Version specs in `package.json`."""

    @pytest.mark.parametrize(
        "spec",
        [
            "1.2.3",
            "0.0.0",
            "10.20.30",
            "5.1.0",
            "1.2.3-rc.1",
            "1.2.3-beta",
            "2.0.0-alpha.1+build.5",
            "1.2.3+20260101",
        ],
    )
    def test_exact_version_passes(self, tmp_path, spec):
        path = _package_json(tmp_path, {"dependencies": {"left-pad": spec}})

        assert check.check_file(path, "package.json") == ([], 1)

    @pytest.mark.parametrize(
        "spec",
        [
            "^1.2.3",
            "~1.2.3",
            "=1.2.3",
            "v1.2.3",
            ">=1.2.3",
            ">1.2.3",
            "<2.0.0",
            "1.x",
            "1.2.x",
            "1.2",
            "1",
            "*",
            "",
            "latest",
            "next",
            "beta",
            "1.2.3 - 2.0.0",
            "1.2.3 || 2.0.0",
            "^1.2.3 || ^2.0.0",
            "https://example.com/pkg.tgz",
            "git+https://github.com/org/pkg.git",
            "git://github.com/org/pkg.git#v1.2.3",
            "github:org/pkg",
            "org/pkg",
            "file:../pkg",
            "link:../pkg",
            "workspace:*",
            "npm:other@1.2.3",
            "$left-pad",
            "01.2.3",
        ],
    )
    def test_loose_version_fails(self, tmp_path, spec):
        path = _package_json(tmp_path, {"dependencies": {"left-pad": spec}})

        offenders, checked = check.check_file(path, "package.json")

        assert offenders == [f"package.json: dependencies: left-pad: {json.dumps(spec)}"]
        assert checked == 1

    @pytest.mark.parametrize(
        "section",
        ["dependencies", "devDependencies", "optionalDependencies", "peerDependencies"],
    )
    def test_every_dependency_section_is_checked(self, tmp_path, section):
        path = _package_json(tmp_path, {section: {"a": "1.0.0", "b": "^2.0.0"}})

        offenders, checked = check.check_file(path, "package.json")

        assert offenders == [f'package.json: {section}: b: "^2.0.0"']
        assert checked == 2

    def test_non_dependency_fields_are_ignored(self, tmp_path):
        path = _package_json(
            tmp_path,
            {"name": "x", "version": "^1.0.0", "engines": {"node": ">=20"}, "scripts": {"a": "b"}},
        )

        assert check.check_file(path, "package.json") == ([], 0)

    def test_flat_override_is_checked(self, tmp_path):
        path = _package_json(tmp_path, {"overrides": {"a": "1.0.0", "b": "^2.0.0"}})

        offenders, checked = check.check_file(path, "package.json")

        assert offenders == ['package.json: overrides: b: "^2.0.0"']
        assert checked == 2

    def test_nested_override_is_checked(self, tmp_path):
        path = _package_json(tmp_path, {"overrides": {"a": {"b": {"c": "~1.0.0"}, "d": "2.0.0"}}})

        offenders, checked = check.check_file(path, "package.json")

        assert offenders == ['package.json: overrides: a > b > c: "~1.0.0"']
        assert checked == 2

    def test_dot_key_of_an_override_object_is_a_version(self, tmp_path):
        path = _package_json(tmp_path, {"overrides": {"a": {".": "^1.0.0", "b": "2.0.0"}}})

        offenders, _ = check.check_file(path, "package.json")

        assert offenders == ['package.json: overrides: a > .: "^1.0.0"']

    def test_trailing_newline_fails(self, tmp_path):
        path = _package_json(tmp_path, {"dependencies": {"a": "1.2.3\n"}})

        offenders, _ = check.check_file(path, "package.json")

        assert offenders == ['package.json: dependencies: a: "1.2.3\\n"']

    def test_non_string_spec_fails(self, tmp_path):
        path = _package_json(tmp_path, {"dependencies": {"a": 1, "b": None}})

        offenders, _ = check.check_file(path, "package.json")

        assert offenders == [
            "package.json: dependencies: a: 1",
            "package.json: dependencies: b: null",
        ]

    def test_dependabot_bump_passes(self, tmp_path):
        before = _package_json(tmp_path, {"devDependencies": {"vite": "5.1.0"}})
        assert check.check_file(before, "package.json") == ([], 1)

        after = _package_json(tmp_path, {"devDependencies": {"vite": "5.2.0"}})
        assert check.check_file(after, "package.json") == ([], 1)


class TestRun:
    """The command line behaviour."""

    def test_clean_run_prints_the_count_per_file(self, tmp_path, capsys):
        py = _pyproject(
            tmp_path, "[project]\nname = 'x'\ndependencies = ['a==1.0.0', 'b==2.0.0']\n"
        )
        npm = _package_json(tmp_path, {"dependencies": {"c": "3.0.0"}})

        status = check.main([str(py), str(npm)])

        assert status == 0
        assert capsys.readouterr().out == (
            f"OK: all dependencies are pinned exactly ({py} 2, {npm} 1)\n"
        )

    def test_offender_fails_with_one_line_per_offender(self, tmp_path, capsys):
        npm = _package_json(tmp_path, {"dependencies": {"a": "^1.0.0", "b": "latest"}})

        status = check.main([str(npm)])

        assert status == 1
        assert capsys.readouterr().out.splitlines() == [
            f'{npm}: dependencies: a: "^1.0.0"',
            f'{npm}: dependencies: b: "latest"',
        ]

    def test_missing_file_is_an_error_not_a_skip(self, tmp_path, capsys):
        status = check.main([str(tmp_path / "package.json")])

        assert status == 1
        assert "file not found" in capsys.readouterr().out

    @pytest.mark.parametrize(
        ("name", "text"),
        [("package.json", "{not json"), ("pyproject.toml", "[project\n")],
    )
    def test_unparsable_file_fails(self, tmp_path, name, text):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")

        offenders, checked = check.check_file(path, name)

        assert len(offenders) == 1
        assert offenders[0].startswith(f"{name}: could not read:")
        assert checked == 0

    def test_non_object_section_fails(self, tmp_path):
        path = _package_json(tmp_path, {"dependencies": ["a"]})

        offenders, _ = check.check_file(path, "package.json")

        assert len(offenders) == 1
        assert offenders[0].startswith("package.json: could not read:")


class TestRepository:
    """The manifests this repository ships."""

    def test_default_files_pass(self, capsys):
        # GIVEN the three manifests named by default
        status = check.main([])

        # THEN every dependency in them is pinned exactly, and the report names all three
        out = capsys.readouterr().out
        assert status == 0, out
        assert out.startswith("OK:")
        for name in check.DEFAULT_FILES:
            assert f"{name} " in out
