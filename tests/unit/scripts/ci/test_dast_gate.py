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

SERVER_ERROR_FINGERPRINT = "schemathesis:not_a_server_error:GET /api/v1/projects"
STYLE_SRC = "CSP: style-src unsafe-inline"
SCRIPT_SRC = "CSP: script-src unsafe-inline"
HEALTH = "http://127.0.0.1:8000/api/v1/health"


def _schemathesis_report(failures: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    """Build a Schemathesis JSON report of a run that finished."""
    report: dict[str, Any] = {
        "complete": True,
        "stop_reason": "completed",
        "running_time": 12.5,
        "operations": {"tested": 25},
        "failures": failures,
    }
    report.update(overrides)
    return report


def _failure(code: str, *operations: str) -> dict[str, Any]:
    """Build one failure group of a Schemathesis report."""
    return {"code": code, "operations": list(operations)}


def _alert(plugin: str, risk: int, uri: str, method: str = "GET", **fields: Any) -> dict[str, Any]:
    """Build one ZAP alert with one instance; the risk code is a string, as in the report."""
    alert = {
        "pluginid": plugin,
        "riskcode": str(risk),
        "instances": [{"uri": uri, "method": method}],
    }
    alert.update(fields)
    return alert


def _zap_report(*alerts: dict[str, Any]) -> dict[str, Any]:
    """Build a ZAP JSON report with one reached site."""
    return {"site": [{"@name": "http://127.0.0.1:8000", "alerts": list(alerts)}]}


def _write_run(
    out: Path,
    *,
    schemathesis: dict[str, Any] | None,
    zap_api: dict[str, Any] | None,
    zap_web: dict[str, Any] | None,
    rcs: tuple[int, int, int] = (1, 0, 0),
) -> None:
    """Lay out an output directory the way the workflow leaves it."""
    (out / "schemathesis").mkdir(parents=True)
    (out / "zap").mkdir()
    (out / "zap-web").mkdir()
    if schemathesis is not None:
        (out / "schemathesis" / "json-20261125T000000Z.json").write_text(json.dumps(schemathesis))
    if zap_api is not None:
        (out / "zap" / "report.json").write_text(json.dumps(zap_api))
    if zap_web is not None:
        (out / "zap-web" / "report.json").write_text(json.dumps(zap_web))
    spec = {
        "paths": {
            f"/api/v1/projects/{PROJECT_ID}/opinions/{{opinion_id}}": {},
            "/api/v1/health": {},
        }
    }
    (out / "zap" / "openapi.pruned.json").write_text(json.dumps(spec))
    for name, rc in zip(("schemathesis", "zap-api", "zap-web"), rcs, strict=True):
        (out / f"{name}.rc").write_text(f"{rc}\n")


def _clean_run(out: Path, **overrides: Any) -> None:
    """Lay out a run with nothing to report, then apply the overrides."""
    parts: dict[str, Any] = {
        "schemathesis": _schemathesis_report([]),
        "zap_api": _zap_report(),
        "zap_web": _zap_report(),
        "rcs": (0, 0, 0),
    }
    parts.update(overrides)
    _write_run(out, **parts)


def _run_gate(
    out: Path, monkeypatch: pytest.MonkeyPatch, open_fingerprints: str | None = None
) -> dict[str, Any]:
    """Run the gate on a directory and return its detail file."""
    if open_fingerprints is None:
        monkeypatch.delenv("DAST_OPEN_FINGERPRINTS", raising=False)
    else:
        monkeypatch.setenv("DAST_OPEN_FINGERPRINTS", open_fingerprints)
    monkeypatch.setenv("GITHUB_OUTPUT", str(out / "github_output"))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(out / "github_summary"))
    gate.main(out)
    return json.loads((out / "gate.json").read_text())


def test_clean_run_does_not_block(tmp_path, monkeypatch):
    """No failure and no alert leaves nothing to block, and the output says so."""
    _clean_run(tmp_path)

    detail = _run_gate(tmp_path, monkeypatch)

    assert detail["blocking"] == 0
    assert (tmp_path / "github_output").read_text() == "blocking=0\n"


