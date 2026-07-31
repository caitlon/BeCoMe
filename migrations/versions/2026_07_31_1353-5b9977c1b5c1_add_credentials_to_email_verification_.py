"""add credentials to email verification tokens

Revision ID: 5b9977c1b5c1
Revises: 21261c13bb2b
Create Date: 2026-07-31 13:53:10.228590

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b9977c1b5c1"
down_revision: str | Sequence[str] | None = "21261c13bb2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Add ``hashed_password``, ``first_name``, and ``last_name`` to
    ``email_verification_tokens``: an activation link carries the credentials of
    the submission that minted it, so redeeming the link applies that submission's
    credentials rather than whatever currently sits on the user row. That is what
    stops one person's registration from activating on another person's password.
    The columns are NOT NULL with no server default, so the table is cleared first
    -- nothing mints a token until this ships, but a row that somehow predates this
    migration would carry no credentials and be unusable by the redeeming code.
    """
    op.execute(sa.text("DELETE FROM email_verification_tokens"))

    op.add_column(
        "email_verification_tokens",
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
    )
    op.add_column(
        "email_verification_tokens",
        sa.Column("first_name", sa.String(length=100), nullable=False),
    )
    op.add_column(
        "email_verification_tokens",
        sa.Column("last_name", sa.String(length=100), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("email_verification_tokens", "last_name")
    op.drop_column("email_verification_tokens", "first_name")
    op.drop_column("email_verification_tokens", "hashed_password")
