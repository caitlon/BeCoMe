"""Invitation management schemas for email-based invitations."""

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, EmailStr, Field

if TYPE_CHECKING:
    from api.db.models import Invitation, Project, User


class InviteByEmailRequest(BaseModel):
    """Request to invite a user by email."""

    email: EmailStr = Field(..., description="Email of user to invite")


class InvitationResponse(BaseModel):
    """Response after creating an invitation."""

    id: str
    project_id: str
    invitee_email: str
    invited_at: datetime

    @classmethod
    def from_model(cls, invitation: "Invitation", invitee: "User") -> "InvitationResponse":
        """Create response from database models.

        :param invitation: Invitation database model
        :param invitee: Invitee user database model
        :return: InvitationResponse instance
        """
        return cls(
            id=str(invitation.id),
            project_id=str(invitation.project_id),
            invitee_email=invitee.email,
            invited_at=invitation.created_at,
        )


class InvitationListItemResponse(BaseModel):
    """Single invitation in user's invitation list."""

    id: str
    project_id: str
    project_name: str
    project_description: str | None
    project_scale_min: float
    project_scale_max: float
    project_scale_unit: str
    inviter_email: str
    inviter_first_name: str
    current_experts_count: int
    invited_at: datetime

    @classmethod
    def from_model(
        cls,
        invitation: "Invitation",
        project: "Project",
        inviter: "User",
        member_count: int,
    ) -> "InvitationListItemResponse":
        """Create response from database models.

        :param invitation: Invitation database model
        :param project: Project database model
        :param inviter: User who sent the invitation
        :param member_count: Current number of project members
        :return: InvitationListItemResponse instance
        """
        return cls(
            id=str(invitation.id),
            project_id=str(project.id),
            project_name=project.name,
            project_description=project.description,
            project_scale_min=project.scale_min,
            project_scale_max=project.scale_max,
            project_scale_unit=project.scale_unit,
            inviter_email=inviter.email,
            inviter_first_name=inviter.first_name,
            current_experts_count=member_count,
            invited_at=invitation.created_at,
        )


class ProjectInvitationResponse(BaseModel):
    """Pending invitation shown on the project detail page."""

    id: str
    invitee_email: str
    invitee_first_name: str
    invitee_last_name: str | None
    invited_at: datetime

    @classmethod
    def from_model(cls, invitation: "Invitation", invitee: "User") -> "ProjectInvitationResponse":
        """Create response from database models.

        :param invitation: Invitation database model
        :param invitee: Invitee user database model
        :return: ProjectInvitationResponse instance
        """
        return cls(
            id=str(invitation.id),
            invitee_email=invitee.email,
            invitee_first_name=invitee.first_name,
            invitee_last_name=invitee.last_name,
            invited_at=invitation.created_at,
        )