def test_server_error_blocks(tmp_path, monkeypatch):
    """A not_a_server_error failure blocks, and the other check failures do not."""
    failures = [
        _failure("ST101", "GET /api/v1/projects"),
        _failure("ST108", "GET /api/v1/projects", "GET /api/v1/projects/{project_id}"),
        _failure("ST103", "GET /api/v1/invitations"),
    ]
    _clean_run(tmp_path, schemathesis=_schemathesis_report(failures))

    detail = _run_gate(tmp_path, monkeypatch)

    tool = detail["tools"]["schemathesis"]
    assert detail["blocking"] == 1
    assert tool["blocking"] == [SERVER_ERROR_FINGERPRINT]
    assert tool["counts"] == {"blocking": 1, "warnings": 3}
    assert (tmp_path / "github_output").read_text() == "blocking=1\n"


def test_listed_fingerprint_is_suppressed_and_left_out_of_the_counts(tmp_path, monkeypatch):
    """A fingerprint in the environment list does not block and is not counted anywhere."""
    failures = [_failure("ST101", "GET /api/v1/projects")]
    _clean_run(tmp_path, schemathesis=_schemathesis_report(failures))

    detail = _run_gate(
        tmp_path, monkeypatch, f"# known\n\n{SERVER_ERROR_FINGERPRINT}\nzap-web:1:GET /\n"
    )

    tool = detail["tools"]["schemathesis"]
    assert detail["blocking"] == 0
    assert tool["suppressed"] == [SERVER_ERROR_FINGERPRINT]
    assert tool["counts"] == {"blocking": 0, "warnings": 0}


def test_zap_medium_blocks_and_low_only_warns(tmp_path, monkeypatch):
    """A Medium alert blocks; a Low or Informational one is a warning."""
    medium = _zap_report(
        _alert("90022", 2, f"http://127.0.0.1:8000/api/v1/projects/{PROJECT_ID}/opinions/1")
    )
    (tmp_path / "medium").mkdir()
    _clean_run(tmp_path / "medium", zap_api=medium)
    low = _zap_report(
        _alert("100001", 1, "http://127.0.0.1:8000/api/v1/health"),
        _alert("100000", 0, "http://127.0.0.1:8000/api/v1/health"),
    )
    (tmp_path / "low").mkdir()
    _clean_run(tmp_path / "low", zap_api=low)

    blocking = _run_gate(tmp_path / "medium", monkeypatch)
    warning = _run_gate(tmp_path / "low", monkeypatch)

    assert blocking["blocking"] == 1
    assert blocking["tools"]["zap-api"]["blocking"] == [
        "zap-api:90022:GET /api/v1/projects/{id}/opinions/{id}"
    ]
    assert warning["blocking"] == 0
    assert warning["tools"]["zap-api"]["counts"] == {
        "blocking": 0,
        "warnings": 2,
        "low": 1,
        "info": 1,
    }


def test_ignore_rule_of_the_web_scan_drops_the_alert_but_not_in_the_api_scan(tmp_path, monkeypatch):
    """Plugin 10055 is ignored by rules-web.conf only, and the gate applies that itself."""
    alert = _alert("10055", 2, "http://127.0.0.1:8081/", name=STYLE_SRC)
    (tmp_path / "web").mkdir()
    _clean_run(tmp_path / "web", zap_web=_zap_report(alert), rcs=(0, 0, 2))
    (tmp_path / "api").mkdir()
    _clean_run(tmp_path / "api", zap_api=_zap_report(alert), rcs=(0, 2, 0))

    web = _run_gate(tmp_path / "web", monkeypatch)
    api = _run_gate(tmp_path / "api", monkeypatch)

    assert web["blocking"] == 0
    assert api["blocking"] == 1


