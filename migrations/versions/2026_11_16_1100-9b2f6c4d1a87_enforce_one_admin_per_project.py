"""enforce one admin per project

Revision ID: 9b2f6c4d1a87
Revises: c4e8a1f7b265
Create Date: 2026-11-16 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9b2f6c4d1a87"
down_revision: str | Sequence[str] | None = "c4e8a1f7b265"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ONE_ADMIN_INDEX = "uq_project_members_one_admin"
_ONE_ADMIN_PREDICATE = "role = 'ADMIN'"
_MEMBERSHIP_UNIQUE = "uq_project_members_project_user_role"
_ADMIN_ROLE_CHECK = "ck_projects_admin_role_is_admin"
_ADMIN_ROLE_CONDITION = "admin_role = 'ADMIN'"
_ADMIN_FK = "fk_projects_admin_membership"


def upgrade() -> None:
    """Upgrade schema.

    Ties projects.admin_id to the project's one ADMIN membership. The partial unique
    index allows at most one ADMIN row per project. projects.admin_role is pinned to
    'ADMIN' by a CHECK, and the deferred composite foreign key from
    (id, admin_id, admin_role) to project_members (project_id, user_id, role) then
    makes the admin_id user hold that ADMIN row. A transfer demotes the old admin and
    promotes the new one inside one transaction, and the checks run at commit.

    Fails when an existing project has no ADMIN row, two of them, or an ADMIN other
    than admin_id, because the objects are created without NOT VALID.
    """
    op.create_index(
        _ONE_ADMIN_INDEX,
        "project_members",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text(_ONE_ADMIN_PREDICATE),
    )
    op.create_unique_constraint(
        _MEMBERSHIP_UNIQUE, "project_members", ["project_id", "user_id", "role"]
    )
    op.add_column(
        "projects",
        sa.Column(
            "admin_role",
            postgresql.ENUM(name="memberrole", create_type=False),
            nullable=False,
            server_default="ADMIN",
        ),
    )
    op.create_check_constraint(_ADMIN_ROLE_CHECK, "projects", _ADMIN_ROLE_CONDITION)
    op.create_foreign_key(
        _ADMIN_FK,
        "projects",
        "project_members",
        ["id", "admin_id", "admin_role"],
        ["project_id", "user_id", "role"],
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    """Downgrade schema.

    Drops the five objects in reverse order, so a project may again have no ADMIN row,
    several of them, or an ADMIN other than admin_id. The memberrole type stays, because
    project_members.role still uses it.
    """
    op.drop_constraint(_ADMIN_FK, "projects", type_="foreignkey")
    op.drop_constraint(_ADMIN_ROLE_CHECK, "projects", type_="check")
    op.drop_column("projects", "admin_role")
    op.drop_constraint(_MEMBERSHIP_UNIQUE, "project_members", type_="unique")
    op.drop_index(_ONE_ADMIN_INDEX, table_name="project_members")
