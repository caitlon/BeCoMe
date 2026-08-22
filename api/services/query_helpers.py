"""Query helpers for reusable database query patterns."""

from sqlalchemy.sql.selectable import Subquery
from sqlmodel import col, func, select
from sqlmodel.sql.expression import SelectOfScalar

from api.db.models import ProjectMember, User


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


def select_account_by_email(email: str) -> SelectOfScalar[User]:
    """Build the statement that resolves an email address to a real account.

    Demo accounts are excluded here rather than at each call site. They exist only to
    hold the opinions in the seeded example project, and every path that resolves an
    address -- login, registration, invitation, password reset, activation resend --
    has to answer for them exactly as it answers for an address nobody registered.
    Each of those paths already answers identically for a missing account, so the
    exclusion adds no way to probe whether a demo address exists.

    :param email: Email address, matched case-insensitively.
    :return: Statement selecting the matching account, demo accounts excluded.
    """
    return select(User).where(User.email == email.lower(), col(User.is_demo).is_(False))
