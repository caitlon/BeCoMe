"""Centralized FastAPI dependencies for service factories and authorization."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlmodel import Session

from api.auth.dependencies import CurrentUser
from api.db.models import Project
from api.db.session import get_session
from api.services.calculation_service import CalculationService
from api.services.invitation_service import InvitationService
from api.services.opinion_service import OpinionService
from api.services.project_service import ProjectService
from api.services.user_service import UserService

# --- Service Factories ---


def get_user_service(session: Annotated[Session, Depends(get_session)]) -> UserService:
    """Create UserService instance."""
    return UserService(session)


def get_project_service(session: Annotated[Session, Depends(get_session)]) -> ProjectService:
    """Create ProjectService instance."""
    return ProjectService(session)


def get_opinion_service(session: Annotated[Session, Depends(get_session)]) -> OpinionService:
    """Create OpinionService instance."""
    return OpinionService(session)


def get_calculation_service(
    session: Annotated[Session, Depends(get_session)],
) -> CalculationService:
    """Create CalculationService instance."""
    return CalculationService(session)


def get_invitation_service(session: Annotated[Session, Depends(get_session)]) -> InvitationService:
    """Create InvitationService instance."""
    return InvitationService(session)


# --- Authorization Dependencies ---


class RequireProjectMember:
    """Dependency that verifies user is a project member and returns the project."""

    def __call__(
        self,
        project_id: UUID,
        current_user: CurrentUser,
        service: Annotated[ProjectService, Depends(get_project_service)],
    ) -> Project:
        """Verify membership and return project.

        :param project_id: Project UUID from path
        :param current_user: Authenticated user
        :param service: Project service
        :return: Project if user is member
        :raises HTTPException: 404 if not found, 403 if not member
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
        return project


class RequireProjectAdmin:
    """Dependency that verifies user is project admin and returns the project."""

    def __call__(
        self,
        project_id: UUID,
        current_user: CurrentUser,
        service: Annotated[ProjectService, Depends(get_project_service)],
    ) -> Project:
        """Verify admin rights and return project.

        :param project_id: Project UUID from path
        :param current_user: Authenticated user
        :param service: Project service
        :return: Project if user is admin
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
                detail="Only project admin can perform this action",
            )
        return project


require_project_member = RequireProjectMember()
require_project_admin = RequireProjectAdmin()

# Type aliases for cleaner route signatures
ProjectMember = Annotated[Project, Depends(require_project_member)]
ProjectAdmin = Annotated[Project, Depends(require_project_admin)]
