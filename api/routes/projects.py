"""Project management routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from api.auth.dependencies import CurrentUser
from api.db.session import get_session
from api.exceptions import MemberNotFoundError
from api.schemas import MemberResponse, ProjectCreate, ProjectResponse, ProjectUpdate
from api.services.project_service import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _get_project_service(session: Annotated[Session, Depends(get_session)]) -> ProjectService:
    """Dependency to get ProjectService instance."""
    return ProjectService(session)


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List user's projects",
)
def list_projects(
    current_user: CurrentUser,
    service: Annotated[ProjectService, Depends(_get_project_service)],
) -> list[ProjectResponse]:
    """Get all projects where the current user is a member.

    :param current_user: Authenticated user
    :param service: Project service
    :return: List of projects with member counts
    """
    projects_with_counts = service.get_user_projects_with_counts(current_user.id)
    return [
        ProjectResponse(
            id=str(project.id),
            name=project.name,
            description=project.description,
            scale_min=project.scale_min,
            scale_max=project.scale_max,
            scale_unit=project.scale_unit,
            admin_id=str(project.admin_id),
            created_at=project.created_at,
            member_count=member_count,
        )
        for project, member_count in projects_with_counts
    ]


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
def create_project(
    request: ProjectCreate,
    current_user: CurrentUser,
    service: Annotated[ProjectService, Depends(_get_project_service)],
) -> ProjectResponse:
    """Create a new project. The creator becomes the admin.

    :param request: Project creation data
    :param current_user: Authenticated user (will be admin)
    :param service: Project service
    :return: Created project
    """
    project = service.create_project(current_user.id, request)
    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        scale_min=project.scale_min,
        scale_max=project.scale_max,
        scale_unit=project.scale_unit,
        admin_id=str(project.admin_id),
        created_at=project.created_at,
        member_count=1,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details",
)
def get_project(
    project_id: UUID,
    current_user: CurrentUser,
    service: Annotated[ProjectService, Depends(_get_project_service)],
) -> ProjectResponse:
    """Get project details. Only members can access.

    :param project_id: Project UUID
    :param current_user: Authenticated user
    :param service: Project service
    :return: Project details
    :raises HTTPException: 404 if not found, 403 if not a member
    """
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not service.is_member(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this project",
        )

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        scale_min=project.scale_min,
        scale_max=project.scale_max,
        scale_unit=project.scale_unit,
        admin_id=str(project.admin_id),
        created_at=project.created_at,
        member_count=service.get_member_count(project_id),
    )


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project",
)
def update_project(
    project_id: UUID,
    request: ProjectUpdate,
    current_user: CurrentUser,
    service: Annotated[ProjectService, Depends(_get_project_service)],
) -> ProjectResponse:
    """Update project. Only admin can update.

    :param project_id: Project UUID
    :param request: Fields to update
    :param current_user: Authenticated user
    :param service: Project service
    :return: Updated project
    :raises HTTPException: 404 if not found, 403 if not admin
    """
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not service.is_admin(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project admin can update",
        )

    try:
        project = service.update_project(project_id, request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        scale_min=project.scale_min,
        scale_max=project.scale_max,
        scale_unit=project.scale_unit,
        admin_id=str(project.admin_id),
        created_at=project.created_at,
        member_count=service.get_member_count(project_id),
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
)
def delete_project(
    project_id: UUID,
    current_user: CurrentUser,
    service: Annotated[ProjectService, Depends(_get_project_service)],
) -> None:
    """Delete project and all related data. Only admin can delete.

    :param project_id: Project UUID
    :param current_user: Authenticated user
    :param service: Project service
    :raises HTTPException: 404 if not found, 403 if not admin
    """
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not service.is_admin(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project admin can delete",
        )

    service.delete_project(project_id)


@router.get(
    "/{project_id}/members",
    response_model=list[MemberResponse],
    summary="List project members",
)
def list_members(
    project_id: UUID,
    current_user: CurrentUser,
    service: Annotated[ProjectService, Depends(_get_project_service)],
) -> list[MemberResponse]:
    """List all members of a project. Only members can access.

    :param project_id: Project UUID
    :param current_user: Authenticated user
    :param service: Project service
    :return: List of members with their roles
    :raises HTTPException: 404 if not found, 403 if not a member
    """
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not service.is_member(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this project",
        )

    members = service.get_members(project_id)
    return [
        MemberResponse(
            user_id=str(membership.user_id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=membership.role.value,
            joined_at=membership.joined_at,
        )
        for membership, user in members
    ]


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member from project",
)
def remove_member(
    project_id: UUID,
    user_id: UUID,
    current_user: CurrentUser,
    service: Annotated[ProjectService, Depends(_get_project_service)],
) -> None:
    """Remove a member from project. Only admin can remove members.

    Admin cannot remove themselves (use delete project instead).

    :param project_id: Project UUID
    :param user_id: User UUID to remove
    :param current_user: Authenticated user
    :param service: Project service
    :raises HTTPException: 404 if not found, 403 if not admin, 400 if removing self
    """
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not service.is_admin(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project admin can remove members",
        )

    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot remove themselves. Delete the project instead.",
        )

    try:
        service.remove_member(project_id, user_id)
    except MemberNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this project",
        ) from e
