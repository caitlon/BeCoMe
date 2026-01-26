"""Query helpers for reusable database query patterns."""

from sqlalchemy.sql.selectable import Subquery
from sqlmodel import col, func, select

from api.db.models import ProjectMember


class MemberCountSubquery:
    """Helper for building member count subqueries.

    Eliminates duplication of member count logic across services.
    """

    @staticmethod
    def build() -> Subquery:
        """Build subquery for counting project members.

        :return: Subquery that can be joined with Project table
        """
        return (
            select(ProjectMember.project_id, func.count().label("member_count"))
            .group_by(col(ProjectMember.project_id))
            .subquery()
        )
