"""add assistant objection to users

Revision ID: e7b3d2a94c18
Revises: d5c1a7e93b02
Create Date: 2026-10-18 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7b3d2a94c18"
down_revision: str | Sequence[str] | None = "d5c1a7e93b02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Adds the flag a user sets to object, under GDPR Article 21, to the assistant reading
    their opinions on behalf of other project members. Every existing account starts
    without an objection.
    """
    op.add_column(
        "users",
        sa.Column(
            "assistant_objection", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    Drops the flag. Any objection recorded since the upgrade is lost, so the assistant
    would read those users' opinions again for other members.
    """
    op.drop_column("users", "assistant_objection")
