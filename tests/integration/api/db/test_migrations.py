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

from api.data.example_project import EXAMPLE_EXPERTS

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


class TestEmailVerificationCredentialsMigration:
    """The migration adding hashed_password/first_name/last_name to the tokens table.

    Split from the table-creation migration so the two ship in separate pull
    requests: PR 1 creates the empty table, behaviourally inert, and PR 2 adds
    these columns once the code that writes and reads them lands.
    """

    def test_upgrade_adds_not_null_columns_and_downgrade_reverts(self, migration_pg, monkeypatch):
        """The credential columns land as NOT NULL, and the migration reverses cleanly."""
        # GIVEN - a database migrated up to the table-creation revision only, the
        # state PR 1 leaves behind
        url = _url(migration_pg)
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
        config = Config("alembic.ini")
        engine = create_engine(url)

        try:
            command.upgrade(config, "21261c13bb2b")

            # THEN - the table exists, but not yet with the credential columns
            token_columns = {c["name"] for c in inspect(engine).get_columns(_TOKENS)}
            assert not {"hashed_password", "first_name", "last_name"} & token_columns

            # WHEN - this migration is applied. Pinned to its own revision id rather
            # than "head" for the same reason as the migrations above: a later
            # migration landing on top would otherwise silently change what this
            # test exercises.
            command.upgrade(config, "5b9977c1b5c1")

            # THEN - the credential columns exist and are NOT NULL
            columns = {c["name"]: c["nullable"] for c in inspect(engine).get_columns(_TOKENS)}
            assert columns["hashed_password"] is False
            assert columns["first_name"] is False
            assert columns["last_name"] is False

            # WHEN - rolled back to its own down_revision
            command.downgrade(config, "21261c13bb2b")

            # THEN - the credential columns are gone (downgrade works)
            token_columns = {c["name"] for c in inspect(engine).get_columns(_TOKENS)}
            assert not {"hashed_password", "first_name", "last_name"} & token_columns

            # WHEN - re-applied (reversibility holds)
            command.upgrade(config, "5b9977c1b5c1")

            # THEN
            columns = {c["name"]: c["nullable"] for c in inspect(engine).get_columns(_TOKENS)}
            assert columns["last_name"] is False
        finally:
            engine.dispose()

    def test_a_token_cannot_exist_without_a_submission(self, migration_pg, monkeypatch):
        """All three credential columns are required, not merely written together.

        Redemption checks the posted password against ``hashed_password`` and writes
        all three, so a row missing any of them would be a link nobody has to
        authenticate against -- which is the takeover the whole flow closes.
        """
        # GIVEN - a database at this migration, holding one account
        url = _url(migration_pg)
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
        engine = create_engine(url)

        try:
            command.upgrade(Config("alembic.ini"), "5b9977c1b5c1")
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
            with pytest.raises(IntegrityError, match="not-null"), engine.begin() as c:
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


