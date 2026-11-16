"""add project scale bounds check

Revision ID: c4e8a1f7b265
Revises: e7b3d2a94c18
Create Date: 2026-11-16 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e8a1f7b265"
down_revision: str | Sequence[str] | None = "e7b3d2a94c18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "ck_projects_scale_bounds"

# Same ceiling as the API's MAX_ABS_FUZZY_VALUE, written out so this migration stays
# frozen when that constant changes. PostgreSQL orders NaN above every number, so NaN
# fails the upper test, and both infinities fall outside the range.
_CONDITION = "scale_min >= -1e15 AND scale_min <= 1e15 AND scale_max >= -1e15 AND scale_max <= 1e15"


def upgrade() -> None:
    """Upgrade schema.

    Refuses scale bounds that are NaN, infinite or larger than 1e15 in absolute value,
    so a range width can never overflow to infinity. Fails when an existing project
    already holds such a bound.
    """
    op.create_check_constraint(_CONSTRAINT, "projects", _CONDITION)


def downgrade() -> None:
    """Downgrade schema.

    Drops the constraint, so the database accepts non-finite and huge scale bounds again.
    """
    op.drop_constraint(_CONSTRAINT, "projects", type_="check")
