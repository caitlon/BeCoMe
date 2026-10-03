"""Unit test for the aggregate `check` job in the CI workflow.

The job reads the result of every job in `needs`, so a job added to the workflow and left
out of that list is not covered by the verdict, and nothing else would notice.
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="the docs extra supplies PyYAML")

ROOT = Path(__file__).resolve().parents[3]


def test_check_job_needs_every_other_job() -> None:
    """The `check` job lists exactly the other jobs of `ci.yml`."""
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    jobs = workflow["jobs"]

    assert set(jobs["check"]["needs"]) == set(jobs) - {"check"}
