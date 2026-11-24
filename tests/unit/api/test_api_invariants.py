"""Structural guards for four rules of the API that nothing else enforces.

Each rule is a project convention that breaks without a sound: a list route
without a page cap works until a table grows, a record without an ``event`` is invisible
to the drain's index, a refusal raised as ``HTTPException`` reaches FastAPI's own handler,
which logs nothing, and a setting missing from the example env files is invisible to
whoever deploys. A reviewer cannot be relied on to notice an absence, so these tests do.

The raise rule covers ``api/routes/`` and the log rule covers literal ``logger.<level>(...)``
calls. A setting's allowlist entry carries the reason; a stale entry fails too.
"""

import ast
import re
from collections.abc import Iterator
from pathlib import Path
from typing import get_origin

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from api.config import Settings
from api.pagination import PaginationParams
from tests.unit.api.test_route_authorization import _api_routes, _route_key

ROOT = Path(__file__).resolve().parents[3]
API_ROOT = ROOT / "api"
LOG_METHODS = frozenset({"debug", "info", "warning", "error", "exception", "critical", "log"})
MIN_LOG_CALLS = 100
MIN_HTTP_RAISES = 10
MIN_SETTINGS = 50

# Settings with no example line, with why none belongs there: an example line invites
# setting the variable, which is wrong or moot for each of these.
UNDOCUMENTED_SETTINGS: dict[str, str] = {
    "ENVIRONMENT": "Derived from APP_ENV in Settings.__init__, which is the only selector.",
    "TESTING": "Set by the test runner (tests/unit/api/conftest.py), never by a deployer.",
    "RAILWAY_ENVIRONMENT_NAME": "Injected by Railway on every deployed service.",
    "API_VERSION": "Read from the installed package metadata, not configuration.",
    **dict.fromkeys(
        (
            "LANGSMITH_TRACING_V2",
            "LANGCHAIN_TRACING_V2",
            "LANGSMITH_TRACING",
            "LANGCHAIN_TRACING",
            "LANGSMITH_RUNS_ENDPOINTS",
            "LANGCHAIN_RUNS_ENDPOINTS",
        ),
        "The LangSmith library's own switch, read only so a deployed service can refuse it.",
    ),
}


def _relative(path: Path) -> str:
    """Render a path relative to the repository root, with forward slashes.

    :param path: A file under the repository.
    :return: The stable id used in messages and allowlist keys.
    """
    return path.relative_to(ROOT).as_posix()


def _logger_calls(tree: ast.AST) -> Iterator[ast.Call]:
    """Yield every ``logger.<level>(...)`` call in a syntax tree.

    :param tree: Parsed module, or any node inside one.
    :return: Iterator over the matching calls.
    """
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in LOG_METHODS
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "logger"
        ):
            yield node


def _has_event(call: ast.Call) -> bool:
    """Report whether a log call passes ``extra={...}`` holding the constant key ``"event"``.

    :param call: A logger call.
    :return: True when the ``extra`` dict literal has an ``"event"`` key.
    """
    return any(
        kw.arg == "extra"
        and isinstance(kw.value, ast.Dict)
        and any(isinstance(k, ast.Constant) and k.value == "event" for k in kw.value.keys)
        for kw in call.keywords
    )


def _has_pagination(dependant: Dependant) -> bool:
    """Report whether a route's dependency tree contains ``PaginationParams``.

    :param dependant: The route's resolved dependency tree.
    :return: True when ``PaginationParams`` appears anywhere in the tree.
    """
    return dependant.call is PaginationParams or any(
        _has_pagination(sub) for sub in dependant.dependencies
    )


def _list_routes() -> list[APIRoute]:
    """Collect the GET routes that answer with a list.

    :return: Routes whose response model (taken from the return annotation) is ``list[...]``.
    """
    gets = (r for r in _api_routes() if "GET" in (r.methods or ()))
    return [r for r in gets if get_origin(r.response_model) is list]


def _http_raises(
    node: ast.AST, func: ast.FunctionDef | ast.AsyncFunctionDef | None = None
) -> Iterator[tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.Raise, list[ast.stmt]]]:
    """Yield each ``raise HTTPException(...)`` with its function and the statements before it.

    Known limits: a log in an earlier branch of the same block counts as logged, and
    ``raise exc`` of a pre-built exception is not seen.

    :param node: Node to walk.
    :param func: The function enclosing ``node``, if any.
    :return: Iterator of ``(innermost function, raise, earlier statements of the same block)``.
    """
    for _, value in ast.iter_fields(node):
        if not isinstance(value, list):
            continue
        for i, child in enumerate(value):
            if not isinstance(child, ast.AST):
                continue
            if isinstance(child, ast.Raise) and func is not None:
                exc = child.exc
                if isinstance(exc, ast.Call) and (
                    getattr(exc.func, "id", None) == "HTTPException"
                    or getattr(exc.func, "attr", None) == "HTTPException"
                ):
                    yield func, child, value[:i]
            inner = child if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) else func
            yield from _http_raises(child, inner)


