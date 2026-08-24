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

    The keep-or-clear decision is made in Python instead of a SQL ``WHERE`` clause.
    ``_is_likert_scale`` calls a unit empty when ``scale_unit.strip()`` is falsy, and
    Python's ``str.strip()`` removes every whitespace character -- tabs, newlines,
    and more -- while SQL's ``TRIM()`` with no explicit character list removes only
    the plain space, in both PostgreSQL and SQLite. A unit holding a bare tab passes
    the application's rule and must keep its verdict, but a ``TRIM``-based filter
    would leave that tab in place and clear it anyway. Re-running the identical
    Python expression here, instead of a hand-built SQL equivalent, is what keeps
    this migration from drifting away from the rule it exists to mirror.

    The condition itself negates ``_is_likert_scale`` in full rather than naming
    only the 0-100-with-a-unit rows. A project outside the 0-100 range never
    received a verdict in the first place, so both filters touch the same rows
    today. The full negation is used anyway, because it also clears anything odd
    that predates the current logic instead of assuming today's data is the only
    shape that exists.
    """
    connection = op.get_bind()
    candidates = connection.execute(
        sa.text(
            "SELECT cr.project_id, p.scale_min, p.scale_max, p.scale_unit "
            "FROM calculation_results cr JOIN projects p ON p.id = cr.project_id "
            "WHERE cr.likert_value IS NOT NULL OR cr.likert_decision IS NOT NULL"
        )
    ).all()

    # Mirrors CalculationService._is_likert_scale as of this revision, inlined
    # rather than imported from api. so this migration keeps working even after
    # that method changes again -- a migration is a record of what it did the day
    # it ran, not a window onto the application's current logic.
    stale_ids = [
        row.project_id
        for row in candidates
        if not (row.scale_min == 0 and row.scale_max == 100 and not row.scale_unit.strip())
    ]

    if stale_ids:
        connection.execute(
            sa.text(
                "UPDATE calculation_results SET likert_value = NULL, likert_decision = NULL "
                "WHERE project_id IN :ids"
            ).bindparams(sa.bindparam("ids", expanding=True)),
            {"ids": stale_ids},
        )


def downgrade() -> None:
    """Downgrade schema.

    No-op. The verdict this migration clears comes from expert opinions that
    ``calculation_results`` never stores, so the original ``likert_value`` and
    ``likert_decision`` cannot be reconstructed from anything left in this table.
    The application recomputes both the next time ``CalculationService.recalculate``
    runs for the project.
    """
