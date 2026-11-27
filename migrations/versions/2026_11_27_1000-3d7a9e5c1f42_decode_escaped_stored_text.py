"""decode escaped stored text

Revision ID: 3d7a9e5c1f42
Revises: 9b2f6c4d1a87
Create Date: 2026-11-27 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3d7a9e5c1f42"
down_revision: str | Sequence[str] | None = "9b2f6c4d1a87"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every column that sanitize_text cleans: (table, column, maximum length or None).
_COLUMNS: tuple[tuple[str, str, int | None], ...] = (
    ("projects", "name", 255),
    ("projects", "description", None),
    ("projects", "scale_unit", 50),
    ("expert_opinions", "position", 255),
)


def _unescape(column: str) -> str:
    """Return the SQL that turns the three entities back into characters.

    The ampersand comes last, so ``&amp;lt;`` becomes the text ``&lt;`` and not ``<``.
    """
    return f"replace(replace(replace({column}, '&lt;', '<'), '&gt;', '>'), '&amp;', '&')"


def _escape(column: str) -> str:
    """Return the SQL that escapes the three characters the way bleach did.

    The ampersand comes first, so the entities it adds are not escaped a second time.
    """
    return f"replace(replace(replace({column}, '&', '&amp;'), '<', '&lt;'), '>', '&gt;')"


def upgrade() -> None:
    """Upgrade schema.

    Before the sanitizer stopped HTML-escaping, bleach stored ``&``, ``<`` and ``>`` in
    project names, descriptions and units and in opinion positions as ``&amp;``, ``&lt;``
    and ``&gt;``, and every reader escapes again on output, so "R&D" showed as "R&amp;D".
    This decodes the three entities once. Bleach's output never held a bare ``<`` or ``>``,
    and it escaped every ``&`` except one that looked like the start of an entity
    (``AT&T;``); only the three exact entities are replaced, so such text is left as it is.
    The text is plain SQL and imports no application code, so it does not change when the
    sanitizer does.

    A save by the previous application version between this migration and the new version
    going live stores the old escaped form, which this migration does not see; such a row
    keeps its entities.

    Accepted: an entity a user typed on purpose before the change (``&lt;b&gt;``) is
    decoded too, because bleach's own output looks the same. A decoded value may hold
    tag-like text, which is harmless because every reader escapes, and the next save
    cleans it. Decoded text is never longer than the escaped text, so it always fits.
    """
    for table, column, _ in _COLUMNS:
        op.execute(
            sa.text(
                f"UPDATE {table} SET {column} = {_unescape(column)} "  # noqa: S608
                f"WHERE {column} LIKE '%&%' AND {column} <> {_unescape(column)}"
            )
        )


def downgrade() -> None:
    """Downgrade schema.

    Escapes the three characters again, which restores the old storage form but not
    byte for byte the old rows: an entity typed on purpose, such as ``&lt;``, comes back
    as ``&amp;lt;``. Escaping makes text longer, so in a bounded column a row is only
    changed when the escaped value fits; one that would not fit stays as it is, since the
    old code could never have stored it.
    """
    for table, column, max_length in _COLUMNS:
        fits = f" AND length({_escape(column)}) <= {max_length}" if max_length else ""
        op.execute(
            sa.text(
                f"UPDATE {table} SET {column} = {_escape(column)} "  # noqa: S608
                f"WHERE ({column} LIKE '%&%' OR {column} LIKE '%<%' OR {column} LIKE '%>%')"
                f"{fits}"
            )
        )
