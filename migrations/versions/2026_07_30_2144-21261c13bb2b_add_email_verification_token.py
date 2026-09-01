"""add email verification token

Revision ID: 21261c13bb2b
Revises: b1d9f4a2c7e3
Create Date: 2026-07-30 21:44:51.278099

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "21261c13bb2b"
down_revision: str | Sequence[str] | None = "b1d9f4a2c7e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Add ``email_verified_at`` to ``users`` for the deferred-activation flow: NULL
    means unverified, which the login route will refuse once the release that wires
    that flow up ships. This migration lands the column ahead of it, so between the
    two nothing reads the value. becomify.app already has live users, and the flip
    must not lock them out, so existing rows are backfilled to their own
    ``created_at``, treating pre-existing accounts as verified as of when they
    registered. ``email_verification_tokens``
    mirrors ``password_reset_tokens``, storing only the SHA-256 hash of each
    activation token.
    """
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(), nullable=True))

    op.execute(
        sa.text("UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL")
    )

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_email_verification_tokens_token_hash"),
        "email_verification_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_email_verification_tokens_user_id"),
        "email_verification_tokens",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_email_verification_tokens_user_id"), table_name="email_verification_tokens"
    )
    op.drop_index(
        op.f("ix_email_verification_tokens_token_hash"), table_name="email_verification_tokens"
    )
    op.drop_table("email_verification_tokens")
    op.drop_column("users", "email_verified_at")
