"""Calculation result schemas for project-based calculations."""

from datetime import datetime

from pydantic import BaseModel

from api.schemas.calculation import FuzzyNumberOutput

# Alias for backward compatibility
FuzzyNumberResult = FuzzyNumberOutput


class CalculationResultResponse(BaseModel):
    """BeCoMe calculation result for a project."""

    best_compromise: FuzzyNumberResult
    arithmetic_mean: FuzzyNumberResult
    median: FuzzyNumberResult
    max_error: float
    num_experts: int
    likert_value: int | None
    likert_decision: str | None
    calculated_at: datetime
