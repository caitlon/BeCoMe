"""add example project support

Revision ID: c4e81f7a9d23
Revises: 5b9977c1b5c1
Create Date: 2026-08-22 12:00:00.000000

"""

import secrets
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from api.auth.password import hash_password
from api.data.example_project import EXAMPLE_EXPERTS

# revision identifiers, used by Alembic.
revision: str = "c4e81f7a9d23"
down_revision: str | Sequence[str] | None = "5b9977c1b5c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Adds the two flags the example-project feature runs on and creates the pool of
    service accounts that hold its expert opinions.

    The pool is created here rather than by the application so that no two concurrent
    activations can race to insert the same account. Each row is inserted already
    verified: an account with a NULL ``email_verified_at`` is what registration treats
    as an unfinished signup, and it would hand anyone who registers that address an
    activation link to a service account that sits in every user's example project.
    One bcrypt hash of 64 random bytes is shared by all of them -- the plaintext is
    never held anywhere, so no password can ever match.
    """
    op.add_column(
        "users",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "projects",
        sa.Column("is_example", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    demo_accounts = sa.table(
        "users",
        sa.column("id", sa.Uuid()),
        sa.column("email", sa.String()),
        sa.column("hashed_password", sa.String()),
        sa.column("first_name", sa.String()),
        sa.column("last_name", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("email_verified_at", sa.DateTime()),
        sa.column("is_demo", sa.Boolean()),
    )
    unusable_password = hash_password(secrets.token_urlsafe(64))
    created = datetime.now(UTC).replace(tzinfo=None)
    op.bulk_insert(
        demo_accounts,
        [
            {
                "id": expert.user_id,
                "email": expert.email,
                "hashed_password": unusable_password,
                "first_name": expert.first_name,
                "last_name": expert.last_name,
                "created_at": created,
                "email_verified_at": created,
                "is_demo": True,
            }
            for expert in EXAMPLE_EXPERTS
        ],
    )


def downgrade() -> None:
    """Downgrade schema.

    Example projects go first: dropping ``is_example`` would otherwise leave them
    indistinguishable from real work, and deleting the demo accounts would strip them
    of their opinions and leave a project claiming 14 members with one.
    """
    op.execute(sa.text("DELETE FROM projects WHERE is_example = true"))
    op.execute(sa.text("DELETE FROM users WHERE is_demo = true"))
    op.drop_column("projects", "is_example")
    op.drop_column("users", "is_demo")
