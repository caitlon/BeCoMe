"""Internal Data Transfer Objects for service layer.

These dataclasses replace raw tuples returned by services,
following Interface Segregation Principle (ISP) — clients
work with well-defined types instead of anonymous tuples.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from api.db.models import (
    ExpertOpinion,
    MemberRole,
    Project,
    ProjectMember,
    User,
)


@dataclass(frozen=True)
class ProjectWithMemberCount:
    """Project with its member count.

    Replaces tuple[Project, int] for better type safety.
    """

    project: Project
    member_count: int

    @property
    def id(self) -> UUID:
        """Get project ID."""
        return self.project.id

    @property
    def name(self) -> str:
        """Get project name."""
        return self.project.name


@dataclass(frozen=True)
class ProjectWithMemberCountAndRole:
    """Project with member count and user's role.

    Used for listing projects with role information.
    Note: role is stored as MemberRole enum from SQLModel query.
    """

    project: Project
    member_count: int
    role: MemberRole

    @property
    def id(self) -> UUID:
        """Get project ID."""
        return self.project.id

    @property
    def name(self) -> str:
        """Get project name."""
        return self.project.name


@dataclass(frozen=True)
class MemberWithUser:
    """Project membership with user details.

    Replaces tuple[ProjectMember, User] for better type safety.
    """

    membership: ProjectMember
    user: User

    @property
    def user_id(self) -> UUID:
        """Get user ID."""
        return self.user.id

    @property
    def email(self) -> str:
        """Get user email."""
        return self.user.email

    @property
    def first_name(self) -> str:
        """Get user first name."""
        return self.user.first_name

    @property
    def last_name(self) -> str | None:
        """Get user last name."""
        return self.user.last_name

    @property
    def role(self) -> MemberRole:
        """Get member role."""
        return self.membership.role

    @property
    def joined_at(self) -> datetime:
        """Get join timestamp."""
        return self.membership.joined_at


@dataclass(frozen=True)
class OpinionWithUser:
    """Expert opinion with user details.

    Replaces tuple[ExpertOpinion, User] for better type safety.
    """

    opinion: ExpertOpinion
    user: User

    @property
    def opinion_id(self) -> UUID:
        """Get opinion ID."""
        return self.opinion.id

    @property
    def user_id(self) -> UUID:
        """Get user ID."""
        return self.user.id

    @property
    def position(self) -> str:
        """Get expert position."""
        return self.opinion.position

    @property
    def lower_bound(self) -> float:
        """Get fuzzy number lower bound."""
        return self.opinion.lower_bound

    @property
    def peak(self) -> float:
        """Get fuzzy number peak."""
        return self.opinion.peak

    @property
    def upper_bound(self) -> float:
        """Get fuzzy number upper bound."""
        return self.opinion.upper_bound


@dataclass(frozen=True)
class UpsertResult:
    """Result of upsert operation with creation flag.

    Replaces tuple[ExpertOpinion, bool] for better type safety.
    """

    opinion: ExpertOpinion
    is_new: bool

    @property
    def opinion_id(self) -> UUID:
        """Get opinion ID."""
        return self.opinion.id

    @property
    def was_created(self) -> bool:
        """Check if opinion was newly created."""
        return self.is_new

    @property
    def was_updated(self) -> bool:
        """Check if existing opinion was updated."""
        return not self.is_new
