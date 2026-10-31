"""BeCoMe calculation endpoint.

This module provides direct calculation endpoint without project context. It needs a
signed-in user (session cookie or Bearer token) and counts requests per user. Uses
dependency injection for calculator following DIP.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth.dependencies import CurrentUser
from api.dependencies import get_calculator
from api.middleware.rate_limit import (
    LIMIT_STANDARD,
    bind_user_to_rate_limit,
    get_user_or_client_ip,
    limiter,
)
from api.schemas.calculation import CalculateRequest, CalculateResponse, FuzzyNumberOutput
from src.calculators.become_calculator import BeCoMeCalculator
from src.exceptions import BeCoMeError
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

logger = logging.getLogger("api.route.calculate")

router = APIRouter(prefix="/api/v1", tags=["calculation"])


def require_signed_in_user(request: Request, current_user: CurrentUser) -> None:
    """Require a signed-in caller and key the route's rate limit by their account.

    :param request: FastAPI request, which carries the user to the rate limiter
    :param current_user: The authenticated caller
    :raises HTTPException: 401 when the request has no valid session
    """
    bind_user_to_rate_limit(request, current_user.id)


@router.post(
    "/calculate",
    dependencies=[Depends(require_signed_in_user)],
    responses={400: {"description": "Invalid input or calculation error"}},
)
@limiter.limit(LIMIT_STANDARD, key_func=get_user_or_client_ip)
def calculate(
    request: Request,
    payload: CalculateRequest,
    calculator: Annotated[BeCoMeCalculator, Depends(get_calculator)],
) -> CalculateResponse:
    """Calculate BeCoMe result from expert opinions for a signed-in user.

    :param request: FastAPI request (for rate limiting)
    :param payload: Expert opinions to aggregate
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
        for expert in payload.experts
    ]

    try:
        result = calculator.calculate_compromise(opinions)
    except BeCoMeError as e:
        # The HTTPException raised here reaches FastAPI's own handler, not the app's
        # exception handlers, so this refusal would otherwise leave no trace at all.
        # Only the expert count is logged: the payload carries up to 1000 opinions.
        logger.warning(
            "Calculation rejected",
            extra={
                "event": "calculation_rejected",
                "reason": type(e).__name__,
                "expert_count": len(opinions),
            },
        )
        raise HTTPException(status_code=400, detail=str(e)) from e

    logger.debug(
        "Calculation completed",
        extra={
            "event": "calculation_completed",
            "expert_count": result.num_experts,
            "max_error": result.max_error,
        },
    )
    return CalculateResponse(
        best_compromise=FuzzyNumberOutput.from_domain(result.best_compromise),
        arithmetic_mean=FuzzyNumberOutput.from_domain(result.arithmetic_mean),
        median=FuzzyNumberOutput.from_domain(result.median),
        max_error=result.max_error,
        num_experts=result.num_experts,
    )
