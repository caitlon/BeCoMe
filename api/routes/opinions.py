"""Expert opinion management routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from api.auth.dependencies import CurrentUser
from api.dependencies import get_session
from api.schemas import (
    CalculationResultResponse,
    FuzzyNumberResult,
    OpinionCreate,
    OpinionResponse,
)
from api.services.calculation_service import CalculationService
from api.services.opinion_service import OpinionNotFoundError, OpinionService
from api.services.project_service import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["opinions"])


def _get_opinion_service(session: Annotated[Session, Depends(get_session)]) -> OpinionService:
    """Dependency to get OpinionService instance."""
    return OpinionService(session)


def _get_calculation_service(
    session: Annotated[Session, Depends(get_session)],
) -> CalculationService:
    """Dependency to get CalculationService instance."""
    return CalculationService(session)


def _get_project_service(session: Annotated[Session, Depends(get_session)]) -> ProjectService:
    """Dependency to get ProjectService instance."""
    return ProjectService(session)


def _check_membership(
    project_id: UUID,
    current_user: CurrentUser,
    project_service: ProjectService,
) -> None:
    """Verify user is member of project. Raises HTTPException if not."""
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not project_service.is_member(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this project",
        )


@router.get(
    "/{project_id}/opinions",
    response_model=list[OpinionResponse],
    summary="List project opinions",
)
def list_opinions(
    project_id: UUID,
    current_user: CurrentUser,
    opinion_service: Annotated[OpinionService, Depends(_get_opinion_service)],
    project_service: Annotated[ProjectService, Depends(_get_project_service)],
) -> list[OpinionResponse]:
    """Get all opinions for a project. Only members can access.

    :param project_id: Project UUID
    :param current_user: Authenticated user
    :param opinion_service: Opinion service
    :param project_service: Project service
    :return: List of opinions with user details
    """
    _check_membership(project_id, current_user, project_service)

    opinions = opinion_service.get_opinions_for_project(project_id)
    return [
        OpinionResponse(
            id=str(opinion.id),
            user_id=str(opinion.user_id),
            user_email=user.email,
            user_first_name=user.first_name,
            user_last_name=user.last_name,
            position=opinion.position,
            lower_bound=opinion.lower_bound,
            peak=opinion.peak,
            upper_bound=opinion.upper_bound,
            centroid=(opinion.lower_bound + opinion.peak + opinion.upper_bound) / 3,
            created_at=opinion.created_at,
            updated_at=opinion.updated_at,
        )
        for opinion, user in opinions
    ]


@router.post(
    "/{project_id}/opinions",
    response_model=OpinionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit or update opinion",
)
def submit_opinion(
    project_id: UUID,
    request: OpinionCreate,
    current_user: CurrentUser,
    opinion_service: Annotated[OpinionService, Depends(_get_opinion_service)],
    calculation_service: Annotated[CalculationService, Depends(_get_calculation_service)],
    project_service: Annotated[ProjectService, Depends(_get_project_service)],
) -> OpinionResponse:
    """Submit or update own opinion for a project.

    If opinion already exists, it will be updated. Auto-triggers recalculation.

    :param project_id: Project UUID
    :param request: Opinion data
    :param current_user: Authenticated user
    :param opinion_service: Opinion service
    :param calculation_service: Calculation service
    :param project_service: Project service
    :return: Created or updated opinion
    """
    _check_membership(project_id, current_user, project_service)

    project = project_service.get_project(project_id)
    assert project is not None  # _check_membership ensures project exists
    if request.lower_bound < project.scale_min or request.upper_bound > project.scale_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Values must be within project scale [{project.scale_min}, {project.scale_max}]",
        )

    opinion, _is_new = opinion_service.upsert_opinion(
        project_id=project_id,
        user_id=current_user.id,
        position=request.position,
        lower_bound=request.lower_bound,
        peak=request.peak,
        upper_bound=request.upper_bound,
    )

    calculation_service.recalculate(project_id)

    return OpinionResponse(
        id=str(opinion.id),
        user_id=str(opinion.user_id),
        user_email=current_user.email,
        user_first_name=current_user.first_name,
        user_last_name=current_user.last_name,
        position=opinion.position,
        lower_bound=opinion.lower_bound,
        peak=opinion.peak,
        upper_bound=opinion.upper_bound,
        centroid=(opinion.lower_bound + opinion.peak + opinion.upper_bound) / 3,
        created_at=opinion.created_at,
        updated_at=opinion.updated_at,
    )


@router.delete(
    "/{project_id}/opinions",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete own opinion",
)
def delete_opinion(
    project_id: UUID,
    current_user: CurrentUser,
    opinion_service: Annotated[OpinionService, Depends(_get_opinion_service)],
    calculation_service: Annotated[CalculationService, Depends(_get_calculation_service)],
    project_service: Annotated[ProjectService, Depends(_get_project_service)],
) -> None:
    """Delete own opinion from a project. Auto-triggers recalculation.

    :param project_id: Project UUID
    :param current_user: Authenticated user
    :param opinion_service: Opinion service
    :param calculation_service: Calculation service
    :param project_service: Project service
    """
    _check_membership(project_id, current_user, project_service)

    try:
        opinion_service.delete_opinion(project_id, current_user.id)
    except OpinionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You have not submitted an opinion for this project",
        ) from e

    calculation_service.recalculate(project_id)


@router.get(
    "/{project_id}/result",
    response_model=CalculationResultResponse | None,
    summary="Get calculation result",
)
def get_result(
    project_id: UUID,
    current_user: CurrentUser,
    calculation_service: Annotated[CalculationService, Depends(_get_calculation_service)],
    project_service: Annotated[ProjectService, Depends(_get_project_service)],
) -> CalculationResultResponse | None:
    """Get BeCoMe calculation result for a project.

    Returns None if no opinions have been submitted yet.

    :param project_id: Project UUID
    :param current_user: Authenticated user
    :param calculation_service: Calculation service
    :param project_service: Project service
    :return: Calculation result or None
    """
    _check_membership(project_id, current_user, project_service)

    result = calculation_service.get_result(project_id)
    if not result:
        return None

    return CalculationResultResponse(
        best_compromise=FuzzyNumberResult(
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
        arithmetic_mean=FuzzyNumberResult(
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
        median=FuzzyNumberResult(
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
