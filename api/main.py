"""FastAPI application entry point."""

import math
from typing import Self

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from api.config import get_settings
from src.calculators.become_calculator import BeCoMeCalculator
from src.exceptions import BeCoMeError
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

# --- Request/Response Schemas ---


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


# --- Helper Functions ---


def fuzzy_to_output(fuzzy: FuzzyTriangleNumber) -> FuzzyNumberOutput:
    """Convert FuzzyTriangleNumber to API output format."""
    return FuzzyNumberOutput(
        lower=fuzzy.lower_bound,
        peak=fuzzy.peak,
        upper=fuzzy.upper_bound,
        centroid=fuzzy.centroid,
    )


# --- Application ---


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="BeCoMe API",
        description="Best Compromise Mean — Group Decision Making under Fuzzy Uncertainty",
        version=settings.api_version,
    )

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
    def health_check() -> HealthResponse:
        """Check API health status."""
        return HealthResponse(status="ok", version=settings.api_version)

    @app.post("/api/v1/calculate", response_model=CalculateResponse, tags=["calculation"])
    def calculate(request: CalculateRequest) -> CalculateResponse:
        """Calculate BeCoMe result from expert opinions."""
        # Convert input to domain models
        opinions = [
            ExpertOpinion(
                expert_id=expert.name,
                opinion=FuzzyTriangleNumber(
                    lower_bound=expert.lower,
                    peak=expert.peak,
                    upper_bound=expert.upper,
                ),
            )
            for expert in request.experts
        ]

        # Run calculation
        try:
            calculator = BeCoMeCalculator()
            result = calculator.calculate_compromise(opinions)
        except BeCoMeError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        # Convert to response
        return CalculateResponse(
            best_compromise=fuzzy_to_output(result.best_compromise),
            arithmetic_mean=fuzzy_to_output(result.arithmetic_mean),
            median=fuzzy_to_output(result.median),
            max_error=result.max_error,
            num_experts=result.num_experts,
        )

    return app


app = create_app()
