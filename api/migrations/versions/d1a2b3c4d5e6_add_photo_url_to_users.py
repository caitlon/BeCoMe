"""add photo_url to users

Revision ID: d1a2b3c4d5e6
Revises: c8f3a2b95d41
Create Date: 2026-01-22 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "c8f3a2b95d41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add photo_url column to users table."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("photo_url", sa.VARCHAR(length=500), nullable=True))


def downgrade() -> None:
    """Remove photo_url column from users table."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("photo_url")
