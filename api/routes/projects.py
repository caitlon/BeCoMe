"""Project management routes.

Exception handling follows OCP: all exceptions are handled
by centralized middleware, routes focus on business logic only.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth.dependencies import CurrentUser
from api.dependencies import (
    ProjectAdmin,
    ProjectMember,
    get_project_service,
)
from api.schemas import (
    MemberResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ProjectWithRoleResponse,
)
from api.services.project_service import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get(
    "",
    response_model=list[ProjectWithRoleResponse],
    summary="List user's projects",
)
def list_projects(
    current_user: CurrentUser,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> list[ProjectWithRoleResponse]:
    """Get all projects where the current user is a member.

    :param current_user: Authenticated user
    :param service: Project service
    :return: List of projects with member counts and user's role
    """
    projects_with_roles = service.get_user_projects_with_roles(current_user.id)
    return [
        ProjectWithRoleResponse.from_model_with_role(
            item.project, item.member_count, item.role.value
        )
        for item in projects_with_roles
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
    response_model=ProjectWithRoleResponse,
    summary="Get project details",
)
def get_project(
    project: ProjectMember,
    current_user: CurrentUser,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectWithRoleResponse:
    """Get project details. Only members can access.

    :param project: Project (verified membership)
    :param current_user: Authenticated user
    :param service: Project service
    :return: Project details with user's role
    """
    role = service.get_user_role_in_project(project.id, current_user.id)
    return ProjectWithRoleResponse.from_model_with_role(
        project,
        service.get_member_count(project.id),
        role.value if role else "expert",
    )


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
    return [MemberResponse.from_model(member.membership, member.user) for member in members]


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
    MemberNotFoundError is handled by centralized exception middleware.

    :param project: Project (verified admin)
    :param user_id: User UUID to remove
    :param current_user: Authenticated user
    :param service: Project service
    :raises HTTPException: 400 if removing self
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot remove themselves. Delete the project instead.",
        )

    service.remove_member(project.id, user_id)
