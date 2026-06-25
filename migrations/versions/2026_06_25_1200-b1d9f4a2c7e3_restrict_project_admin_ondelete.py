"""restrict project admin ondelete

Revision ID: b1d9f4a2c7e3
Revises: f3a7c2b9d1e4
Create Date: 2026-06-25 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1d9f4a2c7e3"
down_revision: str | Sequence[str] | None = "f3a7c2b9d1e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAME = "projects_admin_id_fkey"


def upgrade() -> None:
    """Upgrade schema.

    Switch ``projects.admin_id`` from ON DELETE CASCADE to ON DELETE RESTRICT so a
    user who still admins a project cannot be deleted, which would otherwise wipe
    that project and every other expert's contribution in it. The API rejects such
    deletes with 409 first (see ``delete_current_user``); this is the DB backstop.
    """
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint(_FK_NAME, type_="foreignkey")
        batch_op.create_foreign_key(_FK_NAME, "users", ["admin_id"], ["id"], ondelete="RESTRICT")


def downgrade() -> None:
    """Downgrade schema (restore ON DELETE CASCADE)."""
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint(_FK_NAME, type_="foreignkey")
        batch_op.create_foreign_key(_FK_NAME, "users", ["admin_id"], ["id"], ondelete="CASCADE")
