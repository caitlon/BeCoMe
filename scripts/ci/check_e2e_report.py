#!/usr/bin/env python3
"""Fail when a Playwright run skipped or failed tests, ran too few, or reported errors.

A spec that skips itself reports success, so a shard whose specs all skip stays green. The
assistant specs do this when ``VITE_ASSISTANT_ENABLED`` does not reach the Playwright
container. This check reads the JSON report of the run and refuses a report with a skipped
test, an unexpected failure, an error outside the tests (the report's top-level ``errors``,
such as a global setup failure or a worker crash), or fewer tests than ``--min-tests``. A
missing or unreadable report fails too, so a dropped reporter setting cannot pass silently.

Usage::

    python scripts/ci/check_e2e_report.py --min-tests N REPORT.json

``REPORT.json`` is written by Playwright's ``json`` reporter to the file named by the
``PLAYWRIGHT_JSON_OUTPUT_FILE`` variable. The counts come from the report's top-level
``stats`` object. Flaky tests, which passed on a retry, count as ran.
Exit status: 0 when the run meets the floor, 1 on any problem, 2 on bad arguments.
"""

import argparse
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

MAX_LISTED = 10
COUNT_KEYS = ("expected", "skipped", "unexpected", "flaky")


def _positive_int(text: str) -> int:
    """Parse a command-line value that must be an integer of at least 1.

    :param text: The argument as typed
    :return: The parsed integer
    :raises argparse.ArgumentTypeError: When the text is not an integer or is below 1
    """
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not an integer") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return value


def _is_count(value: object) -> bool:
    """Tell whether a report value is a plain integer count, booleans excluded."""
    return isinstance(value, int) and not isinstance(value, bool)


def _first_line(error: object) -> str:
    """Return the first line of a report error's ``message``, or ``?`` when it has none."""
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str) or not message.strip():
        return "?"
    return message.strip().splitlines()[0]


def _skipped_tests(suites: object) -> Iterator[str]:
    """Walk the suites of a report and yield ``file: title`` for each skipped test.

    The walk tolerates missing or wrongly typed keys, since a partial report is the case
    this check exists for.

    :param suites: The ``suites`` list of the report or of one suite
    :return: One label per skipped test, in report order
    """
    if not isinstance(suites, list):
        return
    for suite in suites:
        if not isinstance(suite, dict):
            continue
        specs = suite.get("specs")
        for spec in specs if isinstance(specs, list) else []:
            if not isinstance(spec, dict):
                continue
            tests = spec.get("tests")
            for test in tests if isinstance(tests, list) else []:
                if isinstance(test, dict) and test.get("status") == "skipped":
                    yield f"{spec.get('file', '?')}: {spec.get('title', '?')}"
        yield from _skipped_tests(suite.get("suites"))


def check_report(path: Path, min_tests: int) -> tuple[list[str], str]:
    """Check one Playwright JSON report.

    :param path: The report file
    :param min_tests: The least number of tests that must have run
    :return: The problems found (empty when the run is fine) and the one-line summary
    """
    missing = (
        f"{path}: no usable Playwright report; the json reporter or PLAYWRIGHT_JSON_OUTPUT_FILE "
        "may not have reached Playwright"
    )
    try:
        report: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"{missing} ({error})"], ""
    stats = report.get("stats") if isinstance(report, dict) else None
    if not isinstance(stats, dict) or not all(_is_count(stats.get(k)) for k in COUNT_KEYS):
        return [f"{missing} (no `stats` object with integer counts)"], ""
    errors = report.get("errors", [])
    if not isinstance(errors, list):
        return [f"{missing} (`errors` is not a list)"], ""

    expected, skipped = stats["expected"], stats["skipped"]
    unexpected, flaky = stats["unexpected"], stats["flaky"]
    ran = expected + flaky
    problems: list[str] = []
    if skipped > 0:
        problems.append(f"{skipped} test(s) skipped, none may be; the shard's flag may be unset")
        titles = list(_skipped_tests(report.get("suites")))
        problems.extend(f"  skipped: {title}" for title in titles[:MAX_LISTED])
        if len(titles) > MAX_LISTED:
            problems.append(f"  ... and {len(titles) - MAX_LISTED} more")
    if unexpected > 0:
        problems.append(f"{unexpected} test(s) failed unexpectedly")
    if errors:
        problems.append(f"{len(errors)} error(s) outside the tests")
        problems.extend(f"  error: {_first_line(error)}" for error in errors[:MAX_LISTED])
        if len(errors) > MAX_LISTED:
            problems.append(f"  ... and {len(errors) - MAX_LISTED} more")
    if ran < min_tests:
        problems.append(f"only {ran} test(s) ran, at least {min_tests} expected")
    summary = f"E2E report: {ran} ran ({expected} passed, {flaky} flaky), {skipped} skipped"
    return problems, summary


def main(argv: list[str]) -> int:
    """Run the check over one report.

    :param argv: The command-line arguments, without the program name
    :return: The exit status, 1 when the run skipped or failed tests, ran fewer than the floor,
        or reported errors outside the tests
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("report", type=Path, help="Playwright JSON report file")
    parser.add_argument(
        "--min-tests",
        type=_positive_int,
        required=True,
        help="least number of tests that must have run (flaky ones included)",
    )
    args = parser.parse_args(argv)

    problems, summary = check_report(args.report, args.min_tests)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
