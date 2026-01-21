"""Calculation result schemas for project-based calculations."""

from datetime import datetime

from pydantic import BaseModel

from api.schemas.calculation import FuzzyNumberOutput


class CalculationResultResponse(BaseModel):
    """BeCoMe calculation result for a project."""

    best_compromise: FuzzyNumberOutput
    arithmetic_mean: FuzzyNumberOutput
    median: FuzzyNumberOutput
    max_error: float
    num_experts: int
    likert_value: int | None
    likert_decision: str | None
    calculated_at: datetime
