"""Read the tenant tables back as plain values, to prove a request changed nothing.

A refused request must leave the database as it found it. Comparing row counts alone
would miss an update, so the snapshot holds every column of every row, in a stable order.
"""

from typing import Any

from sqlmodel import Session, SQLModel, select

from api.db.models import (
    CalculationResult,
    ExpertOpinion,
    Invitation,
    Project,
    ProjectMember,
    User,
)

TENANT_TABLES: tuple[type[SQLModel], ...] = (
    User,
    Project,
    ProjectMember,
    ExpertOpinion,
    Invitation,
    CalculationResult,
)


def snapshot(session: Session) -> dict[str, list[dict[str, Any]]]:
    """Dump the users, projects, memberships, opinions, invitations and saved results.

    :param session: Session bound to the engine the test app writes through.
    :return: Table name mapped to its rows as JSON-compatible dicts, ordered by id.
    """
    return {
        table.__name__: sorted(
            (row.model_dump(mode="json") for row in session.exec(select(table)).all()),
            key=lambda row: row["id"],
        )
        for table in TENANT_TABLES
    }
