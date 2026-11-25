"""Judge the DAST run: read what the three scans wrote and decide what blocks.

Stdlib only, so the step needs no environment beyond ``python3``. Run it from the repository
root after the scans::

    python3 .github/dast/gate.py dast-out

It reads, inside the output directory, a report and the exit code of each scan
(``schemathesis/json-*.json`` with ``schemathesis.rc``, ``zap/report.json`` with ``zap-api.rc``,
``zap-web/report.json`` with ``zap-web.rc``) and ``zap/openapi.pruned.json``, the paths of the
API, which turn a scanned address into its path template.

What blocks:

- a Schemathesis failure of a check in ``CHECK_BY_CODE``: a server error (ST101, ST102), ignored
  authentication (ST401) or broken object-level authorization (ST402);
- a ZAP alert of risk Medium or higher, API or web, and one whose risk the report does not state
  readably, after the by-design ``IGNORE`` rules of ``rules-api.conf`` and ``rules-web.conf`` are
  applied here, because ZAP applies them only to its own exit code and still writes the alert
  into the JSON report;
- a scan that did not complete (see ``schemathesis_completed`` and ``zap_completed``), or whose
  report the gate could not read or make sense of.

Every blocking finding is dropped when its fingerprint is listed, one per line, in the
environment variable ``DAST_OPEN_FINGERPRINTS``: a finding already known and tracked
elsewhere. Everything else (other schema conformance failures, operations Schemathesis could
not test, ZAP Low and Informational alerts) is only counted as a warning.

A fingerprint never holds a payload or an id::

    schemathesis:<check>:<METHOD> <path template>, or <no operation> when a failure names none
    zap-api:<alert ref>:<METHOD> <path template of the OpenAPI file, or <unmatched>>
    zap-web:<alert ref>:<METHOD> <path with unknown segments as {x}>

Output. The job log and ``$GITHUB_STEP_SUMMARY`` get totals per tool and, for a scan that did
not complete, one reason out of a fixed list of strings in this file, never text from a report,
because the repository is public. ``<out dir>/gate.json`` gets the detail with fingerprints and
stays private. Whatever the reports hold, the script exits 0 and writes ``blocking=<n>`` to
``$GITHUB_OUTPUT``; a report it cannot judge counts as one blocking item. The last step of the
job fails on a value other than 0, including a missing one.
"""

import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
RISK_INFO, RISK_LOW, BLOCKING_RISK, UNKNOWN_RISK = 0, 1, 2, 4
CHECK_BY_CODE = {
    "ST101": "not_a_server_error",
    "ST102": "not_a_server_error",
    "ST401": "ignored_auth",
    "ST402": "object_level_authorization",
}
# ZAP ignores a rule by plugin id, which drops every alert of that plugin. For a plugin listed
# here the gate drops only the alerts whose name holds the text (in lower case).
BY_DESIGN = {("zap-web", "10055"): "style-src unsafe-inline"}
ID_SEGMENT = re.compile(r"^(?:[0-9a-fA-F-]{32,36}|\d+)$")
# Static routes of the frontend image (pages, nginx.conf routes, assets, frontend/public files).
WEB_ROUTES = frozenset(
    {
        "about", "apple-touch-icon.png", "assets", "case-studies", "case-study", "docs", "faq",
        "favicon-32.png", "favicon.svg", "forgot-password", "healthz", "login", "og-cover.png",
        "onboarding", "privacy", "profile", "projects", "register", "reset-password",
        "robots.txt", "sitemap.xml", "terms", "verify-email",
    }
)  # fmt: skip


def schemathesis_completed(rc: int | None, report: dict[str, Any]) -> str:
    """Say why a Schemathesis run did not finish, or return an empty string when it did.

    Exit codes, from ``schemathesis/cli/constants.py`` of the pinned release: 0 no failures,
    1 failed checks or non-fatal errors (also an uncaught exception), 2 the run could not do
    its job, 130 interrupted. Code 1 does not say whether the run finished, so the report
    decides: it must say ``complete`` and have tested an operation. Of the stop reasons
    (``completed``, ``interrupted``, ``failure_limit``, ``max_time``, ``server_unavailable``;
    ``StopReason`` in ``engine/__init__.py`` of the pinned release) only ``completed`` passes.

    :param rc: Exit code of the process, ``None`` when no code was recorded
    :param report: The parsed JSON report
    :return: A fixed reason, empty when the run completed
    """
    if rc not in (0, 1):
        return "unexpected exit code"
    operations = report.get("operations") or {}
    finished = report.get("complete") is True and report.get("stop_reason") == "completed"
    return "" if finished and operations.get("tested") else "scan did not finish"


