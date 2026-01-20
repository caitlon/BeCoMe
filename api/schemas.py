"""Pydantic schemas for API request/response validation."""

import math
from typing import Self

from pydantic import BaseModel, Field, model_validator

from src.models.fuzzy_number import FuzzyTriangleNumber


class ExpertInput(BaseModel):
    """Single expert opinion input."""

    name: str = Field(..., min_length=1, description="Expert name or identifier")
    lower: float = Field(..., description="Lower bound (pessimistic estimate)")
    peak: float = Field(..., description="Peak value (most likely)")
    upper: float = Field(..., description="Upper bound (optimistic estimate)")

    @model_validator(mode="after")
    def validate_fuzzy_constraints(self) -> Self:
        """Validate: finite values and lower <= peak <= upper."""
        values = [self.lower, self.peak, self.upper]
        if not all(math.isfinite(v) for v in values):
            msg = "Values must be finite (no NaN or infinity)"
            raise ValueError(msg)
        if not (self.lower <= self.peak <= self.upper):
            msg = f"Must satisfy: lower <= peak <= upper. Got: {self.lower}, {self.peak}, {self.upper}"
            raise ValueError(msg)
        return self


class CalculateRequest(BaseModel):
    """Request body for calculation endpoint."""

    experts: list[ExpertInput] = Field(..., min_length=1, description="List of expert opinions")


class FuzzyNumberOutput(BaseModel):
    """Fuzzy triangular number in response."""

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


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    version: str
