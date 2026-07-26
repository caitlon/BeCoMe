"""Project membership business logic service."""

import logging
from uuid import UUID

from sqlmodel import col, select

from api.db.models import ExpertOpinion, MemberRole, ProjectMember, User
from api.exceptions import MemberNotFoundError
from api.schemas.internal import MemberWithUser
from api.services.base import BaseService

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

    def remove_member(self, project_id: UUID, user_id: UUID) -> bool:
        """Remove a member from project, discarding the opinion they submitted.

        The opinion goes in the same transaction as the membership. It carries the
        member's identity -- name, email, position -- and is served to every remaining
        member and embedded in every export, while ``RequireProjectAccess`` stops the
        ex-member from withdrawing it themselves once their membership row is gone.

        :param project_id: Project ID
        :param user_id: User ID to remove
        :return: True when an opinion was discarded, so the caller can recalculate
        :raises MemberNotFoundError: If user is not a member of the project
        """
        membership = self._get_membership(project_id, user_id)
        if not membership:
            raise MemberNotFoundError(f"User {user_id} is not a member of project {project_id}")

        opinion = self._session.exec(
            select(ExpertOpinion).where(
                ExpertOpinion.project_id == project_id,
                ExpertOpinion.user_id == user_id,
            )
        ).first()

        self._session.delete(membership)
        if opinion is not None:
            self._session.delete(opinion)
        self._session.commit()

        logger.info(
            "Member removed",
            extra={
                "event": "member_removed",
                "project_id": str(project_id),
                "user_id": str(user_id),
                "opinion_discarded": opinion is not None,
            },
        )
        return opinion is not None

    def is_member(self, project_id: UUID, user_id: UUID) -> bool:
        """Check if user is a member of the project.

        :param project_id: Project ID
        :param user_id: User ID
        :return: True if user is a member
        """
        return self._get_membership(project_id, user_id) is not None

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

    def add_member(self, project_id: UUID, user_id: UUID, role: MemberRole) -> ProjectMember:
        """Add a member to project.

        :param project_id: Project ID
        :param user_id: User ID to add
        :param role: Member role
        :return: Created ProjectMember instance
        """
        membership = ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role=role,
        )
        return self._save_and_refresh(membership)

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
