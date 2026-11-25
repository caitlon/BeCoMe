"""Unit tests for the DAST gate: what blocks, what only warns and what the public output holds."""

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[4]
PROJECT_ID = "6c1f0a52-7f7e-4a5e-9f0e-0d6a3a8f1b11"


def _load():
    """Import the gate by path, since `.github/dast/` is not a package."""
    spec = importlib.util.spec_from_file_location(
        "dast_gate", ROOT / ".github" / "dast" / "gate.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["dast_gate"] = module
    spec.loader.exec_module(module)
    return module


gate = _load()

SERVER_ERROR = "schemathesis:not_a_server_error:GET /api/v1/projects"
STYLE_SRC = "CSP: style-src unsafe-inline"
SCRIPT_SRC = "CSP: script-src unsafe-inline"
HEALTH = "http://127.0.0.1:8000/api/v1/health"
HEALTH_PRINT = "GET /api/v1/health"
WEB_ROOT = "http://127.0.0.1:8081/"
SCHEMATHESIS_FILE = "schemathesis/json-20261125T000000Z.json"
ZERO = {"blocking": 0, "warnings": 0, "low": 0, "info": 0}
BLOCKED = {**ZERO, "blocking": 1}
LOW_ONLY = {**ZERO, "warnings": 1, "low": 1}
MISSING = object()


def _schemathesis_report(failures: list[Any], **overrides: Any) -> dict[str, Any]:
    """Build a Schemathesis JSON report of a run that finished."""
    report = {
        "complete": True,
        "stop_reason": "completed",
        "operations": {"tested": 25},
        "failures": failures,
    }
    return report | overrides


def _failure(code: str, *operations: str) -> dict[str, Any]:
    """Build one failure group of a Schemathesis report."""
    return {"code": code, "operations": list(operations)}


def _alert(plugin: str, risk: int, uri: str = HEALTH, method: str = "GET", **fields: Any):
    """Build one ZAP alert with one instance; the risk code is a string, as in the report."""
    instance = {"uri": uri, "method": method}
    return {"pluginid": plugin, "riskcode": str(risk), "instances": [instance]} | fields


def _zap_report(*alerts: dict[str, Any]) -> dict[str, Any]:
    """Build a ZAP JSON report with one reached site."""
    return {"site": [{"@name": "http://127.0.0.1:8000", "alerts": list(alerts)}]}


def _clean_run(out: Path, **overrides: Any) -> None:
    """Lay out a run with nothing to report, then apply overrides.

    ``None`` leaves that file out, a string is written as it is, ``rcs`` holds the exit codes.
    """
    spec_paths = {
        f"/api/v1/projects/{PROJECT_ID}/opinions/{{opinion_id}}": {},
        "/api/v1/health": {},
    }
    parts: dict[str, Any] = {
        "schemathesis": _schemathesis_report([]),
        "zap_api": _zap_report(),
        "zap_web": _zap_report(),
        "spec": {"paths": spec_paths},
        "rcs": (0, 0, 0),
    }
    assert overrides.keys() <= parts.keys()
    parts |= overrides
    files = {
        SCHEMATHESIS_FILE: parts["schemathesis"],
        "zap/report.json": parts["zap_api"],
        "zap-web/report.json": parts["zap_web"],
        "zap/openapi.pruned.json": parts["spec"],
    }
    for relative, data in files.items():
        (out / relative).parent.mkdir(parents=True, exist_ok=True)
        if data is not None:
            (out / relative).write_text(data if isinstance(data, str) else json.dumps(data))
    for name, rc in zip(("schemathesis", "zap-api", "zap-web"), parts["rcs"], strict=True):
        if rc is not None:
            (out / f"{name}.rc").write_text(f"{rc}\n")


@pytest.fixture
def run(tmp_path, monkeypatch):
    """Return a function that lays out a run, judges it and returns the detail file."""

    def run_gate(fingerprints: str | None = None, *, lay_out: bool = True, **overrides: Any):
        if lay_out:
            _clean_run(tmp_path, **overrides)
        if fingerprints is None:
            monkeypatch.delenv("DAST_OPEN_FINGERPRINTS", raising=False)
        else:
            monkeypatch.setenv("DAST_OPEN_FINGERPRINTS", fingerprints)
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "github_output"))
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "github_summary"))
        gate.main(tmp_path)
        return json.loads((tmp_path / "gate.json").read_text())

    return run_gate


