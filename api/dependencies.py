"""Centralized FastAPI dependencies for service factories and authorization.

This module provides:
- Dependency injection factories following DIP
- Authorization dependencies following DRY (single parameterized class)
"""

from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlmodel import Session

from api.auth.dependencies import CurrentUser
from api.config import get_settings
from api.db.models import Project
from api.db.session import get_session
from api.services.calculation_service import CalculationService
from api.services.invitation_service import InvitationService
from api.services.opinion_service import OpinionService
from api.services.project_service import ProjectService
from api.services.storage.azure_blob_service import AzureBlobStorageService
from api.services.user_service import UserService
from src.calculators.become_calculator import BeCoMeCalculator

# --- Calculator Factories ---


def get_calculator() -> BeCoMeCalculator:
    """Create BeCoMeCalculator instance.

    Factory function for dependency injection, allowing easy
    substitution in tests.

    :return: BeCoMeCalculator instance
    """
    return BeCoMeCalculator()


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


def get_storage_service() -> AzureBlobStorageService | None:
    """Create storage service if Azure is configured.

    Returns None if Azure storage is not configured,
    allowing graceful degradation.

    :return: AzureBlobStorageService or None
    """
    settings = get_settings()
    if not settings.azure_storage_enabled:
        return None
    return AzureBlobStorageService(settings)


# --- Authorization Dependencies ---


class AccessLevel(str, Enum):
    """Access level for project authorization.

    Following DRY: single enum instead of multiple classes.
    """

    MEMBER = "member"
    ADMIN = "admin"


class RequireProjectAccess:
    """Dependency that verifies user has required access level to a project.

    Following DRY: single parameterized class replaces multiple duplicate classes.
    Following OCP: extend by adding new AccessLevel values, not new classes.

    :param access_level: Required access level (MEMBER or ADMIN)
    """

    def __init__(self, access_level: AccessLevel) -> None:
        """Initialize with required access level.

        :param access_level: Minimum access level required
        """
        self._access_level = access_level

    def __call__(
        self,
        project_id: UUID,
        current_user: CurrentUser,
        service: Annotated[ProjectService, Depends(get_project_service)],
    ) -> Project:
        """Verify access level and return project.

        :param project_id: Project UUID from path
        :param current_user: Authenticated user
        :param service: Project service
        :return: Project if user has required access
        :raises HTTPException: 404 if not found, 403 if insufficient access
        """
        project = service.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

        has_access = self._check_access(service, project_id, current_user.id)
        if not has_access:
            detail = self._get_error_detail()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            )
        return project

    def _check_access(self, service: ProjectService, project_id: UUID, user_id: UUID) -> bool:
        """Check if user has required access level.

        :param service: Project service
        :param project_id: Project ID
        :param user_id: User ID
        :return: True if user has required access
        """
        if self._access_level == AccessLevel.ADMIN:
            return service.is_admin(project_id, user_id)
        return service.is_member(project_id, user_id)

    def _get_error_detail(self) -> str:
        """Get error message for insufficient access.

        :return: Error detail string
        """
        if self._access_level == AccessLevel.ADMIN:
            return "Only project admin can perform this action"
        return "Not a member of this project"


# Pre-configured instances for common use cases
require_project_member = RequireProjectAccess(AccessLevel.MEMBER)
require_project_admin = RequireProjectAccess(AccessLevel.ADMIN)

# Type aliases for cleaner route signatures
ProjectMember = Annotated[Project, Depends(require_project_member)]
ProjectAdmin = Annotated[Project, Depends(require_project_admin)]
