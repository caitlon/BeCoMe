"""Project management routes.

Exception handling follows OCP: all exceptions are handled
by centralized middleware, routes focus on business logic only.
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth.dependencies import CurrentUser
from api.dependencies import (
    ProjectAdmin,
    ProjectMember,
    get_calculation_service,
    get_project_membership_service,
    get_project_query_service,
    get_project_service,
)
from api.pagination import PaginationParams
from api.schemas.project import (
    MemberResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ProjectWithRoleResponse,
    TransferOwnershipRequest,
)
from api.services.calculation_service import CalculationService
from api.services.project_membership_service import ProjectMembershipService
from api.services.project_query_service import ProjectQueryService
from api.services.project_service import ProjectService

# Refusals raised as HTTPException inside a route reach FastAPI's own handler, not the
# app's, so they are logged here or nowhere. Successful writes are not: project_service
# and project_membership_service already emit those events.
logger = logging.getLogger("api.route.projects")

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("", summary="List user's projects")
def list_projects(
    current_user: CurrentUser,
    query_service: Annotated[ProjectQueryService, Depends(get_project_query_service)],
    pagination: Annotated[PaginationParams, Depends()],
) -> list[ProjectWithRoleResponse]:
    """Get projects where the current user is a member.

    :param current_user: Authenticated user
    :param query_service: Project query service
    :param pagination: Bounded limit/offset (capped at MAX_PAGE_SIZE)
    :return: List of projects with member counts and user's role
    """
    projects_with_roles = query_service.get_user_projects_with_roles(
        current_user.id, limit=pagination.limit, offset=pagination.offset
    )
    logger.debug(
        "Projects listed",
        extra={
            "event": "projects_listed",
            "row_count": len(projects_with_roles),
            "limit": pagination.limit,
            "offset": pagination.offset,
        },
    )
    return [
        ProjectWithRoleResponse.from_model_with_role(
            item.project, item.member_count, item.role.value
        )
        for item in projects_with_roles
    ]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
def create_project(
    request: ProjectCreate,
    current_user: CurrentUser,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """Create a new project. The creator becomes the admin.

    :param request: Project creation data
    :param current_user: Authenticated user (will be admin)
    :param service: Project service
    :return: Created project
    """
    project = service.create_project(current_user.id, request)
    return ProjectResponse.from_model(project, member_count=1)


@router.get("/{project_id}", summary="Get project details")
def get_project(
    project_id: UUID,
    project: ProjectMember,
    current_user: CurrentUser,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    membership_service: Annotated[
        ProjectMembershipService, Depends(get_project_membership_service)
    ],
) -> ProjectWithRoleResponse:
    """Get project details. Only members can access.

    :param project: Project (verified membership)
    :param current_user: Authenticated user
    :param project_service: Project service
    :param membership_service: Membership service
    :return: Project details with user's role
    """
    role = membership_service.get_user_role_in_project(project.id, current_user.id)
    if role is None:
        # The ProjectMember dependency already accepted this caller, so a missing role
        # here means the membership went away between the two reads.
        logger.warning(
            "Project membership missing after access check",
            extra={
                "event": "project_membership_missing",
                "project_id": str(project.id),
                "user_id": str(current_user.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found for this project.",
        )
    return ProjectWithRoleResponse.from_model_with_role(
        project,
        project_service.get_member_count(project.id),
        role.value,
    )


@router.patch("/{project_id}", summary="Update project")
def update_project(
    project_id: UUID,
    project: ProjectAdmin,
    request: ProjectUpdate,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """Update project. Only admin can update.

    ScaleRangeError is handled by centralized exception middleware.

    :param project: Project (verified admin)
    :param request: Fields to update
    :param service: Project service
    :return: Updated project
    """
    updated = service.update_project(project.id, request)
    return ProjectResponse.from_model(updated, service.get_member_count(project.id))


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
)
def delete_project(
    project_id: UUID,
    project: ProjectAdmin,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> None:
    """Delete project and all related data. Only admin can delete.

    :param project: Project (verified admin)
    :param service: Project service
    """
    service.delete_project(project.id)


@router.post(
    "/{project_id}/transfer-ownership",
    summary="Transfer project ownership to another member",
)
def transfer_ownership(
    project_id: UUID,
    project: ProjectAdmin,
    request: TransferOwnershipRequest,
    current_user: CurrentUser,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """Transfer project ownership to another member. Only the current admin can do this.

    The new admin must already be a member of the project. MemberNotFoundError
    (target not a member) is handled by centralized exception middleware as 404.

    :param project: Project (verified admin)
    :param request: New admin's user ID
    :param current_user: Authenticated user (the current admin)
    :param service: Project service
    :return: Updated project
    :raises HTTPException: 400 if transferring ownership to self
    """
    if request.new_admin_id == current_user.id:
        logger.warning(
            "Ownership transfer rejected",
            extra={
                "event": "ownership_transfer_rejected",
                "reason": "self_transfer",
                "project_id": str(project.id),
                "user_id": str(current_user.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already the project admin.",
        )
    updated = service.transfer_ownership(project, request.new_admin_id)
    return ProjectResponse.from_model(updated, service.get_member_count(updated.id))


@router.get("/{project_id}/members", summary="List project members")
def list_members(
    project_id: UUID,
    project: ProjectMember,
    membership_service: Annotated[
        ProjectMembershipService, Depends(get_project_membership_service)
    ],
    pagination: Annotated[PaginationParams, Depends()],
) -> list[MemberResponse]:
    """List members of a project. Only members can access.

    :param project: Project (verified membership)
    :param membership_service: Membership service
    :param pagination: Bounded limit/offset (capped at MAX_PAGE_SIZE)
    :return: List of members with their roles
    """
    members = membership_service.get_members(
        project.id, limit=pagination.limit, offset=pagination.offset
    )
    logger.debug(
        "Project members listed",
        extra={
            "event": "members_listed",
            "project_id": str(project.id),
            "row_count": len(members),
        },
    )
    return [MemberResponse.from_model(member.membership, member.user) for member in members]


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member from project",
)
def remove_member(
    project_id: UUID,
    project: ProjectAdmin,
    user_id: UUID,
    current_user: CurrentUser,
    membership_service: Annotated[
        ProjectMembershipService, Depends(get_project_membership_service)
    ],
    calculation_service: Annotated[CalculationService, Depends(get_calculation_service)],
) -> None:
    """Remove a member from project. Only admin can remove members.

    Admin cannot remove themselves (use delete project instead). The member's opinion
    is discarded along with their membership, so the result is recalculated without it.
    MemberNotFoundError is handled by centralized exception middleware.

    :param project: Project (verified admin)
    :param user_id: User UUID to remove
    :param current_user: Authenticated user
    :param membership_service: Membership service
    :param calculation_service: Calculation service (result no longer counts the member)
    :raises HTTPException: 400 if removing self
    """
    if user_id == current_user.id:
        logger.warning(
            "Member removal rejected",
            extra={
                "event": "member_removal_rejected",
                "reason": "self_removal",
                "project_id": str(project.id),
                "user_id": str(current_user.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot remove themselves. Delete the project instead.",
        )

    if membership_service.remove_member(project.id, user_id):
        calculation_service.recalculate(project.id)
    else:
        # A 204 either way, so without this the no-op is indistinguishable from a
        # removal in the log. project_membership_service logs the removal itself.
        logger.debug(
            "Member removal was a no-op",
            extra={
                "event": "member_removal_noop",
                "project_id": str(project.id),
                "user_id": str(user_id),
            },
        )
