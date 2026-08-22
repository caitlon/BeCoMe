"""add example project support

Revision ID: c4e81f7a9d23
Revises: 5b9977c1b5c1
Create Date: 2026-08-22 12:00:00.000000

"""

import secrets
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

from api.auth.password import hash_password

# revision identifiers, used by Alembic.
revision: str = "c4e81f7a9d23"
down_revision: str | Sequence[str] | None = "5b9977c1b5c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of api.data.example_project.EXAMPLE_EXPERTS (id, email, first name, last
# name) as it stood when this migration was written. A migration is a record of what
# it did the day it ran, not a window onto the application's current state: importing
# EXAMPLE_EXPERTS here would let a later change to the live roster -- a 14th expert, a
# renamed one -- retroactively change what this already-applied migration is defined
# to have inserted, so a database migrated today would silently diverge from one
# migrated after that change even though both ran the exact same migration file. A
# roster change belongs in a migration of its own. Do not replace this with
# ``from api.data.example_project import EXAMPLE_EXPERTS``.
_DEMO_EXPERTS: tuple[tuple[UUID, str, str, str], ...] = (
    (
        UUID("922f3d9b-20be-461f-9b69-90928701ce93"),
        "jana.novakova@example.invalid",
        "Jana",
        "Nováková",
    ),
    (
        UUID("2458e540-24e4-46e5-b2cf-6caac4b9c637"),
        "petr.svoboda@example.invalid",
        "Petr",
        "Svoboda",
    ),
    (
        UUID("a15919aa-5727-4fb9-84e9-2980007cfc58"),
        "marie.dvorakova@example.invalid",
        "Marie",
        "Dvořáková",
    ),
    (UUID("7ec7b7c3-126b-412a-babf-fd79d002e921"), "tomas.cerny@example.invalid", "Tomáš", "Černý"),
    (
        UUID("9b8d41e8-ad45-4b7d-a541-38d781be09da"),
        "lucie.prochazkova@example.invalid",
        "Lucie",
        "Procházková",
    ),
    (UUID("d171a368-ea6a-45f5-9b66-6767052fe916"), "jan.kucera@example.invalid", "Jan", "Kučera"),
    (UUID("923c3a06-0b09-4573-a4da-142c606ae61e"), "eva.vesela@example.invalid", "Eva", "Veselá"),
    (
        UUID("1a530254-57f0-4a8d-adb9-7d5520153f50"),
        "martin.horak@example.invalid",
        "Martin",
        "Horák",
    ),
    (
        UUID("d5bb3746-fdf8-424d-ba9d-3d7d407756a9"),
        "tereza.nemcova@example.invalid",
        "Tereza",
        "Němcová",
    ),
    (UUID("624423f1-04b4-404c-8d55-d1cb82fa8ae4"), "pavel.marek@example.invalid", "Pavel", "Marek"),
    (
        UUID("9f48758c-53ae-4d68-a454-d9c10767104e"),
        "hana.pokorna@example.invalid",
        "Hana",
        "Pokorná",
    ),
    (UUID("329f1e51-a2ee-4d24-ab04-a7720bf3eac7"), "jiri.krejci@example.invalid", "Jiří", "Krejčí"),
    (
        UUID("db3205fc-c11b-431e-950e-573c5bcb4013"),
        "zuzana.blahova@example.invalid",
        "Zuzana",
        "Bláhová",
    ),
)


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
                "id": user_id,
                "email": email,
                "hashed_password": unusable_password,
                "first_name": first_name,
                "last_name": last_name,
                "created_at": created,
                "email_verified_at": created,
                "is_demo": True,
            }
            for user_id, email, first_name, last_name in _DEMO_EXPERTS
        ],
    )


def downgrade() -> None:
    """Downgrade schema.

    An example project is seeded into a real account and is editable like any other
    project from then on: its owner may have added their own opinion, or invited real
    colleagues, whose ``ExpertOpinion`` and ``ProjectMember`` rows sit behind CASCADE
    foreign keys and would be destroyed along with the project if it were deleted
    outright. So only an example project touched by nobody but its admin and the demo
    pool is deleted here. An example project that gained any other real member is left
    in place -- once ``is_example`` is dropped below, it becomes an ordinary project,
    which is the honest outcome, since by then it *is* real work.

    Deleting the demo accounts still cascades their own memberships and opinions out
    of every project, spared or not, so a surviving project loses its demo content but
    keeps every real member's own contribution.
    """
    op.execute(
        sa.text(
            "DELETE FROM projects p WHERE p.is_example = true AND NOT EXISTS ("
            "SELECT 1 FROM project_members pm JOIN users u ON u.id = pm.user_id "
            "WHERE pm.project_id = p.id AND u.is_demo = false AND pm.user_id != p.admin_id"
            ")"
        )
    )
    op.execute(sa.text("DELETE FROM users WHERE is_demo = true"))
    op.drop_column("projects", "is_example")
    op.drop_column("users", "is_demo")
