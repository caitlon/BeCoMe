"""Project management routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth.dependencies import CurrentUser
from api.dependencies import (
    ProjectAdmin,
    ProjectMember,
    get_project_service,
)
from api.exceptions import MemberNotFoundError
from api.schemas import MemberResponse, ProjectCreate, ProjectResponse, ProjectUpdate
from api.services.project_service import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List user's projects",
)
def list_projects(
    current_user: CurrentUser,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> list[ProjectResponse]:
    """Get all projects where the current user is a member.

    :param current_user: Authenticated user
    :param service: Project service
    :return: List of projects with member counts
    """
    projects_with_counts = service.get_user_projects_with_counts(current_user.id)
    return [
        ProjectResponse.from_model(project, member_count)
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


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details",
)
def get_project(
    project: ProjectMember,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """Get project details. Only members can access.

    :param project: Project (verified membership)
    :param service: Project service
    :return: Project details
    """
    return ProjectResponse.from_model(project, service.get_member_count(project.id))


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project",
)
def update_project(
    project: ProjectAdmin,
    request: ProjectUpdate,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """Update project. Only admin can update.

    :param project: Project (verified admin)
    :param request: Fields to update
    :param service: Project service
    :return: Updated project
    """
    try:
        updated = service.update_project(project.id, request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    return ProjectResponse.from_model(updated, service.get_member_count(project.id))


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
)
def delete_project(
    project: ProjectAdmin,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> None:
    """Delete project and all related data. Only admin can delete.

    :param project: Project (verified admin)
    :param service: Project service
    """
    service.delete_project(project.id)


@router.get(
    "/{project_id}/members",
    response_model=list[MemberResponse],
    summary="List project members",
)
def list_members(
    project: ProjectMember,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> list[MemberResponse]:
    """List all members of a project. Only members can access.

    :param project: Project (verified membership)
    :param service: Project service
    :return: List of members with their roles
    """
    members = service.get_members(project.id)
    return [MemberResponse.from_model(membership, user) for membership, user in members]


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member from project",
)
def remove_member(
    project: ProjectAdmin,
    user_id: UUID,
    current_user: CurrentUser,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> None:
    """Remove a member from project. Only admin can remove members.

    Admin cannot remove themselves (use delete project instead).

    :param project: Project (verified admin)
    :param user_id: User UUID to remove
    :param current_user: Authenticated user
    :param service: Project service
    :raises HTTPException: 400 if removing self, 404 if user not member
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot remove themselves. Delete the project instead.",
        )

    try:
        service.remove_member(project.id, user_id)
    except MemberNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this project",
        ) from e
