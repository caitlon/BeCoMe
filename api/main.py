"""FastAPI application entry point.

Run the server::

    uv run uvicorn api.main:app --reload

API will be available at http://localhost:8000
Interactive docs at http://localhost:8000/docs
"""

from typing import Self

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from api.config import get_settings
from src.calculators.become_calculator import BeCoMeCalculator
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
        """Validate: lower <= peak <= upper."""
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
        """Check API health status.

        Example::

            curl http://localhost:8000/api/v1/health

        Response::

            {"status": "ok", "version": "1.0.0"}
        """
        return HealthResponse(status="ok", version=settings.api_version)

    @app.post("/api/v1/calculate", response_model=CalculateResponse, tags=["calculation"])
    def calculate(request: CalculateRequest) -> CalculateResponse:
        """Calculate BeCoMe result from expert opinions.

        Accepts a list of expert opinions as fuzzy triangular numbers
        and returns the best compromise along with intermediate results.

        Example::

            curl -X POST http://localhost:8000/api/v1/calculate \\
                -H "Content-Type: application/json" \\
                -d '{
                    "experts": [
                        {"name": "Expert1", "lower": 5, "peak": 10, "upper": 15},
                        {"name": "Expert2", "lower": 8, "peak": 12, "upper": 18},
                        {"name": "Expert3", "lower": 6, "peak": 11, "upper": 16}
                    ]
                }'

        Response::

            {
                "best_compromise": {"lower": 6.5, "peak": 11.0, "upper": 16.0, "centroid": 11.17},
                "arithmetic_mean": {"lower": 6.33, "peak": 11.0, "upper": 16.33, "centroid": 11.22},
                "median": {"lower": 6.0, "peak": 11.0, "upper": 16.0, "centroid": 11.0},
                "max_error": 0.22,
                "num_experts": 3
            }
        """
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
        except Exception as e:
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
