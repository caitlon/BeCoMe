"""Unit tests for the E2E report check: skips, failures and a short run all fail the shard."""

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[4]


def _load():
    """Import the script by path, since `scripts/` is not a package."""
    spec = importlib.util.spec_from_file_location(
        "check_e2e_report", ROOT / "scripts" / "ci" / "check_e2e_report.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_e2e_report"] = module
    spec.loader.exec_module(module)
    return module


check = _load()


def _report(
    passed: int = 0, skipped: int = 0, unexpected: int = 0, flaky: int = 0
) -> dict[str, Any]:
    """Build a Playwright JSON report with the given test outcomes, nested like a real one."""
    statuses = (["expected"] * passed + ["skipped"] * skipped + ["unexpected"] * unexpected) + [
        "flaky"
    ] * flaky
    specs = [
        {
            "title": f"test {index}",
            "file": "assistant-panel.spec.ts",
            "tests": [{"status": status, "projectName": "chromium"}],
        }
        for index, status in enumerate(statuses)
    ]
    return {
        "suites": [
            {"title": "assistant-panel.spec.ts", "suites": [{"title": "panel", "specs": specs}]}
        ],
        "stats": {
            "expected": passed,
            "skipped": skipped,
            "unexpected": unexpected,
            "flaky": flaky,
        },
    }


def _write(tmp_path: Path, report: object) -> Path:
    """Write a report as JSON under ``tmp_path`` and return its path."""
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def _run(
    path: Path, capsys: pytest.CaptureFixture[str], min_tests: int = 15
) -> tuple[int, str, str]:
    """Run ``main`` on a report and return the status with captured stdout and stderr."""
    status = check.main(["--min-tests", str(min_tests), str(path)])
    captured = capsys.readouterr()
    return status, captured.out, captured.err


def test_all_tests_passed_succeeds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """GIVEN a report of 15 passed tests WHEN checked THEN it exits 0 with a summary line."""
    status, out, err = _run(_write(tmp_path, _report(passed=15)), capsys)

    assert status == 0
    assert out.strip() == "E2E report: 15 ran (15 passed, 0 flaky), 0 skipped"
    assert err == ""


