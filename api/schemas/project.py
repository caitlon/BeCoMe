"""Project management schemas."""

from datetime import datetime
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from api.utils.sanitization import sanitize_text, sanitize_text_or_none

if TYPE_CHECKING:
    from api.db.models import Project, ProjectMember, User


class ProjectCreate(BaseModel):
    """Request to create a new project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: str | None = Field(None, max_length=2000, description="Project description")
    scale_min: float = Field(default=0.0, description="Minimum scale value")
    scale_max: float = Field(default=100.0, description="Maximum scale value")
    scale_unit: str = Field(
        default="", max_length=50, description="Scale unit (e.g., '%', 'points')"
    )

    @field_validator("name", "scale_unit", mode="after")
    @classmethod
    def sanitize_required_text(cls, v: str) -> str:
        """Remove HTML from text fields."""
        return sanitize_text(v)

    @field_validator("description", mode="after")
    @classmethod
    def sanitize_optional_text(cls, v: str | None) -> str | None:
        """Remove HTML from optional text fields."""
        return sanitize_text_or_none(v)

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

    @field_validator("name", "description", "scale_unit", mode="after")
    @classmethod
    def sanitize_text_fields(cls, v: str | None) -> str | None:
        """Remove HTML from text fields."""
        return sanitize_text_or_none(v)


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

    @classmethod
    def from_model(cls, project: "Project", member_count: int) -> "ProjectResponse":
        """Create response from database model.

        :param project: Project database model
        :param member_count: Number of project members
        :return: ProjectResponse instance
        """
        return cls(
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


class ProjectWithRoleResponse(ProjectResponse):
    """Project details with user's role."""

    role: str

    @classmethod
    def from_model_with_role(
        cls, project: "Project", member_count: int, role: str
    ) -> "ProjectWithRoleResponse":
        """Create response from database model with role.

        :param project: Project database model
        :param member_count: Number of project members
        :param role: User's role in the project (admin/expert)
        :return: ProjectWithRoleResponse instance
        """
        return cls(
            id=str(project.id),
            name=project.name,
            description=project.description,
            scale_min=project.scale_min,
            scale_max=project.scale_max,
            scale_unit=project.scale_unit,
            admin_id=str(project.admin_id),
            created_at=project.created_at,
            member_count=member_count,
            role=role,
        )


class MemberResponse(BaseModel):
    """Project member details."""

    user_id: str
    email: str
    first_name: str
    last_name: str | None
    photo_url: str | None = None
    role: str
    joined_at: datetime

    @classmethod
    def from_model(cls, member: "ProjectMember", user: "User") -> "MemberResponse":
        """Create response from database models.

        :param member: ProjectMember database model
        :param user: User database model
        :return: MemberResponse instance
        """
        return cls(
            user_id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            photo_url=user.photo_url,
            role=member.role.value,
            joined_at=member.joined_at,
        )