class TestExampleProjectSupportMigration:
    """The migration adding is_example, is_demo and the demo expert pool."""

    def test_upgrade_creates_the_pool_and_downgrade_removes_it(self, migration_pg, monkeypatch):
        """The pool lands already verified, and the migration reverses cleanly.

        The downgrade's project deletion is exercised here too, not left to run
        against an empty ``projects`` table: an untouched example project is
        deleted, an unrelated ordinary project is unaffected, and -- the property
        that matters most -- an example project a real colleague was invited into
        survives, because the CASCADE foreign keys behind it would otherwise take
        that colleague's own membership down along with the demo data.
        """
        # GIVEN - a clean database with Alembic aimed at it
        url = _url(migration_pg)
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
        config = Config("alembic.ini")
        engine = create_engine(url)

        try:
            # WHEN - migrated up to this migration, pinned to its own revision id so
            # a later migration landing on top cannot silently change what is tested
            command.upgrade(config, "c4e81f7a9d23")

            # THEN - every demo account exists, and none of them is claimable through
            # the registration branch that treats an unverified address as pending
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT email, email_verified_at, hashed_password FROM users "
                        "WHERE is_demo = true ORDER BY email"
                    )
                ).all()
            assert len(rows) == len(EXAMPLE_EXPERTS)
            assert all(row.email_verified_at is not None for row in rows)
            assert {row.email for row in rows} == {e.email for e in EXAMPLE_EXPERTS}
            # AND - every row holds a real bcrypt hash, not an empty or placeholder
            # string: hash_password's own output always carries bcrypt's "$2" prefix
            assert all(row.hashed_password.startswith("$2") for row in rows)
            assert all(len(row.hashed_password) >= 50 for row in rows)

            # AND - both flags exist as columns
            inspector = inspect(engine)
            assert "is_demo" in {c["name"] for c in inspector.get_columns("users")}
            assert "is_example" in {c["name"] for c in inspector.get_columns("projects")}

            # GIVEN - a real account with three projects: one untouched example
            # project, one ordinary project, and one example project a real
            # colleague was invited into
            real_admin_id = uuid4()
            real_colleague_id = uuid4()
            untouched_example_id = uuid4()
            ordinary_project_id = uuid4()
            touched_example_id = uuid4()
            created_at = datetime(2026, 1, 1, tzinfo=UTC)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO users "
                        "(id, email, hashed_password, first_name, last_name, created_at) "
                        "VALUES "
                        "(:admin_id, 'real.admin@example.com', 'hash', 'Real', 'Admin', :now), "
                        "(:colleague_id, 'real.colleague@example.com', 'hash', 'Real', "
                        "'Colleague', :now)"
                    ),
                    {
                        "admin_id": str(real_admin_id),
                        "colleague_id": str(real_colleague_id),
                        "now": created_at,
                    },
                )
                conn.execute(
                    text(
                        "INSERT INTO projects "
                        "(id, name, admin_id, scale_min, scale_max, scale_unit, "
                        "created_at, updated_at, is_example) "
                        "VALUES "
                        "(:untouched_id, 'Untouched example', :admin_id, 0, 100, '', "
                        ":now, :now, true), "
                        "(:ordinary_id, 'Ordinary project', :admin_id, 0, 100, '', "
                        ":now, :now, false), "
                        "(:touched_id, 'Touched example', :admin_id, 0, 100, '', "
                        ":now, :now, true)"
                    ),
                    {
                        "untouched_id": str(untouched_example_id),
                        "ordinary_id": str(ordinary_project_id),
                        "touched_id": str(touched_example_id),
                        "admin_id": str(real_admin_id),
                        "now": created_at,
                    },
                )
                conn.execute(
                    text(
                        "INSERT INTO project_members (id, project_id, user_id, role, joined_at) "
                        "VALUES (:id, :project_id, :user_id, 'EXPERT', :now)"
                    ),
                    {
                        "id": str(uuid4()),
                        "project_id": str(touched_example_id),
                        "user_id": str(real_colleague_id),
                        "now": created_at,
                    },
                )

            # WHEN - rolled back to its own down_revision (pinned, not "-1")
            command.downgrade(config, "5b9977c1b5c1")

            # THEN - both columns are gone (downgrade works)
            inspector = inspect(engine)
            assert "is_demo" not in {c["name"] for c in inspector.get_columns("users")}
            assert "is_example" not in {c["name"] for c in inspector.get_columns("projects")}

            # AND - the untouched example project is gone, but the ordinary project
            # and the touched example project both survive. is_example no longer
            # exists at this point, so survivors are identified by id, not the flag.
            with engine.connect() as conn:
                assert (
                    conn.execute(
                        text("SELECT 1 FROM projects WHERE id = :id"),
                        {"id": str(untouched_example_id)},
                    ).scalar()
                    is None
                )
                assert (
                    conn.execute(
                        text("SELECT 1 FROM projects WHERE id = :id"),
                        {"id": str(ordinary_project_id)},
                    ).scalar()
                    == 1
                )
                assert (
                    conn.execute(
                        text("SELECT 1 FROM projects WHERE id = :id"),
                        {"id": str(touched_example_id)},
                    ).scalar()
                    == 1
                )
                # AND - the real colleague's own membership in the surviving example
                # project was never touched by the demo cleanup
                assert (
                    conn.execute(
                        text(
                            "SELECT 1 FROM project_members "
                            "WHERE project_id = :project_id AND user_id = :user_id"
                        ),
                        {"project_id": str(touched_example_id), "user_id": str(real_colleague_id)},
                    ).scalar()
                    == 1
                )

            # WHEN - re-applied (reversibility holds; the downgrade deleted the pool,
            # so the insert cannot collide with a leftover row)
            command.upgrade(config, "c4e81f7a9d23")

            # THEN
            with engine.connect() as conn:
                count = conn.execute(
                    text("SELECT count(*) FROM users WHERE is_demo = true")
                ).scalar()
            assert count == len(EXAMPLE_EXPERTS)
        finally:
            engine.dispose()