def test_all_tests_skipped_fails_and_lists_titles(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """GIVEN every test skipped (the flag never arrived) WHEN checked THEN it fails and names them."""
    status, out, err = _run(_write(tmp_path, _report(skipped=15)), capsys)

    assert status == 1
    assert out == ""
    assert "15 test(s) skipped" in err
    assert "skipped: assistant-panel.spec.ts: test 0" in err
    assert "only 0 test(s) ran, at least 15 expected" in err


def test_one_skipped_among_fifteen_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """GIVEN 14 passed and 1 skipped WHEN checked THEN it fails on the skip."""
    status, _, err = _run(_write(tmp_path, _report(passed=14, skipped=1)), capsys)

    assert status == 1
    assert "1 test(s) skipped" in err
    assert "skipped: assistant-panel.spec.ts: test 14" in err


def test_fewer_tests_than_floor_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """GIVEN 14 passed tests and a floor of 15 WHEN checked THEN it fails on the count."""
    status, _, err = _run(_write(tmp_path, _report(passed=14)), capsys)

    assert status == 1
    assert "only 14 test(s) ran, at least 15 expected" in err


def test_flaky_tests_count_as_ran(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """GIVEN 13 passed and 2 flaky tests WHEN checked THEN they count toward the floor."""
    status, out, _ = _run(_write(tmp_path, _report(passed=13, flaky=2)), capsys)

    assert status == 0
    assert "15 ran (13 passed, 2 flaky), 0 skipped" in out


def test_unexpected_failure_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """GIVEN a failed test among enough passed ones WHEN checked THEN it fails on the failure."""
    status, _, err = _run(_write(tmp_path, _report(passed=15, unexpected=1)), capsys)

    assert status == 1
    assert "1 test(s) failed unexpectedly" in err


def test_errors_outside_the_tests_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """GIVEN 15 passed but one error outside the tests WHEN checked THEN it fails and names it."""
    report = _report(passed=15)
    report["errors"] = [{"message": "global setup failed\n    at setup.ts:1"}]

    status, out, err = _run(_write(tmp_path, report), capsys)

    assert status == 1
    assert out == ""
    assert "1 error(s) outside the tests" in err
    assert "  error: global setup failed" in err
    assert "setup.ts" not in err


def test_empty_errors_list_succeeds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """GIVEN 15 passed and an empty errors list WHEN checked THEN it exits 0."""
    report = _report(passed=15)
    report["errors"] = []

    status, _, err = _run(_write(tmp_path, report), capsys)

    assert status == 0
    assert err == ""


def test_errors_that_is_not_a_list_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """GIVEN `errors` given as a string WHEN checked THEN it fails as an unusable report."""
    report = _report(passed=15)
    report["errors"] = "boom"

    status, _, err = _run(_write(tmp_path, report), capsys)

    assert status == 1
    assert "no usable Playwright report" in err
    assert "`errors` is not a list" in err


def test_error_without_message_lists_a_placeholder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """GIVEN an error entry with no message WHEN checked THEN it is listed as `?`."""
    report = _report(passed=15)
    report["errors"] = [{"stack": "x"}]

    status, _, err = _run(_write(tmp_path, report), capsys)

    assert status == 1
    assert "  error: ?" in err


def test_missing_report_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """GIVEN no report file WHEN checked THEN it fails and points at the reporter setting."""
    status, out, err = _run(tmp_path / "absent.json", capsys)

    assert status == 1
    assert out == ""
    assert "no usable Playwright report" in err
    assert "PLAYWRIGHT_JSON_OUTPUT_FILE" in err


def test_invalid_json_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """GIVEN a report that is not JSON (the reporter printed elsewhere) WHEN checked THEN it fails."""
    path = tmp_path / "report.json"
    path.write_text("not json {", encoding="utf-8")

    status, _, err = _run(path, capsys)

    assert status == 1
    assert "no usable Playwright report" in err


@pytest.mark.parametrize(
    "report",
    [
        {"suites": []},
        [],
        {"stats": {"expected": 15}},
        {"stats": {"expected": "15", "skipped": 0, "unexpected": 0, "flaky": 0}},
        {"stats": {"expected": 15, "skipped": False, "unexpected": 0, "flaky": 0}},
    ],
)
def test_report_without_usable_stats_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], report: object
) -> None:
    """GIVEN a report with no complete integer stats WHEN checked THEN it fails as unusable."""
    status, _, err = _run(_write(tmp_path, report), capsys)

    assert status == 1
    assert "no `stats` object with integer counts" in err


def test_long_skipped_list_is_capped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """GIVEN 12 skipped tests WHEN checked THEN only 10 titles are listed, plus a count of the rest."""
    status, _, err = _run(_write(tmp_path, _report(skipped=12)), capsys)

    assert status == 1
    assert err.count("  skipped: ") == 10
    assert "  ... and 2 more" in err


def test_long_error_list_is_capped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """GIVEN 12 top-level errors WHEN checked THEN only 10 are listed, plus a count of the rest."""
    report = _report(passed=15)
    report["errors"] = [{"message": f"boom {index}\nstack"} for index in range(12)]

    status, _, err = _run(_write(tmp_path, report), capsys)

    assert status == 1
    assert len([line for line in err.splitlines() if line.startswith("  error: ")]) == 10
    assert "  ... and 2 more" in err


def test_walk_tolerates_missing_keys(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """GIVEN skipped stats but a suite tree with missing keys WHEN checked THEN it still fails cleanly."""
    report = {
        "suites": [{"specs": [{"tests": [{"status": "skipped"}]}]}, "junk", {"suites": None}],
        "stats": {"expected": 0, "skipped": 1, "unexpected": 0, "flaky": 0},
    }

    status, _, err = _run(_write(tmp_path, report), capsys)

    assert status == 1
    assert "skipped: ?: ?" in err


@pytest.mark.parametrize("value", ["0", "-3", "many"])
def test_min_tests_must_be_a_positive_integer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str
) -> None:
    """GIVEN a --min-tests that is not a positive integer WHEN parsed THEN argparse exits 2."""
    path = _write(tmp_path, _report(passed=15))

    with pytest.raises(SystemExit) as raised:
        check.main(["--min-tests", value, str(path)])

    assert raised.value.code == 2
    assert "--min-tests" in capsys.readouterr().err
