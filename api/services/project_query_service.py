"""Project query service for complex UI queries."""

import logging
from time import perf_counter
from uuid import UUID

from sqlmodel import col, select

from api.db.models import MemberRole, Project, ProjectMember
from api.schemas.internal import ProjectWithMemberCount, ProjectWithMemberCountAndRole
from api.services.base import BaseService
from api.services.query_helpers import MemberCountSubquery

logger = logging.getLogger("api.service.project_query")


def _log_query(variant: str, user_id: UUID, row_count: int, start: float, **fields: object) -> None:
    """Trace one project query's shape and cost.

    This is the application-level answer to "trace the reads". Turning
    ``sqlalchemy.engine`` up instead would print the statement and, at DEBUG, its bound
    parameters, meaning password hashes, addresses, and names, into the log drain, so
    :data:`api.logging_config._EXTERNAL_LOG_LEVELS` pins that logger below DEBUG and
    the shape and timing are recorded here instead. The statement itself is never
    logged.

    :param variant: Which query ran: ``with_counts`` or ``with_roles``.
    :param user_id: Owner of the result set.
    :param row_count: Rows returned.
    :param start: ``perf_counter()`` reading taken before the query.
    :param fields: Extra context, for example the paging window.
    """
    logger.debug(
        "User projects queried",
        extra={
            "event": "user_projects_queried",
            "variant": variant,
            "user_id": str(user_id),
            "row_count": row_count,
            "duration_ms": round((perf_counter() - start) * 1000.0, 1),
            **fields,
        },
    )


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
        start = perf_counter()
        results = self._session.exec(statement).all()
        _log_query("with_counts", user_id, len(results), start)
        return [
            ProjectWithMemberCount(project=project, member_count=count)
            for project, count in results
        ]

    def get_user_projects_with_roles(
        self, user_id: UUID, limit: int | None = None, offset: int = 0
    ) -> list[ProjectWithMemberCountAndRole]:
        """Get projects where user is a member, with member counts and role.

        Uses a single query with subquery to avoid N+1 problem.

        :param user_id: User ID
        :param limit: Max rows to return; ``None`` returns every project.
        :param offset: Rows to skip when a limit is set.
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
        if limit is not None:
            statement = statement.limit(limit).offset(offset)
        start = perf_counter()
        results = self._session.exec(statement).all()
        _log_query("with_roles", user_id, len(results), start, limit=limit, offset=offset)
        return [
            ProjectWithMemberCountAndRole(
                project=project,
                member_count=count,
                role=MemberRole(role) if isinstance(role, str) else role,
            )
            for project, count, role in results
        ]
