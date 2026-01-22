"""make last_name required

Revision ID: bbb52b428242
Revises:
Create Date: 2026-01-22 16:20:02.052754

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bbb52b428242"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Make last_name column NOT NULL."""
    # SQLite requires batch mode for ALTER COLUMN
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("last_name", existing_type=sa.VARCHAR(length=100), nullable=False)


def downgrade() -> None:
    """Revert last_name to nullable."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("last_name", existing_type=sa.VARCHAR(length=100), nullable=True)
