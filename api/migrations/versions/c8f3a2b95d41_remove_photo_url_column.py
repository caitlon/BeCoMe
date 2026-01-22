"""remove photo_url column

Revision ID: c8f3a2b95d41
Revises: bbb52b428242
Create Date: 2026-01-22 19:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8f3a2b95d41"
down_revision: str | Sequence[str] | None = "bbb52b428242"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove photo_url column from users table."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("photo_url")


def downgrade() -> None:
    """Re-add photo_url column to users table."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("photo_url", sa.VARCHAR(length=500), nullable=True))
