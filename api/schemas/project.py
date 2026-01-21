"""Project management schemas."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator


class ProjectCreate(BaseModel):
    """Request to create a new project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: str | None = Field(None, max_length=2000, description="Project description")
    scale_min: float = Field(default=0.0, description="Minimum scale value")
    scale_max: float = Field(default=100.0, description="Maximum scale value")
    scale_unit: str = Field(
        default="", max_length=50, description="Scale unit (e.g., '%', 'points')"
    )

    @model_validator(mode="after")
    def validate_scale(self) -> Self:
        """Validate scale_min < scale_max."""
        if self.scale_min >= self.scale_max:
            msg = f"scale_min ({self.scale_min}) must be less than scale_max ({self.scale_max})"
            raise ValueError(msg)
        return self


class ProjectUpdate(BaseModel):
    """Request to update a project (partial update)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    scale_min: float | None = None
    scale_max: float | None = None
    scale_unit: str | None = Field(None, max_length=50)


class ProjectResponse(BaseModel):
    """Project details response."""

    id: str
    name: str
    description: str | None
    scale_min: float
    scale_max: float
    scale_unit: str
    admin_id: str
    created_at: datetime
    member_count: int


class MemberResponse(BaseModel):
    """Project member details."""

    user_id: str
    email: str
    first_name: str
    last_name: str | None
    role: str
    joined_at: datetime
