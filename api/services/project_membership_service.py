"""Project membership business logic service."""

from uuid import UUID

from sqlmodel import col, select

from api.db.models import MemberRole, ProjectMember, User
from api.exceptions import MemberNotFoundError
from api.schemas.internal import MemberWithUser
from api.services.base import BaseService


class ProjectMembershipService(BaseService):
    """Service for project membership operations.

    Handles member queries, role checks, and membership mutations.
    """

    def get_members(self, project_id: UUID) -> list[MemberWithUser]:
        """Get all members of a project with user details.

        :param project_id: Project ID
        :return: List of MemberWithUser instances
        """
        statement = (
            select(ProjectMember, User)
            .join(User)
            .where(ProjectMember.project_id == project_id)
            .order_by(col(ProjectMember.joined_at))
        )
        results = self._session.exec(statement).all()
        return [MemberWithUser(membership=membership, user=user) for membership, user in results]

    def remove_member(self, project_id: UUID, user_id: UUID) -> None:
        """Remove a member from project.

        :param project_id: Project ID
        :param user_id: User ID to remove
        :raises MemberNotFoundError: If user is not a member of the project
        """
        membership = self._get_membership(project_id, user_id)
        if not membership:
            raise MemberNotFoundError(f"User {user_id} is not a member of project {project_id}")

        self._delete_and_commit(membership)

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