@pytest.mark.parametrize("missing", ["schemathesis", "zap_api", "zap_web"])
def test_missing_report_blocks(tmp_path, monkeypatch, missing):
    """A scan that left no readable report counts as one blocking item."""
    _clean_run(tmp_path, **{missing: None})

    detail = _run_gate(tmp_path, monkeypatch)

    assert detail["blocking"] == 1
    assert "report missing" in {t["incomplete"] for t in detail["tools"].values()}


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"rcs": (2, 0, 0)}, "unexpected exit code"),
        ({"rcs": (0, 3, 0)}, "unexpected exit code"),
        ({"rcs": (0, 0, 3)}, "unexpected exit code"),
        ({"zap_web": {"site": []}}, "target not reached"),
        (
            {"schemathesis": _schemathesis_report([], stop_reason="server_unavailable")},
            "scan did not finish",
        ),
        ({"schemathesis": _schemathesis_report([], complete=False)}, "scan did not finish"),
        (
            {"schemathesis": _schemathesis_report([], operations={"tested": 0})},
            "scan did not finish",
        ),
    ],
)
def test_a_scan_that_did_not_complete_blocks(tmp_path, monkeypatch, overrides, reason):
    """An exit code or a report that says the scan did not finish blocks, whatever it found."""
    _clean_run(tmp_path, **overrides)

    detail = _run_gate(tmp_path, monkeypatch)

    assert detail["blocking"] == 1
    assert reason in {t["incomplete"] for t in detail["tools"].values()}


def test_exit_code_one_with_a_finished_report_is_not_incomplete(tmp_path, monkeypatch):
    """Schemathesis exits 1 for failed checks, so the report decides completion."""
    failures = [_failure("ST108", "GET /api/v1/projects")]
    _clean_run(tmp_path, schemathesis=_schemathesis_report(failures), rcs=(1, 0, 0))

    detail = _run_gate(tmp_path, monkeypatch)

    assert detail["tools"]["schemathesis"]["incomplete"] == ""
    assert detail["blocking"] == 0


def test_incomplete_scan_cannot_be_suppressed(tmp_path, monkeypatch):
    """The open-fingerprint list only reaches findings, never a scan that did not finish."""
    _clean_run(tmp_path, zap_web={"site": []})

    detail = _run_gate(tmp_path, monkeypatch, "zap-web:incomplete\nzap-web:10055:GET /")

    assert detail["blocking"] == 1


def test_fingerprints_hold_templates_and_never_a_payload(tmp_path, monkeypatch):
    """Ids become {id}, an unknown API path becomes <unmatched> and web segments become {x}."""
    unknown = "http://127.0.0.1:8000/api/v1/pro%27jects/1/opinions/1?q=<script>"
    in_id = "http://127.0.0.1:8000/api/v1/projects/%27%20OR%201%3D1--/opinions/1?q=<script>"
    baked = f"http://127.0.0.1:8000/api/v1/projects/{PROJECT_ID}/opinions/77?x=1"
    api = _zap_report(
        _alert("40018", 3, unknown, "POST"),
        _alert("40018", 3, in_id),
        _alert("40018", 3, baked),
    )
    web = _zap_report(_alert("10038", 2, "http://127.0.0.1:8081/assets/index-AbC123.js?v=<x>"))
    _clean_run(tmp_path, zap_api=api, zap_web=web, rcs=(0, 2, 2))

    detail = _run_gate(tmp_path, monkeypatch)

    assert detail["tools"]["zap-api"]["blocking"] == [
        "zap-api:40018:GET /api/v1/projects/{id}/opinions/{id}",
        "zap-api:40018:POST <unmatched>",
    ]
    assert detail["tools"]["zap-web"]["blocking"] == ["zap-web:10038:GET /assets/{x}"]


def test_public_output_holds_totals_only(tmp_path, monkeypatch, capsys):
    """The log and the step summary carry counts per tool, no fingerprint and no path."""
    failures = [_failure("ST101", "GET /api/v1/projects"), _failure("ST108", "GET /api/v1/health")]
    zap = _zap_report(_alert("90022", 2, "http://127.0.0.1:8000/api/v1/health"))
    _clean_run(tmp_path, schemathesis=_schemathesis_report(failures), zap_api=zap, rcs=(1, 2, 0))

    _run_gate(tmp_path, monkeypatch)

    printed = capsys.readouterr().out
    summary = (tmp_path / "github_summary").read_text()
    for text in (printed, summary):
        assert "schemathesis: blocking 1, warnings 1" in text
        assert "zap-api: blocking 1, warnings 0, low 0, info 0" in text
        assert "zap-web: blocking 0, warnings 0, low 0, info 0" in text
        assert "/api/" not in text
        assert "90022" not in text
        assert "ST101" not in text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("", set()), ("\n  \n# note\n a \nb\n", {"a", "b"})],
)
def test_open_fingerprints_parsing(raw, expected):
    """Blank lines and comment lines are not fingerprints; the rest is trimmed."""
    assert gate.open_fingerprints(raw) == expected


