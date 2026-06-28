"""Expert opinion management routes.

Exception handling follows OCP: all exceptions are handled
by centralized middleware, routes focus on business logic only.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from api.auth.dependencies import CurrentUser
from api.dependencies import (
    ProjectMember,
    get_calculation_service,
    get_opinion_service,
    get_result_export_service,
)
from api.middleware.rate_limit import LIMIT_STANDARD, limiter
from api.schemas.calculation import CalculationResultResponse, FuzzyNumberOutput
from api.schemas.opinion import OpinionCreate, OpinionResponse
from api.services.calculation_service import CalculationService
from api.services.export.data import ExportFormat, ReportLang
from api.services.export.result_export_service import ResultExportService
from api.services.opinion_service import OpinionService

router = APIRouter(prefix="/api/v1/projects", tags=["opinions"])


@router.get("/{project_id}/opinions", summary="List project opinions")
def list_opinions(
    project_id: UUID,
    project: ProjectMember,
    opinion_service: Annotated[OpinionService, Depends(get_opinion_service)],
) -> list[OpinionResponse]:
    """Get all opinions for a project. Only members can access.

    :param project: Project (verified membership)
    :param opinion_service: Opinion service
    :return: List of opinions with user details
    """
    opinions = opinion_service.get_opinions_for_project(project.id)
    return [OpinionResponse.from_model(item.opinion, item.user) for item in opinions]


@router.post(
    "/{project_id}/opinions",
    status_code=status.HTTP_201_CREATED,
    summary="Submit or update opinion",
)
def submit_opinion(
    project_id: UUID,
    project: ProjectMember,
    request: OpinionCreate,
    current_user: CurrentUser,
    opinion_service: Annotated[OpinionService, Depends(get_opinion_service)],
    calculation_service: Annotated[CalculationService, Depends(get_calculation_service)],
) -> OpinionResponse:
    """Submit or update own opinion for a project.

    If opinion already exists, it will be updated. Auto-triggers recalculation.
    ValuesOutOfRangeError is handled by centralized exception middleware.

    :param project: Project (verified membership)
    :param request: Opinion data
    :param current_user: Authenticated user
    :param opinion_service: Opinion service
    :param calculation_service: Calculation service
    :return: Created or updated opinion
    """
    opinion_service.validate_values_in_range(
        project, request.lower_bound, request.peak, request.upper_bound
    )

    result = opinion_service.upsert_opinion(
        project_id=project.id,
        user_id=current_user.id,
        position=request.position,
        lower_bound=request.lower_bound,
        peak=request.peak,
        upper_bound=request.upper_bound,
    )

    calculation_service.recalculate(project.id)

    return OpinionResponse.from_model(result.opinion, current_user)


@router.delete(
    "/{project_id}/opinions",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete own opinion",
)
def delete_opinion(
    project_id: UUID,
    project: ProjectMember,
    current_user: CurrentUser,
    opinion_service: Annotated[OpinionService, Depends(get_opinion_service)],
    calculation_service: Annotated[CalculationService, Depends(get_calculation_service)],
) -> None:
    """Delete own opinion from a project. Auto-triggers recalculation.

    OpinionNotFoundError is handled by centralized exception middleware.

    :param project: Project (verified membership)
    :param current_user: Authenticated user
    :param opinion_service: Opinion service
    :param calculation_service: Calculation service
    """
    opinion_service.delete_opinion(project.id, current_user.id)
    calculation_service.recalculate(project.id)


@router.get("/{project_id}/result", summary="Get calculation result")
def get_result(
    project_id: UUID,
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
        best_compromise=FuzzyNumberOutput.from_bounds(
            result.best_compromise_lower,
            result.best_compromise_peak,
            result.best_compromise_upper,
        ),
        arithmetic_mean=FuzzyNumberOutput.from_bounds(
            result.arithmetic_mean_lower,
            result.arithmetic_mean_peak,
            result.arithmetic_mean_upper,
        ),
        median=FuzzyNumberOutput.from_bounds(
            result.median_lower,
            result.median_peak,
            result.median_upper,
        ),
        max_error=result.max_error,
        num_experts=result.num_experts,
        likert_value=result.likert_value,
        likert_decision=result.likert_decision,
        calculated_at=result.calculated_at,
    )


@router.get(
    "/{project_id}/result/export",
    summary="Export calculation result as PDF or CSV",
)
@limiter.limit(LIMIT_STANDARD)
def export_result(
    request: Request,
    project_id: UUID,
    project: ProjectMember,
    service: Annotated[ResultExportService, Depends(get_result_export_service)],
    export_format: Annotated[ExportFormat, Query(alias="format", description="File format")],
    lang: Annotated[ReportLang, Query(description="Report language")] = ReportLang.EN,
) -> Response:
    """Export a project's BeCoMe result as a downloadable PDF or CSV file.

    Members only, with the same tenant-isolation guard as the result endpoint.
    Returns 404 when the project has no calculated result yet.

    :param request: FastAPI request (for rate limiting).
    :param project_id: Project UUID from the path.
    :param project: Project (verified membership).
    :param service: Result export service.
    :param export_format: Requested file format (the ``format`` query parameter).
    :param lang: Report language (defaults to English).
    :return: The rendered file as an attachment download.
    """
    exported = service.export(project, export_format, lang)
    if exported is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No calculation result to export",
        )
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'},
    )
