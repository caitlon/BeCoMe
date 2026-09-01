"""stop storing the likert verdict

Revision ID: d5c1a7e93b02
Revises: a8d7ba4fcdde
Create Date: 2026-09-01 21:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5c1a7e93b02"
down_revision: str | Sequence[str] | None = "a8d7ba4fcdde"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    The agreement verdict is a pure function of the project's scale and the compromise
    triple, both of which this table and ``projects`` already hold. Storing it as well
    made it a cache, and the cache had no invalidation: editing a project's scale
    rewrote ``projects`` and left ``likert_value`` and ``likert_decision`` untouched, so
    a budget or a percentage kept an agreement sentence attached to it. Revision
    ``a8d7ba4fcdde`` cleaned exactly those rows once, and the application went on
    producing them, because ``update_project`` never called a recalculation.

    Dropping the columns removes the class of defect rather than one path into it.
    ``api/services/likert_verdict.py`` derives the verdict on every read instead, which
    costs one comparison and one interpretation and needs no expert opinions.
    """
    with op.batch_alter_table("calculation_results") as batch:
        batch.drop_constraint("ck_calculation_results_likert_range", type_="check")
        batch.drop_column("likert_decision")
        batch.drop_column("likert_value")


def downgrade() -> None:
    """Downgrade schema.

    Restores the columns and the range check, but not the values: they are derived, and
    the code that wrote them is gone. Every row comes back with NULL in both, which is
    the same state a project that is not on an agreement scale always had. Nothing is
    lost by that, because anything reading these columns can compute them from the row
    it is already holding.
    """
    with op.batch_alter_table("calculation_results") as batch:
        batch.add_column(sa.Column("likert_value", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("likert_decision", sa.String(length=100), nullable=True))
        batch.create_check_constraint(
            "ck_calculation_results_likert_range",
            "likert_value IS NULL OR (likert_value >= 0 AND likert_value <= 100)",
        )
