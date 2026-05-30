"""hash password reset token

Revision ID: f3a7c2b9d1e4
Revises: c83186b79ad7
Create Date: 2026-05-30 22:44:02.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a7c2b9d1e4"
down_revision: str | Sequence[str] | None = "c83186b79ad7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    password_reset_tokens is an empty scaffold; replace the raw ``token`` column
    with a SHA-256 ``token_hash`` so a database leak never exposes a usable token.
    """
    op.drop_index(op.f("ix_password_reset_tokens_token"), table_name="password_reset_tokens")
    op.drop_column("password_reset_tokens", "token")
    op.add_column(
        "password_reset_tokens",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
    )
    op.create_index(
        op.f("ix_password_reset_tokens_token_hash"),
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_password_reset_tokens_token_hash"), table_name="password_reset_tokens"
    )
    op.drop_column("password_reset_tokens", "token_hash")
    op.add_column(
        "password_reset_tokens",
        sa.Column("token", sa.Uuid(), nullable=False),
    )
    op.create_index(
        op.f("ix_password_reset_tokens_token"),
        "password_reset_tokens",
        ["token"],
        unique=True,
    )