def test_clean_run_does_not_block(run, tmp_path):
    """No failure and no alert leaves nothing to block, and the output says so."""
    assert run()["blocking"] == 0
    assert (tmp_path / "github_output").read_text() == "blocking=0\n"


def test_only_the_blocking_checks_block(run, tmp_path):
    """Server errors, ignored auth and broken object-level authorization block; the rest warn."""
    failures = [
        _failure("ST101", "GET /api/v1/projects"),
        _failure("ST102", "POST /api/v1/projects"),
        _failure("ST401", "GET /api/v1/projects/{project_id}"),
        _failure("ST402", "GET /api/v1/projects/{project_id}"),
        _failure("ST108", "GET /api/v1/projects", "GET /api/v1/projects/{project_id}"),
        _failure("ST103", "GET /api/v1/invitations"),
    ]

    detail = run(schemathesis=_schemathesis_report(failures))

    tool = detail["tools"]["schemathesis"]
    assert tool["blocking"] == [
        "schemathesis:ignored_auth:GET /api/v1/projects/{project_id}",
        SERVER_ERROR,
        "schemathesis:not_a_server_error:POST /api/v1/projects",
        "schemathesis:object_level_authorization:GET /api/v1/projects/{project_id}",
    ]
    assert tool["counts"] == {"blocking": 4, "warnings": 3}
    assert detail["blocking"] == 4
    assert (tmp_path / "github_output").read_text() == "blocking=4\n"


@pytest.mark.parametrize(
    ("overrides", "errored"),
    [
        ({"operations": {"tested": 20, "errored": 3}, "errors": [{"title": "Connection"}]}, 3),
        ({"errors": [{"title": "Timeout", "count": 1}]}, 1),
    ],
    ids=["errored-operations", "errors-list-alone"],
)
def test_errored_schemathesis_operations_are_warnings(run, overrides, errored):
    """Operations Schemathesis could not test are counted and recorded, and do not block."""
    detail = run(schemathesis=_schemathesis_report([], **overrides), rcs=(1, 0, 0))

    tool = detail["tools"]["schemathesis"]
    assert detail["blocking"] == 0
    assert tool["errored"] == errored
    assert tool["counts"] == {"blocking": 0, "warnings": errored}


def test_schemathesis_failure_without_operations_and_odd_codes(run):
    """A failure without operations counts, lowercase codes count and a block is never lowered."""
    failures = [
        _failure("st401"),
        _failure("NOT_A_SERVER_ERROR", "GET /api/v1/projects"),
        _failure("ST101", "GET /api/v1/projects"),
        _failure("not_a_server_error", "GET /api/v1/projects"),
    ]

    tool = run(schemathesis=_schemathesis_report(failures))["tools"]["schemathesis"]

    assert tool["blocking"] == [
        "schemathesis:ignored_auth:<no operation>",
        SERVER_ERROR,
    ]
    assert tool["warnings"] == []


def test_zap_medium_blocks_and_low_only_warns(run):
    """A Medium alert blocks; a Low or Informational one is a warning."""
    uri = f"http://127.0.0.1:8000/api/v1/projects/{PROJECT_ID}/opinions/1"
    medium = run(zap_api=_zap_report(_alert("90022", 2, uri)))["tools"]["zap-api"]
    low = run(zap_api=_zap_report(_alert("100001", 1), _alert("100000", 0)))["tools"]["zap-api"]

    assert medium["blocking"] == ["zap-api:90022:GET /api/v1/projects/{id}/opinions/{id}"]
    assert medium["counts"] == BLOCKED
    assert low["counts"] == {**ZERO, "warnings": 2, "low": 1, "info": 1}


# fmt: off
IGNORE_CASES = [
    ("zap_web", [_alert("10055", 2, WEB_ROOT, name=STYLE_SRC)], []),
    ("zap_web", [_alert("10055", 2, WEB_ROOT, alert=STYLE_SRC)], []),
    ("zap_web", [_alert("10055", 2, WEB_ROOT, name="CSP: style-src unsafe-hashes")],
     ["zap-web:10055:GET /"]),
    ("zap_api", [_alert("10055", 2, WEB_ROOT, name=STYLE_SRC)], ["zap-api:10055:GET <unmatched>"]),
    ("zap_web", [_alert("10055", 2, WEB_ROOT, name=STYLE_SRC.upper()),
                 _alert("10055", 2, WEB_ROOT, name=SCRIPT_SRC, alertRef="10055-1")],
     ["zap-web:10055-1:GET /"]),
]
# fmt: on


