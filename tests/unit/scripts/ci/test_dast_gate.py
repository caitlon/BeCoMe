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


def _alert(plugin: str, risk: int, uri: str, method: str = "GET") -> dict[str, Any]:
    """Build one ZAP alert with one instance; the risk code is a string, as in the report."""
    return {
        "pluginid": plugin,
        "riskcode": str(risk),
        "instances": [{"uri": uri, "method": method}],
    }


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
    alert = _alert("10055", 2, "http://127.0.0.1:8081/")
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
    assert "no readable report" in {t["incomplete"] for t in detail["tools"].values()}


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"rcs": (2, 0, 0)}, "exit code outside 0 and 1"),
        ({"rcs": (0, 3, 0)}, "exit code outside 0 to 2"),
        ({"zap_web": {"site": []}}, "target not reached"),
        (
            {"schemathesis": _schemathesis_report([], stop_reason="server_unavailable")},
            "run stopped early",
        ),
        ({"schemathesis": _schemathesis_report([], complete=False)}, "run stopped early"),
        (
            {"schemathesis": _schemathesis_report([], operations={"tested": 0})},
            "no operation was tested",
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
