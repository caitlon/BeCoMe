"""GDPR data export schemas (Article 20 - data portability).

These schemas describe the machine-readable document returned by
``GET /users/me/export``. They deliberately mirror only the data a user
contributed (profile, owned projects, memberships, opinions, invitations) and
never expose password material.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from api.schemas.calculation import FuzzyNumberOutput
from api.utils.photo_links import build_photo_url

if TYPE_CHECKING:
    from api.db.models import (
        CalculationResult,
        ExpertOpinion,
        Invitation,
        Project,
        ProjectMember,
        User,
    )

EXPORT_FORMAT_VERSION = "1.0"
EXPORT_DESCRIPTION = (
    "Personal data export under GDPR Article 20 (right to data portability). "
    "Contains all data associated with your BeCoMe account."
)


def _fuzzy(lower: float, peak: float, upper: float) -> FuzzyNumberOutput:
    """Build a fuzzy-number output with a centroid from raw bounds.

    :param lower: Lower bound (pessimistic estimate).
    :param peak: Peak value (most likely).
    :param upper: Upper bound (optimistic estimate).
    :return: FuzzyNumberOutput with the computed centroid.
    """
    return FuzzyNumberOutput(
        lower=lower,
        peak=peak,
        upper=upper,
        centroid=(lower + peak + upper) / 3,
    )


class ExportMetadata(BaseModel):
    """Metadata describing the export document itself."""

    format_version: str
    generated_at: datetime
    description: str


class ExportProfile(BaseModel):
    """The account holder's own profile (no password material)."""

    id: str
    email: str
    first_name: str
    last_name: str
    photo_url: str | None = None
    created_at: datetime

    @classmethod
    def from_user(cls, user: "User") -> "ExportProfile":
        """Build the profile section from a user model.

        :param user: User database model.
        :return: ExportProfile with the public photo URL, never a password hash.
        """
        return cls(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            photo_url=build_photo_url(user.id, user.photo_url),
            created_at=user.created_at,
        )


class ExportResult(BaseModel):
    """BeCoMe calculation result attached to an owned project."""

    best_compromise: FuzzyNumberOutput
    arithmetic_mean: FuzzyNumberOutput
    median: FuzzyNumberOutput
    max_error: float
    num_experts: int
    likert_value: int | None = None
    likert_decision: str | None = None
    calculated_at: datetime

    @classmethod
    def from_model(cls, result: "CalculationResult") -> "ExportResult":
        """Build the result section from a calculation result model.

        :param result: CalculationResult database model.
        :return: ExportResult with grouped fuzzy components.
        """
        return cls(
            best_compromise=_fuzzy(
                result.best_compromise_lower,
                result.best_compromise_peak,
                result.best_compromise_upper,
            ),
            arithmetic_mean=_fuzzy(
                result.arithmetic_mean_lower,
                result.arithmetic_mean_peak,
                result.arithmetic_mean_upper,
            ),
            median=_fuzzy(
                result.median_lower,
                result.median_peak,
                result.median_upper,
            ),
            max_error=result.max_error,
            num_experts=result.num_experts,
            likert_value=result.likert_value,
            likert_decision=result.likert_decision,
            calculated_at=result.calculated_at,
        )


class ExportOwnedProject(BaseModel):
    """A project the account holder administers."""

    id: str
    name: str
    description: str | None = None
    scale_min: float
    scale_max: float
    scale_unit: str
    created_at: datetime
    result: ExportResult | None = None

    @classmethod
    def from_model(
        cls, project: "Project", result: "CalculationResult | None"
    ) -> "ExportOwnedProject":
        """Build an owned-project section from a project model.

        The cached result is passed explicitly (loaded via an outer join) so the
        export assembles in a fixed number of queries instead of lazy-loading per
        project.

        :param project: Project database model.
        :param result: Cached calculation result, or None when not computed yet.
        :return: ExportOwnedProject including the cached result when present.
        """
        return cls(
            id=str(project.id),
            name=project.name,
            description=project.description,
            scale_min=project.scale_min,
            scale_max=project.scale_max,
            scale_unit=project.scale_unit,
            created_at=project.created_at,
            result=ExportResult.from_model(result) if result else None,
        )


class ExportMembership(BaseModel):
    """A project the account holder participates in."""

    project_id: str
    project_name: str
    role: str
    joined_at: datetime

    @classmethod
    def from_model(cls, member: "ProjectMember", project: "Project") -> "ExportMembership":
        """Build a membership section from a membership model.

        :param member: ProjectMember database model.
        :param project: The project joined to the membership.
        :return: ExportMembership with the project name and the user's role.
        """
        return cls(
            project_id=str(member.project_id),
            project_name=project.name,
            role=member.role.value,
            joined_at=member.joined_at,
        )


class ExportOpinion(BaseModel):
    """An expert opinion the account holder submitted."""

    id: str
    project_id: str
    project_name: str
    position: str
    lower_bound: float
    peak: float
    upper_bound: float
    centroid: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, opinion: "ExpertOpinion", project: "Project") -> "ExportOpinion":
        """Build an opinion section from an opinion model.

        :param opinion: ExpertOpinion database model.
        :param project: The project the opinion belongs to.
        :return: ExportOpinion with the fuzzy triangular values and project name.
        """
        return cls(
            id=str(opinion.id),
            project_id=str(opinion.project_id),
            project_name=project.name,
            position=opinion.position,
            lower_bound=opinion.lower_bound,
            peak=opinion.peak,
            upper_bound=opinion.upper_bound,
            centroid=(opinion.lower_bound + opinion.peak + opinion.upper_bound) / 3,
            created_at=opinion.created_at,
            updated_at=opinion.updated_at,
        )


class ExportReceivedInvitation(BaseModel):
    """A pending invitation addressed to the account holder."""

    id: str
    project_id: str
    project_name: str
    inviter_email: str
    invited_at: datetime

    @classmethod
    def from_model(
        cls, invitation: "Invitation", project: "Project", inviter: "User"
    ) -> "ExportReceivedInvitation":
        """Build an invitation section from an invitation model.

        :param invitation: Invitation database model.
        :param project: The project the invitation is for.
        :param inviter: The user who sent the invitation.
        :return: ExportReceivedInvitation with project name and inviter email.
        """
        return cls(
            id=str(invitation.id),
            project_id=str(invitation.project_id),
            project_name=project.name,
            inviter_email=inviter.email,
            invited_at=invitation.created_at,
        )


class DataExportResponse(BaseModel):
    """Full GDPR data export for a single user account."""

    export_metadata: ExportMetadata
    profile: ExportProfile
    owned_projects: list[ExportOwnedProject]
    memberships: list[ExportMembership]
    opinions: list[ExportOpinion]
    received_invitations: list[ExportReceivedInvitation]