@pytest.mark.parametrize(
    ("tool", "alerts", "blocking"),
    IGNORE_CASES,
    ids=["web-style-src", "alert-field", "unsafe-hashes", "api-ignores-nothing", "script-src"],
)
def test_ignore_rule_of_the_web_scan_drops_the_style_src_alert_only(run, tool, alerts, blocking):
    """Plugin 10055 is ignored by rules-web.conf only, and the gate narrows it to style-src."""
    detail = run(**{tool: _zap_report(*alerts)})

    tool_detail = detail["tools"][tool.replace("_", "-")]
    assert tool_detail["blocking"] == blocking
    assert tool_detail["warnings"] == []
    assert detail["blocking"] == len(blocking)


def _unjudgeable_cases():
    """List the runs the gate cannot judge, each with the one fixed reason it must give."""
    shape, no_finish = "report has an unexpected shape", "scan did not finish"
    tools = ("schemathesis", "zap_api", "zap_web")
    report = _schemathesis_report
    # fmt: off
    cases = [
        ({"rcs": (2, 0, 0)}, "unexpected exit code"),
        ({"rcs": (0, 3, 0)}, "unexpected exit code"),
        ({"rcs": (0, 0, 3)}, "unexpected exit code"),
        ({"zap_web": {"site": []}}, "target not reached"),
        ({"schemathesis": report([], stop_reason="server_unavailable")}, no_finish),
        ({"schemathesis": report([], complete=False)}, no_finish),
        ({"schemathesis": report([], operations={"tested": 0})}, no_finish),
        ({"zap_api": {"site": "text"}}, shape),
        ({"zap_api": {"site": [{"alerts": "text"}]}}, shape),
        ({"zap_api": {"site": [{"alerts": [{"instances": "text", "riskcode": "2"}]}]}}, shape),
        ({"zap_web": {"site": [{"alerts": [1]}]}}, shape),
        ({"zap_web": {"site": [1]}}, shape),
        ({"schemathesis": report([], operations=[1])}, shape),
        ({"schemathesis": report("text")}, shape),
        ({"schemathesis": report([1])}, shape),
        ({"schemathesis": report([{"code": "ST101", "operations": 5}])}, shape),
        ({"schemathesis": report([{"code": "ST101", "operations": "GET /x"}])}, shape),
        ({"schemathesis": report([], errors="text")}, shape),
        ({"schemathesis": report([], operations={"tested": 3, "errored": "x"})}, shape),
    ]
    # fmt: on
    cases += [({tool: None}, "report missing") for tool in tools]
    for bad_rc in (None, "x"):
        cases += [
            ({"rcs": tuple(bad_rc if at == i else 0 for i in range(3))}, "unexpected exit code")
            for at in range(3)
        ]
    cases += [
        ({tool: content}, "report unreadable")
        for tool in tools
        for content in ("{not json", "[]", '"text"', "")
    ]
    specs = (None, "not json", "[]", '{"paths": []}', '{"paths": {}}', '{"info": {}}')
    return cases + [({"spec": spec}, "spec missing") for spec in specs]


@pytest.mark.parametrize(("overrides", "reason"), _unjudgeable_cases())
def test_a_scan_that_cannot_be_judged_blocks_alone(run, tmp_path, overrides, reason):
    """A bad exit code, an unfinished scan or an unusable report blocks one tool, never a crash."""
    detail = run(**overrides)

    assert sorted(t["incomplete"] for t in detail["tools"].values()) == ["", "", reason]
    assert detail["blocking"] == 1
    assert (tmp_path / "github_output").read_text() == "blocking=1\n"


@pytest.mark.parametrize("rcs", [(1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 2, 0), (0, 0, 2)])
def test_exit_code_one_or_zap_two_with_a_finished_report_is_not_incomplete(run, rcs):
    """Exit code 1 means failed checks or a FAIL rule, ZAP's 2 a WARN rule: the report decides."""
    report = _schemathesis_report([_failure("ST108", "GET /api/v1/projects")])

    detail = run(schemathesis=report, rcs=rcs)

    assert {t["incomplete"] for t in detail["tools"].values()} == {""}
    assert detail["blocking"] == 0


def test_more_than_one_schemathesis_report_is_incomplete(run, tmp_path):
    """One run writes one report, so a second file means the exit code cannot be tied to one."""
    _clean_run(tmp_path)
    (tmp_path / "schemathesis" / "json-20261125T010000Z.json").write_text("{}")

    detail = run(lay_out=False)

    assert detail["tools"]["schemathesis"]["incomplete"] == "more than one report"
    assert detail["blocking"] == 1


