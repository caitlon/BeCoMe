"""Migration test: text stored HTML-escaped is decoded, and the downgrade escapes it again.

Runs Alembic against a clean PostgreSQL database, where the column limits apply. Skipped
when PostgreSQL is not installed.
"""

import shutil
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.skipif(
    not shutil.which("pg_ctl"),
    reason="PostgreSQL not installed (pg_ctl not found in PATH)",
)

# A clean database with no schema preloaded, so Alembic owns every table.
try:
    from pytest_postgresql import factories

    unescape_pg_proc = factories.postgresql_proc()
    unescape_pg = factories.postgresql("unescape_pg_proc")
except ImportError:
    unescape_pg_proc = None
    unescape_pg = None

# Pinned to the revision ids, so a later migration cannot change what is tested.
BEFORE = "9b2f6c4d1a87"  # pragma: allowlist secret
REVISION = "3d7a9e5c1f42"  # pragma: allowlist secret

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _url(pg) -> str:
    """Build a psycopg2 URL for the temporary database."""
    return f"postgresql+psycopg2://{pg.info.user}:@{pg.info.host}:{pg.info.port}/{pg.info.dbname}"


def _insert_user(conn, name: str):
    """Insert one user and return its id."""
    user_id = uuid4()
    conn.execute(
        text(
            "INSERT INTO users (id, email, hashed_password, first_name, last_name, created_at) "
            "VALUES (:id, :email, 'hash', :name, 'User', :now)"
        ),
        {"id": str(user_id), "email": f"{name}@example.com", "name": name, "now": _NOW},
    )
    return user_id


def _insert_project(conn, admin_id, name: str, description: str | None, scale_unit: str):
    """Insert one project with its ADMIN membership and return its id."""
    project_id = uuid4()
    conn.execute(
        text(
            "INSERT INTO projects "
            "(id, name, description, admin_id, scale_min, scale_max, scale_unit, "
            "created_at, updated_at) "
            "VALUES (:id, :name, :description, :admin_id, 0, 100, :scale_unit, :now, :now)"
        ),
        {
            "id": str(project_id),
            "name": name,
            "description": description,
            "admin_id": str(admin_id),
            "scale_unit": scale_unit,
            "now": _NOW,
        },
    )
    conn.execute(
        text(
            "INSERT INTO project_members (id, project_id, user_id, role, joined_at) "
            "VALUES (:id, :project_id, :user_id, 'ADMIN', :now)"
        ),
        {"id": str(uuid4()), "project_id": str(project_id), "user_id": str(admin_id), "now": _NOW},
    )
    return project_id


def _insert_opinion(conn, project_id, user_id, position: str) -> None:
    """Insert one expert opinion."""
    conn.execute(
        text(
            "INSERT INTO expert_opinions "
            "(id, project_id, user_id, position, lower_bound, peak, upper_bound, "
            "created_at, updated_at) "
            "VALUES (:id, :project_id, :user_id, :position, 1, 2, 3, :now, :now)"
        ),
        {
            "id": str(uuid4()),
            "project_id": str(project_id),
            "user_id": str(user_id),
            "position": position,
            "now": _NOW,
        },
    )


def _project_row(conn, project_id) -> tuple[str, str | None, str]:
    """Read (name, description, scale_unit) of one project."""
    row = conn.execute(
        text("SELECT name, description, scale_unit FROM projects WHERE id = :id"),
        {"id": str(project_id)},
    ).one()
    return row.name, row.description, row.scale_unit


def _position(conn, project_id) -> str:
    """Read the position of the one opinion of a project."""
    return conn.execute(
        text("SELECT position FROM expert_opinions WHERE project_id = :id"),
        {"id": str(project_id)},
    ).scalar_one()


class TestUnescapeStoredTextMigration:
    """The data migration decoding the entities bleach used to store."""

    @staticmethod
    def _migrated(unescape_pg, monkeypatch):
        """Point Alembic at the clean database, upgrade it to BEFORE, return (config, engine)."""
        url = _url(unescape_pg)
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
        config = Config("alembic.ini")
        command.upgrade(config, BEFORE)
        return config, create_engine(url)

    def test_upgrade_decodes_and_downgrade_escapes_again(self, unescape_pg, monkeypatch):
        """
        GIVEN rows that hold the escaped form in all four columns and a row of plain text
        WHEN the migration is applied and then rolled back
        THEN the entities are decoded once (`&amp;lt;` becomes the text `&lt;`), the plain row
        and the NULL description stay unchanged, and the downgrade escapes the characters again
        """
        # GIVEN
        config, engine = self._migrated(unescape_pg, monkeypatch)

        try:
            with engine.begin() as conn:
                admin_id = _insert_user(conn, "admin")
                escaped = _insert_project(
                    conn, admin_id, "R&amp;D", "a &lt;b&gt; c &amp;amp; d &amp;lt; e", "&lt;="
                )
                _insert_opinion(conn, escaped, admin_id, "Q&amp;A lead")
                other_id = _insert_user(conn, "other")
                plain = _insert_project(conn, other_id, "Plain name", None, "kg")
                _insert_opinion(conn, plain, other_id, "Plain position")

            # WHEN
            command.upgrade(config, REVISION)

            # THEN
            with engine.connect() as conn:
                assert _project_row(conn, escaped) == ("R&D", "a <b> c &amp; d &lt; e", "<=")
                assert _position(conn, escaped) == "Q&A lead"
                assert _project_row(conn, plain) == ("Plain name", None, "kg")
                assert _position(conn, plain) == "Plain position"

            # WHEN
            command.downgrade(config, BEFORE)

            # THEN: the old storage form, not byte for byte the old rows
            with engine.connect() as conn:
                assert _project_row(conn, escaped) == (
                    "R&amp;D",
                    "a &lt;b&gt; c &amp;amp; d &amp;lt; e",
                    "&lt;=",
                )
                assert _position(conn, escaped) == "Q&amp;A lead"
                assert _project_row(conn, plain) == ("Plain name", None, "kg")
                assert _position(conn, plain) == "Plain position"
        finally:
            engine.dispose()

    def test_downgrade_leaves_a_value_that_would_not_fit_its_column(self, unescape_pg, monkeypatch):
        """
        GIVEN a name of 255 ampersands and a position of 255 of them, as the new code may store
        WHEN the migration is rolled back
        THEN both stay as they are, because their escaped form would exceed the column limit,
        while a short value in the same column is still escaped
        """
        # GIVEN
        config, engine = self._migrated(unescape_pg, monkeypatch)
        command.upgrade(config, REVISION)

        try:
            with engine.begin() as conn:
                admin_id = _insert_user(conn, "admin")
                full = _insert_project(conn, admin_id, "&" * 255, "&" * 300, "&" * 10)
                _insert_opinion(conn, full, admin_id, "&" * 255)
                other_id = _insert_user(conn, "other")
                short = _insert_project(conn, other_id, "R&D", None, "&")

            # WHEN
            command.downgrade(config, BEFORE)

            # THEN
            with engine.connect() as conn:
                name, description, scale_unit = _project_row(conn, full)
                assert name == "&" * 255
                assert description == "&amp;" * 300
                assert scale_unit == "&amp;" * 10
                assert _position(conn, full) == "&" * 255
                assert _project_row(conn, short) == ("R&amp;D", None, "&amp;")
        finally:
            engine.dispose()
