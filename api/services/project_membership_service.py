"""Project membership business logic service."""

import logging
from uuid import UUID

from sqlmodel import col, select

from api.db.models import ExpertOpinion, MemberRole, Project, ProjectMember, User
from api.exceptions import (
    AdminCannotLeaveProjectError,
    MemberNotFoundError,
    ProjectNotFoundError,
)
from api.schemas.internal import MemberWithUser
from api.services.base import BaseService
from api.services.calculation_service import CalculationService

logger = logging.getLogger("api.service.membership")


class ProjectMembershipService(BaseService):
    """Service for project membership operations.

    Handles member queries, role checks, and membership mutations.
    """

    def get_members(
        self, project_id: UUID, limit: int | None = None, offset: int = 0
    ) -> list[MemberWithUser]:
        """Get members of a project with user details.

        :param project_id: Project ID
        :param limit: Max rows to return; ``None`` returns every member.
        :param offset: Rows to skip when a limit is set.
        :return: List of MemberWithUser instances
        """
        statement = (
            select(ProjectMember, User)
            .join(User)
            .where(ProjectMember.project_id == project_id)
            .order_by(col(ProjectMember.joined_at))
        )
        if limit is not None:
            statement = statement.limit(limit).offset(offset)
        results = self._session.exec(statement).all()
        return [MemberWithUser(membership=membership, user=user) for membership, user in results]

    def remove_member(
        self,
        project_id: UUID,
        user_id: UUID,
        calculation_service: CalculationService | None = None,
    ) -> bool:
        """Remove a member from project, discarding the opinion they submitted.

        The opinion goes in the same transaction as the membership. It carries the
        member's identity, meaning name, email, and position, and is served to every
        remaining member and embedded in every export, while ``RequireProjectAccess`` stops the
        ex-member from withdrawing it themselves once their membership row is gone.

        When a calculation service is given and an opinion was discarded, the project's
        result is recalculated in the same transaction, so a failure leaves the
        membership, the opinion and the result untouched. The project row is locked before
        the membership and the opinion, in the order a project deletion takes them.

        :param project_id: Project ID
        :param user_id: User ID to remove
        :param calculation_service: Recalculates the result without the discarded opinion
        :return: True when an opinion was discarded
        :raises ProjectNotFoundError: If the project was deleted before it could be locked
        :raises MemberNotFoundError: If user is not a member of the project
        """
        if calculation_service is not None and not calculation_service.lock_project(project_id):
            raise ProjectNotFoundError("Project not found")
        membership = self._get_membership(project_id, user_id)
        if not membership:
            raise MemberNotFoundError(f"User {user_id} is not a member of project {project_id}")

        opinion_discarded = self._delete_membership(membership, calculation_service)

        logger.info(
            "Member removed",
            extra={
                "event": "member_removed",
                "project_id": str(project_id),
                "user_id": str(user_id),
                "opinion_discarded": opinion_discarded,
            },
        )
        return opinion_discarded

    def leave_project(
        self,
        project_id: UUID,
        user_id: UUID,
        calculation_service: CalculationService,
    ) -> bool:
        """Remove the caller's own membership and opinion, and recalculate the result.

        Does what :meth:`remove_member` does for an admin's removal. The project row is
        locked first, as a transfer of ownership locks it, so the two serialize. The
        project and the membership are then read from the database again, because the
        request's dependencies loaded them before the wait and, under READ COMMITTED, a
        transfer that committed meanwhile would otherwise stay invisible. The admin is
        refused here: a project cannot be left without an admin, and the database would
        reject the delete at commit.

        :param project_id: Project ID
        :param user_id: ID of the member who leaves
        :param calculation_service: Recalculates the result without the discarded opinion
        :return: True when an opinion was discarded
        :raises ProjectNotFoundError: If the project was deleted before it could be locked
        :raises AdminCannotLeaveProjectError: If the user is the project's admin
        :raises MemberNotFoundError: If user is not a member of the project
        """
        if not calculation_service.lock_project(project_id):
            raise ProjectNotFoundError("Project not found")
        project = self._session.get(Project, project_id, populate_existing=True)
        membership = self._session.exec(
            select(ProjectMember)
            .where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
            .execution_options(populate_existing=True)
        ).first()
        if project is None:
            raise ProjectNotFoundError("Project not found")
        if not membership:
            raise MemberNotFoundError(f"User {user_id} is not a member of project {project_id}")
        if project.admin_id == user_id or membership.role == MemberRole.ADMIN:
            raise AdminCannotLeaveProjectError(
                f"User {user_id} is the admin of project {project_id} and cannot leave it"
            )

        opinion_discarded = self._delete_membership(membership, calculation_service)

        logger.info(
            "Member left",
            extra={
                "event": "member_left",
                "project_id": str(project_id),
                "user_id": str(user_id),
                "opinion_discarded": opinion_discarded,
            },
        )
        return opinion_discarded

    def is_member(self, project_id: UUID, user_id: UUID) -> bool:
        """Check if user is a member of the project.

        :param project_id: Project ID
        :param user_id: User ID
        :return: True if user is a member
        """
        return self._get_membership(project_id, user_id) is not None

    def is_demo_account(self, user_id: UUID) -> bool:
        """Report whether a user id belongs to the demo expert pool.

        A demo account can never log in, so accepting one as a transfer target (a
        project's own admin, or an account-deletion disposition) would stand up an
        admin nobody can ever reach again. Callers that accept a transfer target
        should refuse one for which this returns True.

        :param user_id: User id to check.
        :return: True when the account exists and is flagged ``is_demo``.
        """
        user = self._session.get(User, user_id)
        return user is not None and user.is_demo

    def is_admin(self, project_id: UUID, user_id: UUID) -> bool:
        """Check if user is an admin of the project.

        :param project_id: Project ID
        :param user_id: User ID
        :return: True if user is an admin
        """
        statement = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.role == MemberRole.ADMIN,
        )
        return self._session.exec(statement).first() is not None

    def get_user_role_in_project(self, project_id: UUID, user_id: UUID) -> MemberRole | None:
        """Get user's role in a project.

        :param project_id: Project ID
        :param user_id: User ID
        :return: MemberRole if user is a member, None otherwise
        """
        membership = self._get_membership(project_id, user_id)
        return membership.role if membership else None

    def _delete_membership(
        self,
        membership: ProjectMember,
        calculation_service: CalculationService | None,
    ) -> bool:
        """Delete a membership with the member's opinion and commit.

        Expects the project row to be locked already. The result is staged for
        recalculation only when an opinion was discarded, before the one commit.

        :param membership: The membership to delete
        :param calculation_service: Recalculates the result; ``None`` skips it
        :return: True when an opinion was discarded
        """
        opinion = self._session.exec(
            select(ExpertOpinion).where(
                ExpertOpinion.project_id == membership.project_id,
                ExpertOpinion.user_id == membership.user_id,
            )
        ).first()

        self._session.delete(membership)
        if opinion is not None:
            self._session.delete(opinion)
        self._session.flush()
        if opinion is not None and calculation_service is not None:
            calculation_service.stage_recalculation(membership.project_id)
        self._session.commit()
        return opinion is not None

    def _get_membership(self, project_id: UUID, user_id: UUID) -> ProjectMember | None:
        """Get membership record for user in project.

        :param project_id: Project ID
        :param user_id: User ID
        :return: ProjectMember if found, None otherwise
        """
        statement = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        return self._session.exec(statement).first()
