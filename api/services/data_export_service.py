"""GDPR data export business logic service (Article 20 - data portability)."""

import logging
from uuid import UUID

from sqlmodel import col, select

from api.db.models import (
    CalculationResult,
    ExpertOpinion,
    Invitation,
    Project,
    ProjectMember,
    User,
)
from api.db.utils import utc_now
from api.schemas.data_export import (
    EXPORT_DESCRIPTION,
    EXPORT_FORMAT_VERSION,
    DataExportResponse,
    ExportMembership,
    ExportMetadata,
    ExportOpinion,
    ExportOwnedProject,
    ExportProfile,
    ExportReceivedInvitation,
)
from api.services.base import BaseService

logger = logging.getLogger("api.service.data_export")


class DataExportService(BaseService):
    """Assemble a full GDPR data export for a single user account.

    Each related collection is loaded with an explicit join so the whole export
    runs in a fixed number of queries rather than lazy-loading relationships per
    row (no N+1 access).
    """

    def build_export(self, user: User) -> DataExportResponse:
        """Collect every piece of data tied to a user into one document.

        :param user: The authenticated account holder.
        :return: DataExportResponse with profile, owned projects, memberships,
            opinions, and received invitations.
        """
        response = DataExportResponse(
            export_metadata=ExportMetadata(
                format_version=EXPORT_FORMAT_VERSION,
                generated_at=utc_now(),
                description=EXPORT_DESCRIPTION,
            ),
            profile=ExportProfile.from_user(user),
            owned_projects=self._owned_projects(user.id),
            memberships=self._memberships(user.id),
            opinions=self._opinions(user.id),
            received_invitations=self._received_invitations(user.id),
        )
        logger.info(
            "Data export generated",
            extra={
                "event": "data_export_generated",
                "user_id": str(user.id),
                "owned_projects": len(response.owned_projects),
                "memberships": len(response.memberships),
                "opinions": len(response.opinions),
            },
        )
        return response

    def _owned_projects(self, user_id: UUID) -> list[ExportOwnedProject]:
        """Load projects the user administers with their cached results.

        :param user_id: The account holder's ID.
        :return: Owned projects ordered by creation date, each with its result.
        """
        statement = (
            select(Project, CalculationResult)
            .join(CalculationResult, col(CalculationResult.project_id) == Project.id, isouter=True)
            .where(Project.admin_id == user_id)
            .order_by(col(Project.created_at))
        )
        rows = self._session.exec(statement).all()
        return [ExportOwnedProject.from_model(project, result) for project, result in rows]

    def _memberships(self, user_id: UUID) -> list[ExportMembership]:
        """Load the user's project memberships with their projects.

        :param user_id: The account holder's ID.
        :return: Memberships ordered by join date.
        """
        statement = (
            select(ProjectMember, Project)
            .join(Project, col(ProjectMember.project_id) == Project.id)
            .where(ProjectMember.user_id == user_id)
            .order_by(col(ProjectMember.joined_at))
        )
        rows = self._session.exec(statement).all()
        return [ExportMembership.from_model(member, project) for member, project in rows]

    def _opinions(self, user_id: UUID) -> list[ExportOpinion]:
        """Load the opinions the user submitted with their projects.

        :param user_id: The account holder's ID.
        :return: Opinions ordered by creation date.
        """
        statement = (
            select(ExpertOpinion, Project)
            .join(Project, col(ExpertOpinion.project_id) == Project.id)
            .where(ExpertOpinion.user_id == user_id)
            .order_by(col(ExpertOpinion.created_at))
        )
        rows = self._session.exec(statement).all()
        return [ExportOpinion.from_model(opinion, project) for opinion, project in rows]

    def _received_invitations(self, user_id: UUID) -> list[ExportReceivedInvitation]:
        """Load pending invitations addressed to the user with project and inviter.

        :param user_id: The account holder's ID.
        :return: Received invitations ordered by creation date.
        """
        statement = (
            select(Invitation, Project, User)
            .join(Project, col(Invitation.project_id) == Project.id)
            .join(User, col(Invitation.inviter_id) == User.id)
            .where(Invitation.invitee_id == user_id)
            .order_by(col(Invitation.created_at))
        )
        rows = self._session.exec(statement).all()
        return [
            ExportReceivedInvitation.from_model(invitation, project, inviter)
            for invitation, project, inviter in rows
        ]