def test_ignored_plugins_reads_only_ignore_lines(tmp_path):
    """OUTOFSCOPE lines and comments do not become ignored plugin ids."""
    rules = tmp_path / "rules.conf"
    rules.write_text("# c\n*\tOUTOFSCOPE\t.*logout.*\n10055\tIGNORE\t(x)\n10010\tWARN\t(y)\n")

    assert gate.ignored_plugins(rules) == {"10055"}
    assert gate.ignored_plugins(tmp_path / "missing.conf") == set()


def test_shipped_rules_files_ignore_what_the_design_says():
    """The API scan ignores nothing and the web scan ignores the CSP rule alone."""
    dast = ROOT / ".github" / "dast"

    assert gate.ignored_plugins(dast / "rules-api.conf") == set()
    assert gate.ignored_plugins(dast / "rules-web.conf") == {"10055"}


@pytest.mark.parametrize(
    ("risks", "blocking", "counts"),
    [
        ((2, 1), 1, {"blocking": 1, "warnings": 0, "low": 0, "info": 0}),
        ((1, 2), 1, {"blocking": 1, "warnings": 0, "low": 0, "info": 0}),
        ((1, 0), 0, {"blocking": 0, "warnings": 1, "low": 1, "info": 0}),
        ((0, 1), 0, {"blocking": 0, "warnings": 1, "low": 1, "info": 0}),
        ((3, 2, 0), 1, {"blocking": 1, "warnings": 0, "low": 0, "info": 0}),
    ],
)
def test_alerts_sharing_a_fingerprint_keep_the_highest_risk(
    tmp_path, monkeypatch, risks, blocking, counts
):
    """Whatever the order, one fingerprint is one finding with the highest risk seen."""
    api = _zap_report(*(_alert("10055", risk, HEALTH) for risk in risks))
    _clean_run(tmp_path, zap_api=api, rcs=(0, 2, 0))

    detail = _run_gate(tmp_path, monkeypatch)

    assert detail["tools"]["zap-api"]["counts"] == counts
    assert detail["blocking"] == blocking


def test_alert_references_make_distinct_findings(tmp_path, monkeypatch):
    """Two alerts of one plugin with different references are two findings, not one."""
    api = _zap_report(
        _alert("100000", 1, HEALTH, alertRef="100000-1"),
        _alert("100000", 0, HEALTH, alertRef="100000-2"),
    )
    _clean_run(tmp_path, zap_api=api, rcs=(0, 2, 0))

    detail = _run_gate(tmp_path, monkeypatch)

    tool = detail["tools"]["zap-api"]
    assert tool["warnings"] == [
        "zap-api:100000-1:GET /api/v1/health",
        "zap-api:100000-2:GET /api/v1/health",
    ]
    assert tool["counts"] == {"blocking": 0, "warnings": 2, "low": 1, "info": 1}


@pytest.mark.parametrize("instances", [[], None])
def test_alert_without_instances_still_counts(tmp_path, monkeypatch, instances):
    """An alert with an empty or missing instance list keeps its risk."""
    medium = _alert("90022", 2, HEALTH)
    low = _alert("100001", 1, HEALTH)
    for alert in (medium, low):
        if instances is None:
            del alert["instances"]
        else:
            alert["instances"] = instances
    _clean_run(tmp_path, zap_api=_zap_report(medium, low), rcs=(0, 2, 0))

    detail = _run_gate(tmp_path, monkeypatch)

    tool = detail["tools"]["zap-api"]
    assert tool["blocking"] == ["zap-api:90022:- <no instance>"]
    assert tool["warnings"] == ["zap-api:100001:- <no instance>"]