def test_output_directory_is_created_when_missing(tmp_path, monkeypatch):
    """With nothing from the scans at all, the gate still writes its detail and blocks."""
    out = tmp_path / "not" / "there"
    monkeypatch.delenv("DAST_OPEN_FINGERPRINTS", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "github_output"))

    gate.main(out)

    detail = json.loads((out / "gate.json").read_text())
    assert detail["blocking"] == 3
    assert {t["incomplete"] for t in detail["tools"].values()} == {"report missing"}
    assert (tmp_path / "github_output").read_text() == "blocking=3\n"


def test_fingerprints_hold_templates_and_never_a_payload(run):
    """Ids become {id}, an unknown API path becomes <unmatched> and web segments become {x}."""
    host = "http://127.0.0.1:8000/api/v1"
    api = _zap_report(
        _alert("40018", 3, f"{host}/pro%27jects/1/opinions/1?q=<script>", "POST"),
        _alert("40018", 3, f"{host}/projects/%27%20OR%201%3D1--/opinions/1?q=<script>"),
        _alert("40018", 3, f"{host}/projects/{PROJECT_ID}/opinions/77?x=1"),
    )
    web = _zap_report(_alert("10038", 2, "http://127.0.0.1:8081/assets/index-AbC123.js?v=<x>"))

    detail = run(zap_api=api, zap_web=web)

    assert detail["tools"]["zap-api"]["blocking"] == [
        "zap-api:40018:GET /api/v1/projects/{id}/opinions/{id}",
        "zap-api:40018:POST <unmatched>",
    ]
    assert detail["tools"]["zap-web"]["blocking"] == ["zap-web:10038:GET /assets/{x}"]


def test_api_template_prefers_literal_segments_and_never_maps_the_root():
    """Of two templates of one length the literal match wins, and `/` fits no template."""
    spec = ["/api/v1/projects/{id}", "/api/v1/projects/mine", "/{id}"]

    assert gate.api_template("/api/v1/projects/mine", spec) == "/api/v1/projects/mine"
    assert gate.api_template("/", spec) == "<unmatched>"


def test_public_output_holds_totals_and_fixed_reasons_only(run, tmp_path, capsys):
    """The log and the step summary carry counts per tool and a fixed reason, nothing else."""
    failures = [_failure("ST101", "GET /api/v1/projects"), _failure("ST108", HEALTH_PRINT)]
    zap_api = _zap_report(_alert("90022", 2))
    incomplete = "(scan incomplete: target not reached)"

    run(
        schemathesis=_schemathesis_report(failures),
        zap_api=zap_api,
        zap_web={"site": [], "note": "secret-looking-text"},
    )

    for text in (capsys.readouterr().out, (tmp_path / "github_summary").read_text()):
        assert "schemathesis: blocking 1, warnings 1" in text
        assert "zap-api: blocking 1, warnings 0, low 0, info 0" in text
        assert f"zap-web: blocking 1, warnings 0, low 0, info 0 {incomplete}" in text
        for secret in ("/api/", "90022", "ST101", "secret-looking-text"):
            assert secret not in text


def test_parsers_and_shipped_rules(tmp_path):
    """Open fingerprints drop blanks and comments, only IGNORE lines count, and the files agree."""
    rules = tmp_path / "rules.conf"
    rules.write_text("# c\n*\tOUTOFSCOPE\t.*logout.*\n10055\tIGNORE\t(x)\n10010\tWARN\t(y)\n")
    dast = ROOT / ".github" / "dast"

    assert gate.open_fingerprints("") == set()
    assert gate.open_fingerprints("\n  \n# note\n a \nb\n") == {"a", "b"}
    assert gate.ignored_plugins(rules) == {"10055"}
    assert gate.ignored_plugins(tmp_path / "missing.conf") == set()
    assert gate.ignored_plugins(dast / "rules-api.conf") == set()
    assert gate.ignored_plugins(dast / "rules-web.conf") == {"10055"}


def test_web_files_of_the_frontend_public_folder_keep_their_names():
    """Static files that exist in frontend/public are routes, not variable segments."""
    names = {path.name for path in (ROOT / "frontend" / "public").iterdir() if path.is_file()}

    assert names
    assert names <= gate.WEB_ROUTES


