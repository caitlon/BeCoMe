"""BeCoMe calculation schemas."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

from api.schemas.validators import validate_fuzzy_constraints
from src.models.fuzzy_number import FuzzyTriangleNumber


class ExpertInput(BaseModel):
    """Single expert opinion input."""

    name: str = Field(..., min_length=1, description="Expert name or identifier")
    lower: float = Field(..., description="Lower bound (pessimistic estimate)")
    peak: float = Field(..., description="Peak value (most likely)")
    upper: float = Field(..., description="Upper bound (optimistic estimate)")

    @model_validator(mode="after")
    def validate_fuzzy(self) -> Self:
        """Validate fuzzy number constraints."""
        validate_fuzzy_constraints(self.lower, self.peak, self.upper)
        return self


class CalculateRequest(BaseModel):
    """Request body for calculation endpoint."""

    experts: list[ExpertInput] = Field(..., min_length=1, description="List of expert opinions")


class FuzzyNumberOutput(BaseModel):
    """Fuzzy triangular number in response.

    Used for both stateless calculation endpoint and project results.
    """

    lower: float
    peak: float
    upper: float
    centroid: float

    @classmethod
    def from_domain(cls, fuzzy: FuzzyTriangleNumber) -> "FuzzyNumberOutput":
        """Create from domain FuzzyTriangleNumber."""
        return cls(
            lower=fuzzy.lower_bound,
            peak=fuzzy.peak,
            upper=fuzzy.upper_bound,
            centroid=fuzzy.centroid,
        )


class CalculateResponse(BaseModel):
    """Response from calculation endpoint."""

    best_compromise: FuzzyNumberOutput
    arithmetic_mean: FuzzyNumberOutput
    median: FuzzyNumberOutput
    max_error: float
    num_experts: int


class CalculationResultResponse(CalculateResponse):
    """BeCoMe calculation result for a project.

    Extends CalculateResponse with Likert interpretation and timestamp.
    """

    likert_value: int | None = Field(None, ge=0, le=100)
    likert_decision: str | None = None
    calculated_at: datetime