@pytest.mark.parametrize("riskcode", [None, "", "high", "4", "-1", "2.5", [2], {"a": 1}])
def test_unreadable_risk_code_blocks(tmp_path, monkeypatch, riskcode):
    """A risk the gate cannot read is treated as the worst case."""
    alert = _alert("90022", 1, HEALTH)
    alert["riskcode"] = riskcode
    _clean_run(tmp_path, zap_api=_zap_report(alert), rcs=(0, 2, 0))

    detail = _run_gate(tmp_path, monkeypatch)

    assert detail["tools"]["zap-api"]["blocking"] == ["zap-api:90022:GET /api/v1/health"]
    assert detail["blocking"] == 1


def test_missing_riskcode_key_blocks(tmp_path, monkeypatch):
    """An alert with no risk code at all blocks."""
    alert = _alert("90022", 1, HEALTH)
    del alert["riskcode"]
    _clean_run(tmp_path, zap_web=_zap_report(alert), rcs=(0, 0, 2))

    assert _run_gate(tmp_path, monkeypatch)["blocking"] == 1


def test_integer_risk_code_is_read(tmp_path, monkeypatch):
    """A risk code given as a number works like the digit string of a real report."""
    alert = _alert("90022", 1, HEALTH)
    alert["riskcode"] = 2
    _clean_run(tmp_path, zap_api=_zap_report(alert), rcs=(0, 2, 0))

    assert _run_gate(tmp_path, monkeypatch)["blocking"] == 1


@pytest.mark.parametrize("spec", [None, "not json", "[]", '{"paths": []}', '{"info": {}}'])
def test_missing_or_unusable_spec_makes_the_api_scan_incomplete(tmp_path, monkeypatch, spec):
    """Without the paths of the API the fingerprints cannot be trusted, so the scan blocks."""
    _clean_run(tmp_path)
    spec_file = tmp_path / "zap" / "openapi.pruned.json"
    if spec is None:
        spec_file.unlink()
    else:
        spec_file.write_text(spec)

    detail = _run_gate(tmp_path, monkeypatch)

    assert detail["tools"]["zap-api"]["incomplete"] == "spec missing"
    assert detail["blocking"] == 1


def test_zap_suppression_drops_a_listed_blocking_fingerprint(tmp_path, monkeypatch):
    """A listed zap-api fingerprint drops a Medium, once, whatever the number of alerts."""
    api = _zap_report(_alert("90022", 2, HEALTH), _alert("90022", 3, HEALTH))
    _clean_run(tmp_path, zap_api=api, rcs=(0, 2, 0))

    detail = _run_gate(tmp_path, monkeypatch, "zap-api:90022:GET /api/v1/health")

    tool = detail["tools"]["zap-api"]
    assert detail["blocking"] == 0
    assert tool["suppressed"] == ["zap-api:90022:GET /api/v1/health"]
    assert tool["counts"] == {"blocking": 0, "warnings": 0, "low": 0, "info": 0}


def test_listing_the_fingerprint_of_a_low_finding_changes_nothing(tmp_path, monkeypatch):
    """Only blocking findings are suppressed: a listed Low stays a counted warning."""
    api = _zap_report(_alert("100001", 1, HEALTH), _alert("90022", 2, HEALTH, "POST"))
    _clean_run(tmp_path, zap_api=api, rcs=(0, 2, 0))

    detail = _run_gate(tmp_path, monkeypatch, "zap-api:100001:GET /api/v1/health")

    tool = detail["tools"]["zap-api"]
    assert detail["blocking"] == 1
    assert tool["suppressed"] == []
    assert tool["counts"] == {"blocking": 1, "warnings": 1, "low": 1, "info": 0}


@pytest.mark.parametrize("tool_index", [1, 2])
def test_zap_exit_codes_one_and_three(tmp_path, monkeypatch, tool_index):
    """ZAP exit code 1 (a FAIL rule) is a finished scan; 3 is a scan that broke."""
    names = ("schemathesis", "zap-api", "zap-web")
    finished = [0, 0, 0]
    finished[tool_index] = 1
    broken = [0, 0, 0]
    broken[tool_index] = 3
    (tmp_path / "finished").mkdir()
    _clean_run(tmp_path / "finished", rcs=tuple(finished))
    (tmp_path / "broken").mkdir()
    _clean_run(tmp_path / "broken", rcs=tuple(broken))

    accepted = _run_gate(tmp_path / "finished", monkeypatch)
    refused = _run_gate(tmp_path / "broken", monkeypatch)

    assert accepted["tools"][names[tool_index]]["incomplete"] == ""
    assert accepted["blocking"] == 0
    assert refused["tools"][names[tool_index]]["incomplete"] == "unexpected exit code"
    assert refused["blocking"] == 1


