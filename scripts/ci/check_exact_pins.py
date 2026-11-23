#!/usr/bin/env python3
"""Fail when a dependency is not pinned to one exact version.

Every dependency of ``pyproject.toml``, ``frontend/package.json`` and
``.railway/package.json`` is pinned: ``==<version>`` for Python and a bare ``MAJOR.MINOR.PATCH``
for npm. Ranges, carets, tildes, tags, URLs and aliases are refused, so a lock-file refresh
cannot widen what the project installs. A Dependabot bump keeps the pin exact and passes.

Checked in ``pyproject.toml``: ``[project].dependencies``, every list of
``[project.optional-dependencies]``, every list of ``[dependency-groups]`` and the
``dev-dependencies``, ``override-dependencies`` and ``constraint-dependencies`` lists of
``[tool.uv]``. Only a ``{include-group = ...}`` table inside ``[dependency-groups]`` is skipped,
because it names no package; any other table or non-string entry is an offender. Every key of
``[tool.uv.sources]`` is an offender whatever its value, because a source can point an exact
pin at another origin.
``[build-system].requires`` is not checked: it names the build backend, not a project
dependency, and ``requires-python`` is an interpreter constraint, not a package.

Checked in ``package.json``: ``dependencies``, ``devDependencies``, ``optionalDependencies``,
``peerDependencies`` and every string leaf of ``overrides``, nested objects included.

Usage::

    python scripts/ci/check_exact_pins.py [FILE ...]

A ``.toml`` file is read as ``pyproject.toml`` and a ``.json`` file as ``package.json``.
Exit status: 0 when every pin is exact, 1 on any offender or unreadable file.
"""

import json
import re
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FILES = ("pyproject.toml", "frontend/package.json", ".railway/package.json")

# name, optional extras, `==`, a version with no wildcard, optional environment marker.
PYTHON_PIN = re.compile(
    r"""^[A-Za-z0-9][A-Za-z0-9._-]*      # project name
    (?:\s*\[[A-Za-z0-9._,\s-]*\])?       # optional extras
    \s*==\s*[0-9][A-Za-z0-9.!+_-]*       # exact version, no `*`, no second specifier
    (?:\s*;\s*\S.*)?$                    # optional marker
    """,
    re.VERBOSE,
)

# MAJOR.MINOR.PATCH with optional -prerelease and +build, as in semver 2.0.
NPM_PIN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$"
)

UV_DEPENDENCY_LISTS = ("dev-dependencies", "override-dependencies", "constraint-dependencies")

UV_SOURCES = "tool.uv.sources"

NPM_DEPENDENCY_SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)

# One checked entry: section, name, the spec as written.
Entry = tuple[str, str, Any]


def _python_name(spec: str) -> str:
    """Return the package name at the front of a requirement, for the report.

    :param spec: The requirement string
    :return: The text up to the first specifier, extras or marker character
    """
    return re.split(r"[\s\[<>=!~;@]", spec, maxsplit=1)[0] or spec


def pyproject_entries(data: dict[str, Any]) -> Iterator[Entry]:
    """Yield every requirement string of a parsed ``pyproject.toml``.

    :param data: The parsed TOML document
    :return: ``(section, name, spec)`` for each requirement entry
    :raises TypeError: When a dependency list is not a list or ``tool.uv.sources`` is not a table
    """
    project = data.get("project", {})
    uv = data.get("tool", {}).get("uv", {})
    groups = [
        ("project.dependencies", project.get("dependencies", []), False),
        *(
            (f"project.optional-dependencies.{extra}", specs, False)
            for extra, specs in project.get("optional-dependencies", {}).items()
        ),
        *(
            (f"dependency-groups.{group}", specs, True)
            for group, specs in data.get("dependency-groups", {}).items()
        ),
        *((f"tool.uv.{key}", uv[key], False) for key in UV_DEPENDENCY_LISTS if key in uv),
    ]
    for section, specs, allows_include in groups:
        if not isinstance(specs, list):
            raise TypeError(f"{section} is not a list")
        for spec in specs:
            # {include-group = "..."} names no package, and only a dependency group has it
            if allows_include and isinstance(spec, dict) and spec.keys() == {"include-group"}:
                continue
            name = _python_name(spec) if isinstance(spec, str) else str(spec)
            yield section, name, spec
    sources = uv.get("sources", {})
    if not isinstance(sources, dict):
        raise TypeError("tool.uv.sources is not a table")
    for name, source in sources.items():
        yield UV_SOURCES, name, source


def _override_entries(value: Any, trail: tuple[str, ...]) -> Iterator[Entry]:
    """Yield the string leaves of an ``overrides`` object, recursing into nested objects.

    :param value: The ``overrides`` value, or one nested level of it
    :param trail: The keys leading to ``value``
    :return: ``(section, name, spec)`` for each leaf
    """
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from _override_entries(nested, (*trail, key))
    else:
        yield "overrides", " > ".join(trail), value


def package_json_entries(data: dict[str, Any]) -> Iterator[Entry]:
    """Yield every dependency spec of a parsed ``package.json``.

    :param data: The parsed JSON document
    :return: ``(section, name, spec)`` for each dependency and override leaf
    """
    for section in NPM_DEPENDENCY_SECTIONS:
        for name, spec in data.get(section, {}).items():
            yield section, name, spec
    if "overrides" in data:
        yield from _override_entries(data["overrides"], ())


def is_exact_python(spec: Any) -> bool:
    """Tell whether a requirement is ``name[extras]==version`` with an optional marker.

    :param spec: The requirement as written
    :return: True when it pins one exact version
    """
    return isinstance(spec, str) and PYTHON_PIN.fullmatch(spec) is not None


def is_exact_npm(spec: Any) -> bool:
    """Tell whether an npm spec is a bare exact semver version.

    :param spec: The version spec as written
    :return: True when it is ``MAJOR.MINOR.PATCH`` with an optional prerelease and build part
    """
    return isinstance(spec, str) and NPM_PIN.fullmatch(spec) is not None


def check_file(path: Path, label: str) -> tuple[list[str], int]:
    """Check one manifest.

    :param path: The ``.toml`` or ``.json`` file to read
    :param label: The name to print for the file
    :return: The offender messages and the number of specs checked
    """
    try:
        if path.suffix == ".toml":
            entries = list(pyproject_entries(tomllib.loads(path.read_text(encoding="utf-8"))))
            is_exact = is_exact_python
        else:
            entries = list(package_json_entries(json.loads(path.read_text(encoding="utf-8"))))
            is_exact = is_exact_npm
    except FileNotFoundError:
        return [f"{label}: file not found"], 0
    except (OSError, UnicodeDecodeError, ValueError, AttributeError, TypeError) as exc:
        return [f"{label}: could not read: {exc}"], 0

    offenders = [
        f"{label}: {section}: {name}: {json.dumps(spec, default=str)}"
        for section, name, spec in entries
        if section == UV_SOURCES or not is_exact(spec)
    ]
    return offenders, len(entries)


def main(argv: list[str]) -> int:
    """Run the check over the given manifests, or over the default three.

    :param argv: The file paths; empty means the three default manifests
    :return: The exit status, 1 when any offender or unreadable file was found
    """
    paths = [Path(arg) for arg in argv] or [ROOT / name for name in DEFAULT_FILES]
    messages: list[str] = []
    counts: list[str] = []
    for path in paths:
        label = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
        offenders, checked = check_file(path, label)
        messages.extend(offenders)
        counts.append(f"{label} {checked}")
    if messages:
        print("\n".join(messages))
        return 1
    print(f"OK: all dependencies are pinned exactly ({', '.join(counts)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
