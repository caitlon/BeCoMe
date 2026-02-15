"""BeCoMe calculation endpoint.

This module provides direct calculation endpoint without project context.
Uses dependency injection for calculator following DIP.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_calculator
from api.schemas.calculation import CalculateRequest, CalculateResponse, FuzzyNumberOutput
from src.calculators.become_calculator import BeCoMeCalculator
from src.exceptions import BeCoMeError
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

router = APIRouter(prefix="/api/v1", tags=["calculation"])


@router.post(
    "/calculate",
    responses={400: {"description": "Invalid input or calculation error"}},
)
def calculate(
    request: CalculateRequest,
    calculator: Annotated[BeCoMeCalculator, Depends(get_calculator)],
) -> CalculateResponse:
    """Calculate BeCoMe result from expert opinions.

    :param request: Expert opinions to aggregate
    :param calculator: Injected BeCoMeCalculator instance
    :return: Calculation result with fuzzy numbers
    """
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

    try:
        result = calculator.calculate_compromise(opinions)
    except BeCoMeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return CalculateResponse(
        best_compromise=FuzzyNumberOutput.from_domain(result.best_compromise),
        arithmetic_mean=FuzzyNumberOutput.from_domain(result.arithmetic_mean),
        median=FuzzyNumberOutput.from_domain(result.median),
        max_error=result.max_error,
        num_experts=result.num_experts,
    )
