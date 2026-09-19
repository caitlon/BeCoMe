"""Allowlisted view models: exactly the fields the assistant may see.

Each view lists the fields it accepts; extra="ignore" drops everything else the
real API response carries. That is what keeps user_email and user_id out of the
model's reach without a hand-maintained blocklist, and it drops any field a
response gains later, such as a photo_url, the same way.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class FuzzyView(BaseModel):
    """One fuzzy triangular number: lower, peak, upper bound and centroid."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    lower: float
    peak: float
    upper: float
    centroid: float


class ProjectBrief(BaseModel):
    """One row of the caller's project list."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str
    name: str
    role: str
    is_example: bool


class ProjectView(BaseModel):
    """A single project's details, as the caller is allowed to see them."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str
    name: str
    description: str | None
    scale_min: float
    scale_max: float
    scale_unit: str
    role: str


class ResultView(BaseModel):
    """A project's BeCoMe calculation result."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    best_compromise: FuzzyView
    arithmetic_mean: FuzzyView
    median: FuzzyView
    max_error: float
    num_experts: int
    agreement_level: str
    likert_value: int | None
    likert_decision: str | None
    calculated_at: datetime


class OpinionView(BaseModel):
    """One expert's opinion, with the expert named but never identified."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    expert_name: str
    position: str
    lower_bound: float
    peak: float
    upper_bound: float
    centroid: float

    @model_validator(mode="before")
    @classmethod
    def _build_expert_name(cls, data: Any) -> Any:
        """Fold user_first_name/user_last_name into expert_name.

        Runs before the allowlist drops them: user_first_name and user_last_name
        never appear as fields on this model, so without this there would be
        nothing left to combine into expert_name.

        :param data: Raw OpinionResponse-shaped payload from the underlying API.
        :return: The payload with expert_name added, unchanged otherwise.
        """
        if isinstance(data, dict) and "expert_name" not in data:
            first = data.get("user_first_name", "")
            last = data.get("user_last_name") or ""
            data = {**data, "expert_name": f"{first} {last}".strip()}
        return data
