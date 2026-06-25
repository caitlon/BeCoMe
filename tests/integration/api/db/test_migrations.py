"""Migration tests: run Alembic against a clean PostgreSQL database.

These exercise the migration scripts themselves (upgrade/downgrade), not just the
models, so a reversible schema change is proven end to end. Skipped when
PostgreSQL is not installed.
"""

import shutil

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

    migration_pg_proc = factories.postgresql_proc()
    migration_pg = factories.postgresql("migration_pg_proc")
except ImportError:
    migration_pg_proc = None
    migration_pg = None


def _url(pg) -> str:
    """Build a psycopg2 URL for the temporary database."""
    return f"postgresql+psycopg2://{pg.info.user}:@{pg.info.host}:{pg.info.port}/{pg.info.dbname}"


def _delete_rule(engine, constraint_name: str) -> str | None:
    """Return the ON DELETE rule of a foreign key from information_schema."""
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT delete_rule FROM information_schema.referential_constraints "
                "WHERE constraint_name = :name"
            ),
            {"name": constraint_name},
        ).scalar()


class TestProjectAdminRestrictMigration:
    """The migration switching projects.admin_id to ON DELETE RESTRICT."""

    def test_upgrade_sets_restrict_and_downgrade_restores_cascade(self, migration_pg, monkeypatch):
        """upgrade applies RESTRICT, downgrade reverts to CASCADE, and it is reversible."""
        # GIVEN - a clean database with Alembic aimed at it
        url = _url(migration_pg)
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
        config = Config("alembic.ini")
        engine = create_engine(url)

        try:
            # WHEN - the full migration chain is applied
            command.upgrade(config, "head")

            # THEN - admin_id is protected by RESTRICT
            assert _delete_rule(engine, "projects_admin_id_fkey") == "RESTRICT"

            # WHEN - the RESTRICT migration is rolled back one step
            command.downgrade(config, "-1")

            # THEN - the constraint reverts to CASCADE (downgrade works)
            assert _delete_rule(engine, "projects_admin_id_fkey") == "CASCADE"

            # WHEN - re-applied (reversibility holds)
            command.upgrade(config, "head")

            # THEN
            assert _delete_rule(engine, "projects_admin_id_fkey") == "RESTRICT"
        finally:
            engine.dispose()