def test_web_rule_is_ignored_for_style_src_only(tmp_path, monkeypatch):
    """The ignored CSP rule drops the style-src alert; a script-src alert of it still blocks."""
    uri = "http://127.0.0.1:8081/"
    style_only = _zap_report(_alert("10055", 2, uri, name=STYLE_SRC))
    mixed = _zap_report(
        _alert("10055", 2, uri, name=STYLE_SRC.upper()),
        _alert("10055", 2, uri, name=SCRIPT_SRC, alertRef="10055-1"),
    )
    (tmp_path / "style").mkdir()
    _clean_run(tmp_path / "style", zap_web=style_only, rcs=(0, 0, 2))
    (tmp_path / "mixed").mkdir()
    _clean_run(tmp_path / "mixed", zap_web=mixed, rcs=(0, 0, 2))

    style = _run_gate(tmp_path / "style", monkeypatch)
    both = _run_gate(tmp_path / "mixed", monkeypatch)

    assert style["blocking"] == 0
    assert style["tools"]["zap-web"]["counts"] == {
        "blocking": 0,
        "warnings": 0,
        "low": 0,
        "info": 0,
    }
    assert both["tools"]["zap-web"]["blocking"] == ["zap-web:10055-1:GET /"]
    assert both["blocking"] == 1


def test_two_sites_in_one_report_are_both_read(tmp_path, monkeypatch):
    """A ZAP report can hold several sites; alerts of each one count."""
    web = {
        "site": [
            {"@name": "http://127.0.0.1:8081", "alerts": [_alert("10038", 2, "http://x/a")]},
            {"@name": "http://127.0.0.1:8082", "alerts": [_alert("10096", 2, "http://x/b")]},
        ]
    }
    _clean_run(tmp_path, zap_web=web, rcs=(0, 0, 2))

    detail = _run_gate(tmp_path, monkeypatch)

    assert detail["tools"]["zap-web"]["blocking"] == [
        "zap-web:10038:GET /{x}",
        "zap-web:10096:GET /{x}",
    ]


def test_web_files_of_the_frontend_public_folder_keep_their_names():
    """Static files that exist in frontend/public are routes, not variable segments."""
    public = ROOT / "frontend" / "public"
    names = {path.name for path in public.iterdir() if path.is_file()}

    assert names
    assert names <= gate.WEB_ROUTES


@pytest.mark.parametrize("tool", ["schemathesis", "zap_api", "zap_web"])
@pytest.mark.parametrize("content", ["{not json", "[]", '"text"', ""])
def test_malformed_report_blocks_as_unreadable(tmp_path, monkeypatch, tool, content):
    """A report that is not a JSON object counts as one blocking item, and the gate goes on."""
    _clean_run(tmp_path)
    path = {
        "schemathesis": tmp_path / "schemathesis" / "json-20261125T000000Z.json",
        "zap_api": tmp_path / "zap" / "report.json",
        "zap_web": tmp_path / "zap-web" / "report.json",
    }[tool]
    path.write_text(content)

    detail = _run_gate(tmp_path, monkeypatch)

    assert detail["blocking"] == 1
    assert "report unreadable" in {t["incomplete"] for t in detail["tools"].values()}
    assert (tmp_path / "github_output").read_text() == "blocking=1\n"