@pytest.mark.parametrize(
    ("risks", "counts"),
    [((2, 1), BLOCKED), ((1, 2), BLOCKED), ((1, 0), LOW_ONLY), ((0, 1), LOW_ONLY),
     ((3, 2, 0), BLOCKED)],
)  # fmt: skip
def test_alerts_sharing_a_fingerprint_keep_the_highest_risk(run, risks, counts):
    """Whatever the order, one fingerprint is one finding with the highest risk seen."""
    detail = run(zap_api=_zap_report(*(_alert("10055", risk) for risk in risks)))

    assert detail["tools"]["zap-api"]["counts"] == counts
    assert detail["blocking"] == counts["blocking"]


def test_alert_references_make_distinct_findings(run):
    """Two alerts of one plugin with different references are two findings, not one."""
    alerts = (_alert("100000", 1, alertRef="100000-1"), _alert("100000", 0, alertRef="100000-2"))

    tool = run(zap_api=_zap_report(*alerts))["tools"]["zap-api"]

    assert tool["warnings"] == [f"zap-api:100000-{n}:{HEALTH_PRINT}" for n in (1, 2)]
    assert tool["counts"] == {"blocking": 0, "warnings": 2, "low": 1, "info": 1}


@pytest.mark.parametrize("instances", [[], None])
def test_alert_without_instances_still_counts(run, instances):
    """An alert with an empty or missing instance list keeps its risk."""
    alerts = [_alert("90022", 2), _alert("100001", 1)]
    for alert in alerts:
        alert.pop("instances")
        if instances is not None:
            alert["instances"] = instances

    tool = run(zap_api=_zap_report(*alerts))["tools"]["zap-api"]

    assert tool["blocking"] == ["zap-api:90022:- <no instance>"]
    assert tool["warnings"] == ["zap-api:100001:- <no instance>"]


@pytest.mark.parametrize(
    "riskcode",
    [None, "", "high", "4", "-1", "2.5", [2], {"a": 1}, MISSING, 2, True, False, 0.5, 1.5, 2.0],
    ids=lambda value: "missing" if value is MISSING else repr(value),
)
def test_unreadable_or_medium_risk_code_blocks(run, riskcode):
    """A risk the gate cannot read is the worst case, and an integer Medium reads like a string."""
    alert = _alert("90022", 1)
    if riskcode is MISSING:
        del alert["riskcode"]
    else:
        alert["riskcode"] = riskcode

    detail = run(zap_api=_zap_report(alert))

    assert detail["tools"]["zap-api"]["blocking"] == [f"zap-api:90022:{HEALTH_PRINT}"]
    assert detail["blocking"] == 1


SERVER_ERROR_REPORT = _schemathesis_report([_failure("ST101", "GET /api/v1/projects")])
# fmt: off
SUPPRESSION_CASES = [
    ("schemathesis", {"schemathesis": SERVER_ERROR_REPORT},
     f"# known\n\n{SERVER_ERROR}\nzap-web:1:GET /\n", {"blocking": 0, "warnings": 0},
     [SERVER_ERROR]),
    ("zap-api", {"zap_api": _zap_report(_alert("90022", 2), _alert("90022", 3))},
     f"zap-api:90022:{HEALTH_PRINT}", ZERO, [f"zap-api:90022:{HEALTH_PRINT}"]),
    ("zap-api", {"zap_api": _zap_report(_alert("100001", 1), _alert("90022", 2, method="POST"))},
     f"zap-api:100001:{HEALTH_PRINT}", {**LOW_ONLY, "blocking": 1}, []),
    ("zap-web", {"zap_web": {"site": []}}, "zap-web:incomplete\nzap-web:10055:GET /", BLOCKED, []),
]
# fmt: on


@pytest.mark.parametrize(
    ("tool", "overrides", "listed", "counts", "suppressed"),
    SUPPRESSION_CASES,
    ids=["schemathesis-listed", "zap-medium-dropped-once", "zap-low-unchanged", "incomplete-stays"],
)
def test_suppression_reaches_blocking_findings_only(
    run, tool, overrides, listed, counts, suppressed
):
    """A listed Medium drops once; a listed Low and an incomplete scan stay as they are."""
    detail = run(listed, **overrides)["tools"][tool]

    assert detail["suppressed"] == suppressed
    assert detail["counts"] == counts


def test_two_sites_in_one_report_are_both_read(run):
    """A ZAP report can hold several sites; alerts of each one count."""
    sites = [
        _zap_report(_alert(plugin, 2, "http://x/a"))["site"][0] for plugin in ("10038", "10096")
    ]

    detail = run(zap_web={"site": sites})

    assert detail["tools"]["zap-web"]["blocking"] == [
        "zap-web:10038:GET /{x}",
        "zap-web:10096:GET /{x}",
    ]