def zap_completed(rc: int | None, report: dict[str, Any]) -> str:
    """Say why a ZAP scan did not finish, or return an empty string when it did.

    Exit codes, from ``zap-api-scan.py`` and ``zap-baseline.py`` of the pinned image: 0 passed,
    1 at least one FAIL rule, 2 at least one WARN (never with ``-I``), 3 any other failure.
    The scripts do not tell whether the scan reached its target, so the report must also have
    a non-empty ``site`` list: a target that was never reached leaves it empty.

    :param rc: Exit code of the process, ``None`` when no code was recorded
    :param report: The parsed JSON report
    :return: A fixed reason, empty when the scan completed
    """
    if rc not in (0, 1, 2):
        return "unexpected exit code"
    return "" if report.get("site") else "target not reached"


def read_rc(path: Path) -> int | None:
    """Read an exit code written by the workflow.

    :param path: File holding one integer
    :return: The code, or ``None`` when the file is missing or not an integer
    """
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def read_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    """Parse a JSON object from a file.

    :param path: The file
    :return: The object and an empty string, or ``None`` and a fixed reason: ``report missing``
        when the file does not exist, ``report unreadable`` for anything else that goes wrong
    """
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return None, "report missing"
    except (OSError, ValueError, RecursionError):
        data = None
    return (data, "") if isinstance(data, dict) else (None, "report unreadable")


def ignored_plugins(rules: Path) -> frozenset[str]:
    """List the plugin ids a ZAP rules file marks IGNORE.

    :param rules: A tab-separated ZAP rules file
    :return: The ids of the rules with the action ``IGNORE``
    """
    try:
        lines = rules.read_text().splitlines()
    except OSError:
        return frozenset()
    ids: set[str] = set()
    for line in lines:
        parts = line.split("\t")
        if not line.startswith("#") and len(parts) >= 2 and parts[1].strip() == "IGNORE":
            ids.add(parts[0].strip())
    return frozenset(ids)


def open_fingerprints(raw: str) -> frozenset[str]:
    """Parse the newline-separated list of accepted fingerprints.

    :param raw: The value of ``DAST_OPEN_FINGERPRINTS``, possibly empty
    :return: The fingerprints, without blank lines and ``#`` comments
    """
    lines = (line.strip() for line in raw.splitlines())
    return frozenset(line for line in lines if line and not line.startswith("#"))


def is_variable(segment: str) -> bool:
    """Tell whether a path segment of the API stands for an id.

    :param segment: One segment of a path
    :return: ``True`` for an OpenAPI parameter or a UUID or integer baked into the spec
    """
    return (segment.startswith("{") and segment.endswith("}")) or bool(ID_SEGMENT.match(segment))


def api_template(path: str, spec_paths: list[str]) -> str:
    """Map a scanned path to the path template of the OpenAPI file.

    The file has the fixture ids baked in, so a template matches by segment count and by its
    literal segments; a segment that is a parameter or an id matches anything. The best match
    is the one with the most literal segments agreeing. Ids in the result become ``{id}`` so
    that the fingerprint is the same from one run to the next.

    :param path: The path of the scanned address, without scheme, host and query
    :param spec_paths: The paths of the OpenAPI file
    :return: The normalised template, or ``<unmatched>`` when no path of the file fits
    """
    segments = [part for part in path.split("/") if part]
    best: tuple[int, list[str]] | None = None
    for candidate in spec_paths:
        template = [part for part in candidate.split("/") if part]
        if len(template) != len(segments):
            continue
        score = 0
        for have, want in zip(segments, template, strict=True):
            if is_variable(want):
                continue
            if have != want:
                break
            score += 1
        else:
            if best is None or score > best[0]:
                best = (score, template)
    if best is None:
        return "<unmatched>"
    return "/" + "/".join("{id}" if is_variable(part) else part for part in best[1])


def web_template(path: str) -> str:
    """Replace every segment that is not a known static route with ``{x}``.

    :param path: The path of the scanned address, without scheme, host and query
    :return: The path with its variable segments masked
    """
    segments = [segment for segment in path.split("/") if segment]
    return "/" + "/".join(s if s in WEB_ROUTES else "{x}" for s in segments)


@dataclass
class Finding:
    """One finding of one scan, reduced to what the gate keeps.

    ``risk`` is the ZAP risk code, ``UNKNOWN_RISK`` when the report does not state one readably,
    and ``None`` for a Schemathesis failure, which has no risk scale.
    """

    fingerprint: str
    blocking: bool
    risk: int | None = None


