"""Invitation management schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


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


class InvitationInfoResponse(BaseModel):
    """Public information about an invitation."""

    project_name: str
    project_description: str | None
    admin_name: str
    expires_at: datetime
    is_valid: bool