def _unlogged_raises() -> tuple[int, dict[str, list[int]]]:
    """Find route raises of ``HTTPException`` with no log call before them in their block.

    A raise counts as logged when an earlier statement of the same block (the branch or
    ``except`` body holding the raise) contains a ``logger.<level>(...)`` call or a call
    to a module-level function of the same module that contains one (``users.py`` logs
    through such helpers). A log in another branch does not cover the raise.

    :return: The number of raises seen, and ``<file>:<function>`` mapped to the line numbers of
        its unlogged raises.
    """
    total = 0
    found: dict[str, list[int]] = {}
    for path in sorted((API_ROOT / "routes").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        helpers = {
            fn.name
            for fn in tree.body
            if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef) and any(_logger_calls(fn))
        }
        for func, raised, before in _http_raises(tree):
            total += 1
            logged = any(
                any(_logger_calls(stmt))
                or any(
                    isinstance(n, ast.Call) and getattr(n.func, "id", None) in helpers
                    for n in ast.walk(stmt)
                )
                for stmt in before
            )
            if not logged:
                found.setdefault(f"{_relative(path)}:{func.name}", []).append(raised.lineno)
    return total, found


def _settings_env_names() -> set[str]:
    """Collect the environment variable of every ``Settings`` field.

    A field is read from its upper-cased name unless it declares a string ``validation_alias``.

    :return: The variable names.
    """
    return {
        (f.validation_alias if isinstance(f.validation_alias, str) else name).upper()
        for name, f in Settings.model_fields.items()
    }


def _documented_env_names() -> set[str]:
    """Collect the names with a ``NAME=`` line, commented out or not, in the example env files.

    :return: Variable names found in ``env/.env*.example`` and ``docker/.env.example``.
    """
    files = [*(ROOT / "env").glob(".env*.example"), ROOT / "docker" / ".env.example"]
    text = "\n".join(f.read_text(encoding="utf-8") for f in files)
    return set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]*)=", text, re.MULTILINE))


class TestListRoutesPaginate:
    """A list endpoint cannot return an unbounded result set."""

    def test_there_are_list_routes_to_check(self):
        """
        GIVEN the application factory
        WHEN GET routes answering with a list are collected
        THEN some are found, so the guard below is not vacuously true
        """
        assert _list_routes(), "no list GET routes found, so the guard below would pass vacuously"

    def test_every_list_route_takes_pagination_params(self):
        """
        GIVEN every GET route whose response is a list
        WHEN its dependency tree is inspected
        THEN PaginationParams is part of it

        Take ``pagination: Annotated[PaginationParams, Depends()]``: its cap is what stops
        one request pulling every row as projects and opinions grow.
        """
        unpaginated = [_route_key(r) for r in _list_routes() if not _has_pagination(r.dependant)]

        assert not unpaginated, f"list routes without PaginationParams: {unpaginated}"


class TestEveryLogCallCarriesAnEvent:
    """A record without an ``event`` cannot be indexed or counted in the drain."""

    def test_every_logger_call_passes_an_event(self):
        """
        GIVEN every logger call under api/
        WHEN its ``extra`` argument is read from the syntax tree
        THEN it is a dict literal with an ``"event"`` key

        A plausible call count is asserted too, or a broken walker would pass.
        """
        total = 0
        missing: list[str] = []
        for path in sorted(API_ROOT.rglob("*.py")):
            for call in _logger_calls(ast.parse(path.read_text(encoding="utf-8"))):
                total += 1
                if not _has_event(call):
                    missing.append(f"{_relative(path)}:{call.lineno}")

        assert total > MIN_LOG_CALLS, f"only {total} logger calls found, the walker is broken"
        assert not missing, f"logger calls without extra={{'event': ...}}: {missing}"


class TestRoutesThatRaiseHttpExceptionLog:
    """A refusal raised as HTTPException bypasses the domain handler, so it logs itself."""

    def test_every_http_exception_raise_is_preceded_by_a_log(self):
        """
        GIVEN every ``raise HTTPException`` in api/routes
        WHEN the statements before it in the same block are searched
        THEN they hold a logger call or a call to a same-module helper that logs

        FastAPI's own handler logs nothing, so without this a refusal leaves no trace.
        Raise a ``BeCoMeAPIError`` subclass instead, or log before raising.
        """
        total, unlogged = _unlogged_raises()

        assert total >= MIN_HTTP_RAISES, f"only {total} HTTPException raises found, walker broken"
        assert not unlogged, f"HTTPException raised with no log before it: {unlogged}"


class TestEverySettingIsDocumented:
    """A setting a deployer cannot find in the example env files is a setting nobody sets."""

    def test_every_setting_has_an_example_line_or_a_reason(self):
        """
        GIVEN every field of Settings
        WHEN its variable is looked up in the example env files
        THEN it has a ``NAME=`` line there or an entry in UNDOCUMENTED_SETTINGS
        """
        settings, documented = _settings_env_names(), _documented_env_names()
        missing = sorted(settings - documented - UNDOCUMENTED_SETTINGS.keys())

        assert len(settings) > MIN_SETTINGS, f"only {len(settings)} Settings fields found"
        assert len(documented) > MIN_SETTINGS, f"only {len(documented)} names in the examples"
        assert not missing, f"settings absent from the example env files: {missing}"

    def test_the_exemption_list_has_no_stale_entries(self):
        """
        GIVEN the exemptions declared above
        WHEN they are matched against Settings
        THEN each one is still a Settings field
        """
        stale = sorted(UNDOCUMENTED_SETTINGS.keys() - _settings_env_names())

        assert not stale, f"exemptions naming settings that no longer exist: {stale}"
