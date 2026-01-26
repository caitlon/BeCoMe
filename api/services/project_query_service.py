"""Project query service for complex UI queries."""

from uuid import UUID

from sqlmodel import col, select

from api.db.models import MemberRole, Project, ProjectMember
from api.schemas.internal import ProjectWithMemberCount, ProjectWithMemberCountAndRole
from api.services.base import BaseService
from api.services.query_helpers import MemberCountSubquery


class ProjectQueryService(BaseService):
    """Service for complex project queries.

    Handles queries that join multiple tables for UI display.
    """

    def get_user_projects_with_counts(self, user_id: UUID) -> list[ProjectWithMemberCount]:
        """Get all projects where user is a member, with member counts.

        Uses a single query with subquery to avoid N+1 problem.

        :param user_id: User ID
        :return: List of ProjectWithMemberCount instances
        """
        member_count_subquery = MemberCountSubquery.build()

        statement = (
            select(Project, member_count_subquery.c.member_count)
            .join(ProjectMember, col(ProjectMember.project_id) == Project.id)
            .join(
                member_count_subquery,
                member_count_subquery.c.project_id == Project.id,
            )
            .where(ProjectMember.user_id == user_id)
            .order_by(col(Project.created_at).desc())
        )
        results = self._session.exec(statement).all()
        return [
            ProjectWithMemberCount(project=project, member_count=count)
            for project, count in results
        ]

    def get_user_projects_with_roles(self, user_id: UUID) -> list[ProjectWithMemberCountAndRole]:
        """Get all projects where user is a member, with member counts and role.

        Uses a single query with subquery to avoid N+1 problem.

        :param user_id: User ID
        :return: List of ProjectWithMemberCountAndRole instances
        """
        member_count_subquery = MemberCountSubquery.build()

        statement = (
            select(Project, member_count_subquery.c.member_count, ProjectMember.role)
            .join(ProjectMember, col(ProjectMember.project_id) == Project.id)
            .join(
                member_count_subquery,
                member_count_subquery.c.project_id == Project.id,
            )
            .where(ProjectMember.user_id == user_id)
            .order_by(col(Project.created_at).desc())
        )
        results = self._session.exec(statement).all()
        return [
            ProjectWithMemberCountAndRole(
                project=project,
                member_count=count,
                role=MemberRole(role) if isinstance(role, str) else role,
            )
            for project, count, role in results
        ]
