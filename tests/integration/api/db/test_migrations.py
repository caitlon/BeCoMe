"""Migration tests: run Alembic against a clean PostgreSQL database.

These exercise the migration scripts themselves (upgrade/downgrade), not just the
models, so a reversible schema change is proven end to end. Skipped when
PostgreSQL is not installed.
"""

import shutil
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.skipif(
    not shutil.which("pg_ctl"),
    reason="PostgreSQL not installed (pg_ctl not found in PATH)",
)

_TOKENS = "email_verification_tokens"

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
            # WHEN - migrated up to (and including) this migration. Pinned to its
            # own revision id rather than "head": later migrations land on top of
            # this one, and "head"/"-1" addressing would silently start exercising
            # them instead of the RESTRICT change this test is about.
            command.upgrade(config, "b1d9f4a2c7e3")

            # THEN - admin_id is protected by RESTRICT
            assert _delete_rule(engine, "projects_admin_id_fkey") == "RESTRICT"

            # WHEN - this migration is rolled back to its own down_revision
            command.downgrade(config, "f3a7c2b9d1e4")

            # THEN - the constraint reverts to CASCADE (downgrade works)
            assert _delete_rule(engine, "projects_admin_id_fkey") == "CASCADE"

            # WHEN - re-applied (reversibility holds)
            command.upgrade(config, "b1d9f4a2c7e3")

            # THEN
            assert _delete_rule(engine, "projects_admin_id_fkey") == "RESTRICT"
        finally:
            engine.dispose()


class TestEmailVerificationMigration:
    """The migration adding email_verified_at and email_verification_tokens."""

    def test_upgrade_backfills_existing_users_and_downgrade_reverts(
        self, migration_pg, monkeypatch
    ):
        """A pre-existing user is backfilled to verified, and the migration reverses cleanly."""
        # GIVEN - a database migrated up to the revision just before this one
        url = _url(migration_pg)
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
        config = Config("alembic.ini")
        engine = create_engine(url)

        try:
            command.upgrade(config, "b1d9f4a2c7e3")

            # A user row as it existed before email_verified_at was added
            user_id = uuid4()
            created_at = datetime(2026, 1, 1, tzinfo=UTC)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO users "
                        "(id, email, hashed_password, first_name, last_name, created_at) "
                        "VALUES (:id, :email, :hashed_password, :first_name, :last_name, "
                        ":created_at)"
                    ),
                    {
                        "id": str(user_id),
                        "email": "preexisting@example.com",
                        "hashed_password": "hash",
                        "first_name": "Pre",
                        "last_name": "Existing",
                        "created_at": created_at,
                    },
                )

            # WHEN - the email verification migration is applied. Pinned to its own
            # revision id rather than "head" for the same reason as the RESTRICT
            # migration above: a later migration landing on top would otherwise
            # silently change what this test exercises.
            command.upgrade(config, "21261c13bb2b")

            # THEN - the pre-existing row is backfilled to its own created_at
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT email_verified_at, created_at FROM users WHERE id = :id"),
                    {"id": str(user_id)},
                ).one()
            assert row.email_verified_at == row.created_at

            # AND - a token can carry the submission it was minted for
            token_columns = {c["name"] for c in inspect(engine).get_columns(_TOKENS)}
            assert {"hashed_password", "first_name", "last_name"} <= token_columns

            # WHEN - the migration is rolled back to its own down_revision (pinned,
            # not "-1", for the same reason)
            command.downgrade(config, "b1d9f4a2c7e3")

            # THEN - the column and the token table are gone (downgrade works)
            inspector = inspect(engine)
            columns = [c["name"] for c in inspector.get_columns("users")]
            assert "email_verified_at" not in columns
            assert _TOKENS not in inspector.get_table_names()

            # WHEN - re-applied (reversibility holds)
            command.upgrade(config, "21261c13bb2b")

            # THEN
            assert _TOKENS in inspect(engine).get_table_names()
        finally:
            engine.dispose()

    def test_a_token_cannot_carry_half_a_submission(self, migration_pg, monkeypatch):
        """The three credential columns are written together or not at all.

        Redemption treats them as one value, so a row with only some of them set would
        activate an account with a password and somebody else's name still on it.
        """
        # GIVEN - a database at this migration, holding one account
        url = _url(migration_pg)
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
        engine = create_engine(url)

        try:
            command.upgrade(Config("alembic.ini"), "21261c13bb2b")
            user_id = uuid4()
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO users "
                        "(id, email, hashed_password, first_name, last_name, created_at) "
                        "VALUES (:id, 'partial@example.com', 'hash', 'Part', 'Ial', :created_at)"
                    ),
                    {"id": str(user_id), "created_at": datetime(2026, 1, 1, tzinfo=UTC)},
                )

            # WHEN / THEN - a token with a password but no names is rejected
            with pytest.raises(IntegrityError, match="credentials_complete"), engine.begin() as c:
                c.execute(
                    text(
                        f"INSERT INTO {_TOKENS} "  # noqa: S608 - constant table name
                        "(id, user_id, token_hash, hashed_password, created_at, expires_at) "
                        "VALUES (:id, :user_id, :token_hash, 'a-hash', :now, :now)"
                    ),
                    {
                        "id": str(uuid4()),
                        "user_id": str(user_id),
                        "token_hash": "a" * 64,
                        "now": datetime(2026, 1, 1, tzinfo=UTC),
                    },
                )
        finally:
            engine.dispose()
