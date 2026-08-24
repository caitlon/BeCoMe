"""clear stale likert verdicts

Revision ID: a8d7ba4fcdde
Revises: c4e81f7a9d23
Create Date: 2026-08-24 14:16:30.109572

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8d7ba4fcdde"
down_revision: str | Sequence[str] | None = "c4e81f7a9d23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    ``CalculationService._is_likert_scale`` now also requires an empty ``scale_unit``.
    Agreement is dimensionless, so a percentage or a budget can share the 0-100 range
    without expressing it. That fix changes only what a future ``recalculate`` stores.
    A row already written under the old rule keeps its stale verdict until something
    recalculates that project again, and both the CSV and PDF exporters read the
    value straight from this table. The example project seeded into every account
    may never get that recalculation, since its owner's opinion is deliberately left
    unseeded.

    The WHERE clause below negates ``_is_likert_scale`` in full rather than naming
    only the 0-100-with-a-unit rows. A project outside the 0-100 range never received
    a verdict in the first place, so both filters touch the same rows today. The full
    negation is used anyway, because it also clears anything odd that predates the
    current logic instead of assuming today's data is the only shape that exists.
    ``TRIM`` is applied to ``scale_unit`` because ``_is_likert_scale`` treats a
    whitespace-only unit as empty too.
    """
    op.execute(
        sa.text(
            "UPDATE calculation_results SET likert_value = NULL, likert_decision = NULL "
            "FROM projects "
            "WHERE projects.id = calculation_results.project_id "
            "AND NOT ("
            "projects.scale_min = 0 AND projects.scale_max = 100 "
            "AND TRIM(projects.scale_unit) = ''"
            ")"
        )
    )


def downgrade() -> None:
    """Downgrade schema.

    No-op. The verdict this migration clears comes from expert opinions that
    ``calculation_results`` never stores, so the original ``likert_value`` and
    ``likert_decision`` cannot be reconstructed from anything left in this table.
    The application recomputes both the next time ``CalculationService.recalculate``
    runs for the project.
    """
