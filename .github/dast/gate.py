"""Judge the DAST run: read what the three scans wrote and decide what blocks.

Stdlib only, so the step needs no environment beyond ``python3``. Run it from the repository
root after the scans::

    python3 .github/dast/gate.py dast-out

It reads, inside the output directory:

- ``schemathesis/json-*.json`` and ``schemathesis.rc``: the Schemathesis run report and the
  exit code of the process;
- ``zap/report.json`` and ``zap-api.rc``: the ZAP API scan;
- ``zap-web/report.json`` and ``zap-web.rc``: the ZAP baseline scan of the frontend image;
- ``zap/openapi.pruned.json``: the paths of the API, used to turn a scanned address into its
  path template.

What blocks:

- a Schemathesis ``not_a_server_error`` failure (code ST101);
- a ZAP alert of risk Medium or higher, API or web, after the by-design ``IGNORE`` rules of
  ``rules-api.conf`` and ``rules-web.conf`` are applied here, because ZAP applies them only to
  its own exit code and still writes the alert into the JSON report;
- a scan that did not complete (see ``schemathesis_completed`` and ``zap_completed``).

Every blocking finding is dropped when its fingerprint is listed, one per line, in the
environment variable ``DAST_OPEN_FINGERPRINTS``: a finding already known and tracked
elsewhere. Everything else (schema conformance, ZAP Low and Informational alerts) is only
counted as a warning.

A fingerprint never holds a payload or an id::

    schemathesis:<check>:<METHOD> <path template>
    zap-api:<plugin id>:<METHOD> <path template of the OpenAPI file, or <unmatched>>
    zap-web:<plugin id>:<METHOD> <path with unknown segments as {x}>

Output. The job log and ``$GITHUB_STEP_SUMMARY`` get totals per tool and nothing more, because
the repository is public. ``<out dir>/gate.json`` gets the detail with fingerprints and stays
private. The script always exits 0 and writes ``blocking=<n>`` to ``$GITHUB_OUTPUT``; the last
step of the job fails on a value other than 0, including a missing one.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
BLOCKING_RISK = 2
RISK_NAMES = {0: "info", 1: "low", 2: "medium", 3: "high"}
CHECK_BY_CODE = {"ST101": "not_a_server_error"}
BLOCKING_SCHEMATHESIS_CODE = "ST101"
ID_SEGMENT = re.compile(r"^(?:[0-9a-fA-F-]{32,36}|\d+)$")
# Static routes of the frontend image: the public pages, the app routes of nginx.conf, the
# asset directory and the files in frontend/public. Any other path segment is a variable.
WEB_ROUTES = frozenset(
    {
        "about", "assets", "case-studies", "case-study", "docs", "faq", "forgot-password",
        "healthz", "login", "onboarding", "privacy", "profile", "projects", "register",
        "reset-password", "robots.txt", "sitemap.xml", "terms", "verify-email",
    }
)  # fmt: skip


def schemathesis_completed(rc: int | None, report: dict[str, Any] | None) -> str:
    """Say why a Schemathesis run did not finish, or return an empty string when it did.

    Exit codes, from ``schemathesis/cli/constants.py`` of the pinned release: 0 no failures,
    1 failed checks or non-fatal errors (also an uncaught exception), 2 the run could not do
    its job (configuration, schema, nothing tested), 130 interrupted. Code 1 does not say
    whether the run finished, so the report decides: it must exist, say ``complete`` and the
    stop reason ``completed`` (not ``server_unavailable``, ``failure_limit`` or
    ``interrupted``), and have tested at least one operation.

    :param rc: Exit code of the process, ``None`` when no code was recorded
    :param report: The parsed JSON report, ``None`` when missing or unreadable
    :return: A short reason, empty when the run completed
    """
    if rc not in (0, 1):
        return "exit code outside 0 and 1"
    if report is None:
        return "no readable report"
    if report.get("complete") is not True or report.get("stop_reason") != "completed":
        return "run stopped early"
    operations = report.get("operations") or {}
    if not operations.get("tested"):
        return "no operation was tested"
    return ""


def zap_completed(rc: int | None, report: dict[str, Any] | None) -> str:
    """Say why a ZAP scan did not finish, or return an empty string when it did.

    Exit codes, from ``zap-api-scan.py`` and ``zap-baseline.py`` of the pinned image (the end
    of ``main``): 0 passed, 1 at least one FAIL rule, 2 at least one WARN (never with ``-I``),
    3 any other failure, which covers an exception and a run that passed no rule at all. The
    scripts do not tell whether the scan reached its target, so the report must also have a
    non-empty ``site`` list: a target that was never reached leaves it empty.

    :param rc: Exit code of the process, ``None`` when no code was recorded
    :param report: The parsed JSON report, ``None`` when missing or unreadable
    :return: A short reason, empty when the scan completed
    """
    if rc not in (0, 1, 2):
        return "exit code outside 0 to 2"
    if report is None:
        return "no readable report"
    if not report.get("site"):
        return "target not reached"
    return ""


def read_rc(path: Path) -> int | None:
    """Read an exit code written by the workflow.

    :param path: File holding one integer
    :return: The code, or ``None`` when the file is missing or not an integer
    """
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def read_json(path: Path) -> dict[str, Any] | None:
    """Parse a JSON object from a file.

    :param path: The file
    :return: The object, or ``None`` when the file is missing, unreadable or not an object
    """
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


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
    segments = path.strip("/").split("/")
    best: tuple[int, list[str]] | None = None
    for candidate in spec_paths:
        template = candidate.strip("/").split("/")
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
    """One finding of one scan, reduced to what the gate keeps."""

    fingerprint: str
    risk: str
    blocking: bool


@dataclass
class ToolResult:
    """The gate's view of one scan."""

    name: str
    rc: int | None
    incomplete: str = ""
    findings: dict[str, Finding] = field(default_factory=dict)
    suppressed: list[str] = field(default_factory=list)
    seconds: float | None = None

    def counts(self) -> dict[str, int]:
        """Count what is left after suppression, by the public categories.

        :return: ``blocking`` and ``warnings``, plus ``low`` and ``info`` for a ZAP scan
        """
        blocking = sum(1 for f in self.findings.values() if f.blocking) + bool(self.incomplete)
        counts = {
            "blocking": blocking,
            "warnings": sum(1 for f in self.findings.values() if not f.blocking),
        }
        if self.name.startswith("zap"):
            counts["low"] = sum(1 for f in self.findings.values() if f.risk == "low")
            counts["info"] = sum(1 for f in self.findings.values() if f.risk == "info")
        return counts