@pytest.mark.parametrize(
    ("tool", "report"),
    [
        ("zap_api", {"site": "text"}),
        ("zap_api", {"site": [{"alerts": "text"}]}),
        ("zap_api", {"site": [{"alerts": [{"instances": "text", "riskcode": "2"}]}]}),
        ("zap_web", {"site": [{"alerts": [1]}]}),
        ("zap_web", {"site": [1]}),
        ("schemathesis", _schemathesis_report([], operations=[1])),
        ("schemathesis", _schemathesis_report("text")),
        ("schemathesis", _schemathesis_report([1])),
        ("schemathesis", _schemathesis_report([{"code": "ST101", "operations": 5}])),
        ("schemathesis", _schemathesis_report([], operations={"tested": 3, "errored": "x"})),
    ],
)
def test_wrong_typed_report_marks_only_that_tool_incomplete(tmp_path, monkeypatch, tool, report):
    """A structure of the wrong type is an incomplete scan with a fixed reason, not a crash."""
    _clean_run(tmp_path, **{tool: report})

    detail = _run_gate(tmp_path, monkeypatch)

    reasons = [t["incomplete"] for t in detail["tools"].values()]
    assert sorted(reasons) == ["", "", "report has an unexpected shape"]
    assert detail["blocking"] == 1
    assert (tmp_path / "github_output").read_text() == "blocking=1\n"


def test_output_directory_is_created_when_missing(tmp_path, monkeypatch):
    """With nothing from the scans at all, the gate still writes its detail and blocks."""
    out = tmp_path / "not" / "there"
    monkeypatch.delenv("DAST_OPEN_FINGERPRINTS", raising=False)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "github_output"))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    gate.main(out)

    detail = json.loads((out / "gate.json").read_text())
    assert detail["blocking"] == 3
    assert {t["incomplete"] for t in detail["tools"].values()} == {"report missing"}
    assert (tmp_path / "github_output").read_text() == "blocking=3\n"


def test_incomplete_reason_is_public_and_fixed(tmp_path, monkeypatch, capsys):
    """The summary names why a scan blocked with a fixed string, and nothing from a report."""
    web = {"site": [], "note": "secret-looking-text"}
    _clean_run(tmp_path, zap_web=web)

    _run_gate(tmp_path, monkeypatch)

    printed = capsys.readouterr().out
    assert (
        "zap-web: blocking 1, warnings 0, low 0, info 0 (scan incomplete: target not reached)"
        in printed
    )
    assert "secret-looking-text" not in printed


@pytest.mark.parametrize("code", ["ST401", "ST402"])
def test_authorization_failures_block(tmp_path, monkeypatch, code):
    """Ignored authentication and broken object-level authorization block like a server error."""
    check = gate.CHECK_BY_CODE[code]
    failures = [_failure(code, "GET /api/v1/projects/{project_id}")]
    _clean_run(tmp_path, schemathesis=_schemathesis_report(failures))

    detail = _run_gate(tmp_path, monkeypatch)

    assert detail["tools"]["schemathesis"]["blocking"] == [
        f"schemathesis:{check}:GET /api/v1/projects/{{project_id}}"
    ]
    assert detail["blocking"] == 1


def test_errored_schemathesis_operations_are_warnings(tmp_path, monkeypatch):
    """Operations Schemathesis could not test are counted and recorded, and do not block."""
    report = _schemathesis_report(
        [], operations={"tested": 20, "errored": 3}, errors=[{"title": "Connection", "count": 3}]
    )
    _clean_run(tmp_path, schemathesis=report, rcs=(1, 0, 0))

    detail = _run_gate(tmp_path, monkeypatch)

    tool = detail["tools"]["schemathesis"]
    assert detail["blocking"] == 0
    assert tool["errored"] == 3
    assert tool["counts"] == {"blocking": 0, "warnings": 3}


def test_errors_list_alone_is_a_warning(tmp_path, monkeypatch):
    """A report with an errors entry and no operation counted still records the error."""
    report = _schemathesis_report([], errors=[{"title": "Timeout", "count": 1}])
    _clean_run(tmp_path, schemathesis=report, rcs=(1, 0, 0))

    detail = _run_gate(tmp_path, monkeypatch)

    assert detail["tools"]["schemathesis"]["counts"] == {"blocking": 0, "warnings": 1}
    assert detail["blocking"] == 0


def test_more_than_one_schemathesis_report_is_incomplete(tmp_path, monkeypatch):
    """One run writes one report, so a second file means the exit code cannot be tied to one."""
    _clean_run(tmp_path)
    second = tmp_path / "schemathesis" / "json-20261125T010000Z.json"
    second.write_text(json.dumps(_schemathesis_report([])))

    detail = _run_gate(tmp_path, monkeypatch)

    assert detail["tools"]["schemathesis"]["incomplete"] == "more than one report"
    assert detail["blocking"] == 1
