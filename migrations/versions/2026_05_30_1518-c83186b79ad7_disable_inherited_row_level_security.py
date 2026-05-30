"""disable inherited row level security

Revision ID: c83186b79ad7
Revises: 189d6f6fea7b
Create Date: 2026-05-30 15:18:55.021428

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c83186b79ad7"
down_revision: str | Sequence[str] | None = "189d6f6fea7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables imported from Supabase with row-level security enabled and forced but
# no policies. That is a no-op for a superuser but denies all access to a
# least-privilege role; authorization is enforced in the application layer
# (api/dependencies.py), so RLS is removed here.
_TABLES: tuple[str, ...] = (
    "users",
    "projects",
    "project_members",
    "invitations",
    "expert_opinions",
    "password_reset_tokens",
    "calculation_results",
)


def upgrade() -> None:
    """Drop the inherited forced row-level security (PostgreSQL only)."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Restore forced row-level security without policies (PostgreSQL only)."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