def judge_schemathesis(out: Path, accepted: frozenset[str]) -> ToolResult:
    """Read the Schemathesis report and sort its failures.

    :param out: The output directory of the run
    :param accepted: Fingerprints that must not block
    :return: The result for the tool
    """
    reports = sorted((out / "schemathesis").glob("json-*.json"))
    report = read_json(reports[-1]) if reports else None
    result = ToolResult("schemathesis", read_rc(out / "schemathesis.rc"))
    result.incomplete = schemathesis_completed(result.rc, report)
    if report is None:
        return result
    running_time = report.get("running_time")
    result.seconds = float(running_time) if isinstance(running_time, int | float) else None
    for failure in report.get("failures") or []:
        code = str(failure.get("code", ""))
        check = CHECK_BY_CODE.get(code, code.lower())
        for operation in failure.get("operations") or []:
            fingerprint = f"schemathesis:{check}:{operation}"
            blocking = code == BLOCKING_SCHEMATHESIS_CODE
            if blocking and fingerprint in accepted:
                result.suppressed.append(fingerprint)
            else:
                result.findings[fingerprint] = Finding(fingerprint, "failure", blocking)
    return result


def judge_zap(
    name: str,
    report_dir: Path,
    rc_file: Path,
    rules: Path,
    spec: Path | None,
    accepted: frozenset[str],
) -> ToolResult:
    """Read a ZAP JSON report and sort its alerts.

    :param name: ``zap-api`` or ``zap-web``, the tool name used in fingerprints
    :param report_dir: Directory holding ``report.json``
    :param rc_file: File holding the exit code of the scan
    :param rules: The rules file of this scan, read for its IGNORE lines
    :param spec: The pruned OpenAPI file, for ``zap-api`` only
    :param accepted: Fingerprints that must not block
    :return: The result for the tool
    """
    report = read_json(report_dir / "report.json")
    result = ToolResult(name, read_rc(rc_file))
    result.incomplete = zap_completed(result.rc, report)
    if report is None:
        return result
    ignored = ignored_plugins(rules)
    spec_paths: list[str] = []
    if spec is not None:
        spec_document = read_json(spec)
        spec_paths = list((spec_document or {}).get("paths", {}))
    for site in report.get("site") or []:
        for alert in site.get("alerts") or []:
            plugin = str(alert.get("pluginid", ""))
            if plugin in ignored:
                continue
            try:
                risk = int(alert.get("riskcode", 0))
            except (TypeError, ValueError):
                risk = 0
            for instance in alert.get("instances") or []:
                path = urlsplit(str(instance.get("uri", ""))).path
                template = (
                    api_template(path, spec_paths) if name == "zap-api" else web_template(path)
                )
                method = str(instance.get("method", "GET")).upper()
                fingerprint = f"{name}:{plugin}:{method} {template}"
                blocking = risk >= BLOCKING_RISK
                if blocking and fingerprint in accepted:
                    result.suppressed.append(fingerprint)
                else:
                    result.findings[fingerprint] = Finding(
                        fingerprint, RISK_NAMES.get(risk, "high"), blocking
                    )
    return result