@dataclass
class ToolResult:
    """The gate's view of one scan."""

    name: str
    rc: int | None
    incomplete: str = ""
    findings: dict[str, Finding] = field(default_factory=dict)
    suppressed: set[str] = field(default_factory=set)
    errored: int = 0

    def counts(self) -> dict[str, int]:
        """Count what is left after suppression, by the public categories.

        :return: ``blocking`` and ``warnings`` (which include the operations Schemathesis could
            not test), plus ``low`` and ``info`` for a ZAP scan
        """
        findings = self.findings.values()
        counts = {
            "blocking": sum(1 for f in findings if f.blocking) + bool(self.incomplete),
            "warnings": sum(1 for f in findings if not f.blocking) + self.errored,
        }
        if self.name.startswith("zap"):
            counts["low"] = sum(1 for f in findings if f.risk == RISK_LOW)
            counts["info"] = sum(1 for f in findings if f.risk == RISK_INFO)
        return counts


def as_list(value: Any) -> list[Any]:
    """Read a JSON array a report may leave out: empty for ``None``, ``TypeError`` otherwise."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError("expected a list")
    return value


def judge_schemathesis(out: Path, accepted: frozenset[str]) -> ToolResult:
    """Read the Schemathesis report and sort its failures.

    A run writes exactly one ``json-<timestamp>.json`` (``config/_report.py`` of the pinned
    release 4.34.2). More than one file means more than one run wrote into the directory, so the
    exit code cannot be tied to a report and the run counts as incomplete.

    :param out: The output directory of the run
    :param accepted: Fingerprints that must not block
    :return: The result for the tool
    """
    result = ToolResult("schemathesis", read_rc(out / "schemathesis.rc"))
    reports = sorted((out / "schemathesis").glob("json-*.json"))
    if len(reports) > 1:
        result.incomplete = "more than one report"
        return result
    report, problem = read_json(reports[0]) if reports else (None, "report missing")
    if report is None:
        result.incomplete = problem
        return result
    result.incomplete = schemathesis_completed(result.rc, report)
    operations = report.get("operations") or {}
    result.errored = max(int(operations.get("errored") or 0), len(as_list(report.get("errors"))))
    # A fingerprint that blocks once keeps blocking, whatever else shares it.
    blocks: dict[str, bool] = {}
    for failure in as_list(report.get("failures")):
        code = str(failure.get("code", "")).upper()
        check = CHECK_BY_CODE.get(code, code.lower())
        for operation in as_list(failure.get("operations")) or ["<no operation>"]:
            fingerprint = f"schemathesis:{check}:{operation}"
            blocks[fingerprint] = blocks.get(fingerprint, False) or code in CHECK_BY_CODE
    for fingerprint, blocking in blocks.items():
        if blocking and fingerprint in accepted:
            result.suppressed.add(fingerprint)
        else:
            result.findings[fingerprint] = Finding(fingerprint, blocking)
    return result


def parse_risk(value: Any) -> int:
    """Read the ``riskcode`` of a ZAP alert, failing closed.

    :param value: The raw value, a digit string in a real report; an integer reads the same
    :return: The risk 0 to 3, or ``UNKNOWN_RISK`` for anything else (a boolean, a float), which
        blocks
    """
    readable = (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, str) and value.isascii() and value.isdigit()
    )
    risk = int(value) if readable else UNKNOWN_RISK
    return risk if risk in (RISK_INFO, RISK_LOW, BLOCKING_RISK, 3) else UNKNOWN_RISK


def judge_zap(
    name: str,
    report_dir: Path,
    rc_file: Path,
    rules: Path,
    spec: Path | None,
    accepted: frozenset[str],
) -> ToolResult:
    """Read a ZAP JSON report and sort its alerts.

    Alerts that share a fingerprint are one finding with the highest risk among them: one
    alert reference can come with several risks, and a Low must never hide a Medium.

    :param name: ``zap-api`` or ``zap-web``, the tool name used in fingerprints
    :param report_dir: Directory holding ``report.json``
    :param rc_file: File holding the exit code of the scan
    :param rules: The rules file of this scan, read for its IGNORE lines
    :param spec: The pruned OpenAPI file, for ``zap-api`` only
    :param accepted: Fingerprints that must not block
    :return: The result for the tool
    """
    result = ToolResult(name, read_rc(rc_file))
    report, problem = read_json(report_dir / "report.json")
    if report is None:
        result.incomplete = problem
        return result
    result.incomplete = zap_completed(result.rc, report)
    spec_paths: list[str] = []
    if spec is not None:
        document, _ = read_json(spec)
        paths = document.get("paths") if document else None
        if isinstance(paths, dict) and paths:
            spec_paths = list(paths)
        elif not result.incomplete:
            result.incomplete = "spec missing"
    ignored = ignored_plugins(rules)
    risks: dict[str, int] = {}
    for site in report.get("site") or []:
        for alert in site.get("alerts") or []:
            plugin = str(alert.get("pluginid", ""))
            alert_name = str(alert.get("name") or alert.get("alert") or "")
            needle = BY_DESIGN.get((name, plugin))
            if plugin in ignored and (needle is None or needle in alert_name.lower()):
                continue
            reference = str(alert.get("alertRef") or plugin)
            risk = parse_risk(alert.get("riskcode"))
            # An alert without an instance is still an alert: it keeps its risk.
            for instance in alert.get("instances") or [None]:
                if instance is None:
                    method, template = "-", "<no instance>"
                else:
                    path = urlsplit(str(instance.get("uri", ""))).path
                    method = str(instance.get("method") or "GET").upper()
                    template = (
                        api_template(path, spec_paths) if name == "zap-api" else web_template(path)
                    )
                fingerprint = f"{name}:{reference}:{method} {template}"
                risks[fingerprint] = max(risks.get(fingerprint, risk), risk)
    for fingerprint, risk in risks.items():
        blocking = risk >= BLOCKING_RISK
        if blocking and fingerprint in accepted:
            result.suppressed.add(fingerprint)
        else:
            result.findings[fingerprint] = Finding(fingerprint, blocking, risk)
    return result


def judged(name: str, rc_file: Path, judge: Callable[[], ToolResult]) -> ToolResult:
    """Run one tool's judging, turning any surprise in its report into an incomplete scan.

    :param name: The tool name
    :param rc_file: File holding the exit code of the scan
    :param judge: The call that reads the report and returns the result
    :return: The result, or an incomplete one when the report has a shape the gate cannot read
    """
    try:
        return judge()
    except Exception:  # a report of any shape must still end in a verdict
        return ToolResult(name, read_rc(rc_file), "report has an unexpected shape")


def summary_lines(results: list[ToolResult]) -> list[str]:
    """Write the public summary: totals per tool and the reason of an incomplete scan.

    :param results: The result of each tool
    :return: Markdown lines, safe for the job log and the step summary
    """
    lines = ["## DAST", ""]
    for result in results:
        counts = result.counts()
        parts = [f"blocking {counts['blocking']}", f"warnings {counts['warnings']}"]
        parts += [f"{key} {counts[key]}" for key in ("low", "info") if key in counts]
        line = f"- {result.name}: " + ", ".join(parts)
        if result.incomplete:
            line += f" (scan incomplete: {result.incomplete})"
        lines.append(line)
    return lines


def main(out: Path) -> None:
    """Judge the scans in ``out`` and write the summary, the detail and the job output.

    :param out: The output directory of the run
    """
    accepted = open_fingerprints(os.environ.get("DAST_OPEN_FINGERPRINTS", ""))
    results = [
        judged(
            "schemathesis",
            out / "schemathesis.rc",
            lambda: judge_schemathesis(out, accepted),
        ),
        judged(
            "zap-api",
            out / "zap-api.rc",
            lambda: judge_zap(
                "zap-api",
                out / "zap",
                out / "zap-api.rc",
                HERE / "rules-api.conf",
                out / "zap" / "openapi.pruned.json",
                accepted,
            ),
        ),
        judged(
            "zap-web",
            out / "zap-web.rc",
            lambda: judge_zap(
                "zap-web",
                out / "zap-web",
                out / "zap-web.rc",
                HERE / "rules-web.conf",
                None,
                accepted,
            ),
        ),
    ]
    blocking = sum(result.counts()["blocking"] for result in results)
    lines = summary_lines(results)
    print("\n".join(lines))
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as handle:
            handle.write("\n".join(lines) + "\n")
    detail = {
        "blocking": blocking,
        "tools": {
            result.name: {
                "rc": result.rc,
                "incomplete": result.incomplete,
                "errored": result.errored,
                "counts": result.counts(),
                "blocking": sorted(f.fingerprint for f in result.findings.values() if f.blocking),
                "warnings": sorted(
                    f.fingerprint for f in result.findings.values() if not f.blocking
                ),
                "suppressed": sorted(result.suppressed),
            }
            for result in results
        },
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "gate.json").write_text(json.dumps(detail, indent=1))
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as handle:
            handle.write(f"blocking={blocking}\n")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "dast-out"))
