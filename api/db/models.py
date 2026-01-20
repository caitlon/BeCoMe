"""SQLModel table definitions for BeCoMe database."""

import enum
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def _utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(UTC)


class MemberRole(str, enum.Enum):
    """Role of a member within a project."""

    ADMIN = "admin"
    EXPERT = "expert"


class User(SQLModel, table=True):
    """User account in the system."""

    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=255)
    hashed_password: str = Field(max_length=255)
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    photo_url: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=_utc_now)

    owned_projects: list["Project"] = Relationship(back_populates="admin")
    memberships: list["ProjectMember"] = Relationship(back_populates="user")
    opinions: list["ExpertOpinion"] = Relationship(back_populates="user")
    used_invitations: list["Invitation"] = Relationship(back_populates="used_by_user")
    reset_tokens: list["PasswordResetToken"] = Relationship(back_populates="user")


class Project(SQLModel, table=True):
    """A project for group decision-making."""

    __tablename__ = "projects"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None)
    admin_id: UUID = Field(foreign_key="users.id")
    scale_min: float = Field(default=0.0)
    scale_max: float = Field(default=100.0)
    scale_unit: str = Field(default="", max_length=50)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    admin: User = Relationship(back_populates="owned_projects")
    members: list["ProjectMember"] = Relationship(back_populates="project")
    invitations: list["Invitation"] = Relationship(back_populates="project")
    opinions: list["ExpertOpinion"] = Relationship(back_populates="project")
    result: Optional["CalculationResult"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"uselist": False},
    )


class ProjectMember(SQLModel, table=True):
    """Many-to-many relationship between users and projects with roles.

    One user can be a member of a project only once (unique constraint).
    """

    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(foreign_key="projects.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    role: MemberRole = Field(default=MemberRole.EXPERT)
    joined_at: datetime = Field(default_factory=_utc_now)

    project: Project = Relationship(back_populates="members")
    user: User = Relationship(back_populates="memberships")


class Invitation(SQLModel, table=True):
    """Invitation to join a project as an expert."""

    __tablename__ = "invitations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(foreign_key="projects.id", index=True)
    token: UUID = Field(default_factory=uuid4, unique=True, index=True)
    created_at: datetime = Field(default_factory=_utc_now)
    expires_at: datetime
    used_by_id: UUID | None = Field(default=None, foreign_key="users.id")

    project: Project = Relationship(back_populates="invitations")
    used_by_user: User | None = Relationship(back_populates="used_invitations")


class ExpertOpinion(SQLModel, table=True):
    """Expert opinion expressed as a fuzzy triangular number.

    One expert can have only one opinion per project (unique constraint).
    """

    __tablename__ = "expert_opinions"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(foreign_key="projects.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    position: str = Field(default="", max_length=255)
    lower_bound: float
    peak: float
    upper_bound: float
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    project: Project = Relationship(back_populates="opinions")
    user: User = Relationship(back_populates="opinions")


class PasswordResetToken(SQLModel, table=True):
    """Token for password reset via email."""

    __tablename__ = "password_reset_tokens"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    token: UUID = Field(default_factory=uuid4, unique=True, index=True)
    created_at: datetime = Field(default_factory=_utc_now)
    expires_at: datetime
    used_at: datetime | None = Field(default=None)

    user: User = Relationship(back_populates="reset_tokens")


class CalculationResult(SQLModel, table=True):
    """Cached BeCoMe calculation result for a project."""

    __tablename__ = "calculation_results"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(foreign_key="projects.id", unique=True, index=True)
    best_compromise_lower: float
    best_compromise_peak: float
    best_compromise_upper: float
    arithmetic_mean_lower: float
    arithmetic_mean_peak: float
    arithmetic_mean_upper: float
    median_lower: float
    median_peak: float
    median_upper: float
    max_error: float
    num_experts: int
    likert_value: int | None = Field(default=None)
    likert_decision: str | None = Field(default=None, max_length=100)
    calculated_at: datetime = Field(default_factory=_utc_now)

    project: Project = Relationship(back_populates="result")