def summary_lines(results: list[ToolResult]) -> list[str]:
    """Write the public summary: totals per tool.

    :param results: The result of each tool
    :return: Markdown lines, safe for the job log and the step summary
    """
    lines = ["## DAST", ""]
    for result in results:
        counts = result.counts()
        parts = [f"blocking {counts['blocking']}", f"warnings {counts['warnings']}"]
        parts += [f"{key} {counts[key]}" for key in ("low", "info") if key in counts]
        lines.append(f"- {result.name}: " + ", ".join(parts))
    return lines


def main(out: Path) -> None:
    """Judge the scans in ``out`` and write the summary, the detail and the job output.

    :param out: The output directory of the run
    """
    accepted = open_fingerprints(os.environ.get("DAST_OPEN_FINGERPRINTS", ""))  # noqa: TID251
    results = [
        judge_schemathesis(out, accepted),
        judge_zap("zap-api", out / "zap", out / "zap-api.rc", HERE / "rules-api.conf",
                  out / "zap" / "openapi.pruned.json", accepted),
        judge_zap("zap-web", out / "zap-web", out / "zap-web.rc", HERE / "rules-web.conf", None, accepted),
    ]  # fmt: skip
    blocking = sum(result.counts()["blocking"] for result in results)
    lines = summary_lines(results)
    print("\n".join(lines))
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")  # noqa: TID251
    if summary_file:
        with open(summary_file, "a") as handle:
            handle.write("\n".join(lines) + "\n")
    detail = {
        "blocking": blocking,
        "tools": {
            result.name: {
                "rc": result.rc,
                "incomplete": result.incomplete,
                "seconds": result.seconds,
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
    (out / "gate.json").write_text(json.dumps(detail, indent=1))
    output_file = os.environ.get("GITHUB_OUTPUT")  # noqa: TID251
    if output_file:
        with open(output_file, "a") as handle:
            handle.write(f"blocking={blocking}\n")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "dast-out"))
