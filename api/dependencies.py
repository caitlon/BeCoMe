"""Centralized FastAPI dependencies for service factories and authorization.

This module provides:
- Dependency injection factories following DIP
- Authorization dependencies following DRY (single parameterized class)
"""

import logging
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlmodel import Session

from api.auth.dependencies import CurrentUser
from api.config import get_settings
from api.db.models import Project
from api.db.session import get_session
from api.services.calculation_service import CalculationService
from api.services.data_export_service import DataExportService
from api.services.email.base import EmailSender
from api.services.email.console_email_sender import ConsoleEmailSender
from api.services.email.resend_email_sender import ResendEmailSender
from api.services.invitation_service import InvitationService
from api.services.opinion_service import OpinionService
from api.services.password_reset_service import PasswordResetService
from api.services.project_membership_service import ProjectMembershipService
from api.services.project_query_service import ProjectQueryService
from api.services.project_service import ProjectService
from api.services.storage.base import StorageService
from api.services.storage.exceptions import StorageConfigurationError
from api.services.storage.railway_bucket_storage_service import RailwayBucketStorageService
from api.services.user_service import UserService
from src.calculators.become_calculator import BeCoMeCalculator

logger = logging.getLogger("api.security")

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


def get_project_membership_service(
    session: Annotated[Session, Depends(get_session)],
) -> ProjectMembershipService:
    """Create ProjectMembershipService instance."""
    return ProjectMembershipService(session)


def get_project_query_service(
    session: Annotated[Session, Depends(get_session)],
) -> ProjectQueryService:
    """Create ProjectQueryService instance."""
    return ProjectQueryService(session)


def get_opinion_service(session: Annotated[Session, Depends(get_session)]) -> OpinionService:
    """Create OpinionService instance."""
    return OpinionService(session)


def get_calculation_service(
    session: Annotated[Session, Depends(get_session)],
) -> CalculationService:
    """Create CalculationService instance."""
    return CalculationService(session)


def get_data_export_service(
    session: Annotated[Session, Depends(get_session)],
) -> DataExportService:
    """Create DataExportService instance."""
    return DataExportService(session)


def get_invitation_service(session: Annotated[Session, Depends(get_session)]) -> InvitationService:
    """Create InvitationService instance."""
    return InvitationService(session)


def get_password_reset_service(
    session: Annotated[Session, Depends(get_session)],
) -> PasswordResetService:
    """Create PasswordResetService instance."""
    return PasswordResetService(session)


def get_email_service() -> EmailSender:
    """Create the email sender for the configured provider.

    Always returns a usable sender: when the HTTP provider is selected and
    configured it sends for real; otherwise it falls back to the console sender
    that logs the link. The forgot-password flow must never 503 (that would leak
    account existence), so there is no None / unconfigured branch here.

    :return: An EmailSender implementation.
    """
    settings = get_settings()
    if settings.email_provider == "http" and settings.email_enabled:
        return ResendEmailSender(settings)
    return ConsoleEmailSender(settings)


def get_storage_service() -> StorageService | None:
    """Create the storage service when bucket storage is configured.

    Returns None when storage is not configured or initialization fails,
    which disables photo upload while leaving the rest of the API working.

    :return: A StorageService implementation, or None.
    """
    settings = get_settings()
    if not settings.storage_enabled:
        return None
    try:
        return RailwayBucketStorageService(settings)
    except StorageConfigurationError:
        return None


# --- Authorization Dependencies ---


class AccessLevel(StrEnum):
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
        project_service: Annotated[ProjectService, Depends(get_project_service)],
        membership_service: Annotated[
            ProjectMembershipService, Depends(get_project_membership_service)
        ],
    ) -> Project:
        """Verify access level and return project.

        :param project_id: Project UUID from path
        :param current_user: Authenticated user
        :param project_service: Project service for fetching project
        :param membership_service: Membership service for access checks
        :return: Project if user has required access
        :raises HTTPException: 404 if not found, 403 if insufficient access
        """
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

        has_access = self._check_access(membership_service, project_id, current_user.id)
        if not has_access:
            detail = self._get_error_detail()
            logger.warning(
                "Project access denied",
                extra={
                    "event": "access_denied",
                    "project_id": str(project_id),
                    "user_id": str(current_user.id),
                    "required_level": self._access_level.value,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            )
        return project

    def _check_access(
        self, service: ProjectMembershipService, project_id: UUID, user_id: UUID
    ) -> bool:
        """Check if user has required access level.

        :param service: Membership service
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
