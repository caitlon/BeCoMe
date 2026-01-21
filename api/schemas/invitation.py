"""Invitation management schemas."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from api.db.utils import ensure_utc

if TYPE_CHECKING:
    from api.db.models import Invitation, Project, User


class InvitationCreate(BaseModel):
    """Request to create a project invitation."""

    expires_in_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Days until invitation expires (1-90)",
    )


class InvitationResponse(BaseModel):
    """Response after creating an invitation."""

    token: str
    expires_at: datetime
    project_id: str
    project_name: str

    @classmethod
    def from_model(cls, invitation: "Invitation", project: "Project") -> "InvitationResponse":
        """Create response from database models.

        :param invitation: Invitation database model
        :param project: Project database model
        :return: InvitationResponse instance
        """
        return cls(
            token=str(invitation.token),
            expires_at=invitation.expires_at,
            project_id=str(project.id),
            project_name=project.name,
        )


class InvitationInfoResponse(BaseModel):
    """Public information about an invitation."""

    project_name: str
    project_description: str | None
    admin_name: str
    expires_at: datetime
    is_valid: bool

    @classmethod
    def from_model(
        cls,
        invitation: "Invitation",
        project: "Project",
        admin: "User",
    ) -> "InvitationInfoResponse":
        """Create response from database models.

        :param invitation: Invitation database model
        :param project: Project database model
        :param admin: Admin user database model
        :return: InvitationInfoResponse instance
        """
        admin_name = admin.first_name
        if admin.last_name:
            admin_name = f"{admin.first_name} {admin.last_name}"

        is_used = invitation.used_by_id is not None
        is_expired = datetime.now(UTC) > ensure_utc(invitation.expires_at)
        is_valid = not is_used and not is_expired

        return cls(
            project_name=project.name,
            project_description=project.description,
            admin_name=admin_name,
            expires_at=invitation.expires_at,
            is_valid=is_valid,
        )
