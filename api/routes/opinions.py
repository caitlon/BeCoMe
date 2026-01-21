"""Expert opinion management routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth.dependencies import CurrentUser
from api.dependencies import (
    ProjectMember,
    get_calculation_service,
    get_opinion_service,
)
from api.exceptions import OpinionNotFoundError
from api.schemas import (
    CalculationResultResponse,
    FuzzyNumberOutput,
    OpinionCreate,
    OpinionResponse,
)
from api.services.calculation_service import CalculationService
from api.services.opinion_service import OpinionService, ValuesOutOfRangeError

router = APIRouter(prefix="/api/v1/projects", tags=["opinions"])


@router.get(
    "/{project_id}/opinions",
    response_model=list[OpinionResponse],
    summary="List project opinions",
)
def list_opinions(
    project: ProjectMember,
    opinion_service: Annotated[OpinionService, Depends(get_opinion_service)],
) -> list[OpinionResponse]:
    """Get all opinions for a project. Only members can access.

    :param project: Project (verified membership)
    :param opinion_service: Opinion service
    :return: List of opinions with user details
    """
    opinions = opinion_service.get_opinions_for_project(project.id)
    return [OpinionResponse.from_model(opinion, user) for opinion, user in opinions]


@router.post(
    "/{project_id}/opinions",
    response_model=OpinionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit or update opinion",
)
def submit_opinion(
    project: ProjectMember,
    request: OpinionCreate,
    current_user: CurrentUser,
    opinion_service: Annotated[OpinionService, Depends(get_opinion_service)],
    calculation_service: Annotated[CalculationService, Depends(get_calculation_service)],
) -> OpinionResponse:
    """Submit or update own opinion for a project.

    If opinion already exists, it will be updated. Auto-triggers recalculation.

    :param project: Project (verified membership)
    :param request: Opinion data
    :param current_user: Authenticated user
    :param opinion_service: Opinion service
    :param calculation_service: Calculation service
    :return: Created or updated opinion
    """
    try:
        opinion_service.validate_values_in_range(
            project, request.lower_bound, request.peak, request.upper_bound
        )
    except ValuesOutOfRangeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    opinion, _is_new = opinion_service.upsert_opinion(
        project_id=project.id,
        user_id=current_user.id,
        position=request.position,
        lower_bound=request.lower_bound,
        peak=request.peak,
        upper_bound=request.upper_bound,
    )

    calculation_service.recalculate(project.id)

    return OpinionResponse.from_model(opinion, current_user)


@router.delete(
    "/{project_id}/opinions",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete own opinion",
)
def delete_opinion(
    project: ProjectMember,
    current_user: CurrentUser,
    opinion_service: Annotated[OpinionService, Depends(get_opinion_service)],
    calculation_service: Annotated[CalculationService, Depends(get_calculation_service)],
) -> None:
    """Delete own opinion from a project. Auto-triggers recalculation.

    :param project: Project (verified membership)
    :param current_user: Authenticated user
    :param opinion_service: Opinion service
    :param calculation_service: Calculation service
    """
    try:
        opinion_service.delete_opinion(project.id, current_user.id)
    except OpinionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You have not submitted an opinion for this project",
        ) from e

    calculation_service.recalculate(project.id)


@router.get(
    "/{project_id}/result",
    response_model=CalculationResultResponse | None,
    summary="Get calculation result",
)
def get_result(
    project: ProjectMember,
    calculation_service: Annotated[CalculationService, Depends(get_calculation_service)],
) -> CalculationResultResponse | None:
    """Get BeCoMe calculation result for a project.

    Returns None if no opinions have been submitted yet.

    :param project: Project (verified membership)
    :param calculation_service: Calculation service
    :return: Calculation result or None
    """
    result = calculation_service.get_result(project.id)
    if not result:
        return None

    return CalculationResultResponse(
        best_compromise=FuzzyNumberOutput(
            lower=result.best_compromise_lower,
            peak=result.best_compromise_peak,
            upper=result.best_compromise_upper,
            centroid=(
                result.best_compromise_lower
                + result.best_compromise_peak
                + result.best_compromise_upper
            )
            / 3,
        ),
        arithmetic_mean=FuzzyNumberOutput(
            lower=result.arithmetic_mean_lower,
            peak=result.arithmetic_mean_peak,
            upper=result.arithmetic_mean_upper,
            centroid=(
                result.arithmetic_mean_lower
                + result.arithmetic_mean_peak
                + result.arithmetic_mean_upper
            )
            / 3,
        ),
        median=FuzzyNumberOutput(
            lower=result.median_lower,
            peak=result.median_peak,
            upper=result.median_upper,
            centroid=(result.median_lower + result.median_peak + result.median_upper) / 3,
        ),
        max_error=result.max_error,
        num_experts=result.num_experts,
        likert_value=result.likert_value,
        likert_decision=result.likert_decision,
        calculated_at=result.calculated_at,
    )
