"""BeCoMe calculation endpoint."""

from fastapi import APIRouter, HTTPException

from api.schemas import (
    CalculateRequest,
    CalculateResponse,
    FuzzyNumberOutput,
)
from src.calculators.become_calculator import BeCoMeCalculator
from src.exceptions import BeCoMeError
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

router = APIRouter(prefix="/api/v1", tags=["calculation"])


@router.post("/calculate", response_model=CalculateResponse)
def calculate(request: CalculateRequest) -> CalculateResponse:
    """Calculate BeCoMe result from expert opinions."""
    calculator = BeCoMeCalculator()

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
        result = calculator.calculate_compromise(opinions)
    except BeCoMeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Convert to response
    return CalculateResponse(
        best_compromise=FuzzyNumberOutput.from_domain(result.best_compromise),
        arithmetic_mean=FuzzyNumberOutput.from_domain(result.arithmetic_mean),
        median=FuzzyNumberOutput.from_domain(result.median),
        max_error=result.max_error,
        num_experts=result.num_experts,
    )
