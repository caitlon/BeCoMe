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
        deleted, an unrelated ordinary project is unaffected, an example project a
        real colleague was invited into survives because the CASCADE foreign keys
        behind it would otherwise take that colleague's own membership down along
        with the demo data, an example project whose only member is the admin
        survives once that admin has authored their own opinion in it (a
        contribution, not just a membership, has to spare the project from the
        same CASCADE), and an example project with an outstanding invitation to a
        real colleague survives even though that colleague has neither joined nor
        opined yet. It also covers what the deletion leaves behind: a surviving
        project whose only opinions were the demo pool's own is left with a stored
        result describing experts who no longer have one, and that stale result
        must not survive even though the project does.
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

            # GIVEN - a real account with five projects: one untouched example
            # project, one ordinary project, one example project a real colleague
            # was invited into, one example project the admin never invited anyone
            # into but did add their own opinion to, and one example project with
            # an outstanding invitation nobody has answered yet
            real_admin_id = uuid4()
            real_colleague_id = uuid4()
            pending_invitee_id = uuid4()
            untouched_example_id = uuid4()
            ordinary_project_id = uuid4()
            touched_example_id = uuid4()
            admin_authored_example_id = uuid4()
            pending_invitation_example_id = uuid4()
            demo_expert_id = EXAMPLE_EXPERTS[0].user_id
            created_at = datetime(2026, 1, 1, tzinfo=UTC)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO users "
                        "(id, email, hashed_password, first_name, last_name, created_at) "
                        "VALUES "
                        "(:admin_id, 'real.admin@example.com', 'hash', 'Real', 'Admin', :now), "
                        "(:colleague_id, 'real.colleague@example.com', 'hash', 'Real', "
                        "'Colleague', :now), "
                        "(:invitee_id, 'pending.invitee@example.com', 'hash', 'Pending', "
                        "'Invitee', :now)"
                    ),
                    {
                        "admin_id": str(real_admin_id),
                        "colleague_id": str(real_colleague_id),
                        "invitee_id": str(pending_invitee_id),
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
                        ":now, :now, true), "
                        "(:authored_id, 'Admin-authored example', :admin_id, 0, 100, '', "
                        ":now, :now, true), "
                        "(:pending_id, 'Pending-invitation example', :admin_id, 0, 100, '', "
                        ":now, :now, true)"
                    ),
                    {
                        "untouched_id": str(untouched_example_id),
                        "ordinary_id": str(ordinary_project_id),
                        "touched_id": str(touched_example_id),
                        "authored_id": str(admin_authored_example_id),
                        "pending_id": str(pending_invitation_example_id),
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
                # The admin never joins project_members in this fixture either (see
                # the untouched-example case above) -- admin_id on the project row
                # is what identifies them. What is new here is their own opinion.
                conn.execute(
                    text(
                        "INSERT INTO expert_opinions "
                        "(id, project_id, user_id, position, lower_bound, peak, "
                        "upper_bound, created_at, updated_at) "
                        "VALUES (:id, :project_id, :user_id, 'Admin', 0, 50, 100, "
                        ":now, :now)"
                    ),
                    {
                        "id": str(uuid4()),
                        "project_id": str(admin_authored_example_id),
                        "user_id": str(real_admin_id),
                        "now": created_at,
                    },
                )
                # An invitation the colleague has neither accepted nor declined --
                # the one real action that leaves no project_members and no
                # expert_opinions row behind, so it needs its own survival check.
                conn.execute(
                    text(
                        "INSERT INTO invitations "
                        "(id, project_id, invitee_id, inviter_id, created_at) "
                        "VALUES (:id, :project_id, :invitee_id, :inviter_id, :now)"
                    ),
                    {
                        "id": str(uuid4()),
                        "project_id": str(pending_invitation_example_id),
                        "invitee_id": str(pending_invitee_id),
                        "inviter_id": str(real_admin_id),
                        "now": created_at,
                    },
                )
                # The touched example project's only opinion is the demo pool's own,
                # so it is what the colleague's membership spares from the project
                # deletion but not from losing every opinion to the demo cleanup --
                # exactly the case a stale calculation_results row is left behind in.
                conn.execute(
                    text(
                        "INSERT INTO expert_opinions "
                        "(id, project_id, user_id, position, lower_bound, peak, "
                        "upper_bound, created_at, updated_at) "
                        "VALUES (:id, :project_id, :user_id, 'Demo', 30, 50, 70, "
                        ":now, :now)"
                    ),
                    {
                        "id": str(uuid4()),
                        "project_id": str(touched_example_id),
                        "user_id": str(demo_expert_id),
                        "now": created_at,
                    },
                )
                # A stored result on each of the two surviving example projects that
                # carry opinions: one where every opinion is about to be cascaded
                # away with the demo pool (must not survive), and one where the
                # admin's own opinion remains regardless (must survive untouched).
                conn.execute(
                    text(
                        "INSERT INTO calculation_results "
                        "(id, project_id, best_compromise_lower, best_compromise_peak, "
                        "best_compromise_upper, arithmetic_mean_lower, arithmetic_mean_peak, "
                        "arithmetic_mean_upper, median_lower, median_peak, median_upper, "
                        "max_error, num_experts, calculated_at) "
                        "VALUES "
                        "(:id1, :touched_id, 30, 50, 70, 30, 50, 70, 30, 50, 70, 5, 1, :now), "
                        "(:id2, :authored_id, 30, 50, 70, 30, 50, 70, 30, 50, 70, 5, 1, :now)"
                    ),
                    {
                        "id1": str(uuid4()),
                        "id2": str(uuid4()),
                        "touched_id": str(touched_example_id),
                        "authored_id": str(admin_authored_example_id),
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
                # AND - the project the admin never invited anyone into survives too,
                # because they contributed their own opinion to it. Membership alone
                # is not the bar: a solo admin who did exactly what the feature
                # invites -- open the example, add a fourteenth opinion, invite
                # nobody -- must not lose that opinion to the demo cleanup.
                assert (
                    conn.execute(
                        text("SELECT 1 FROM projects WHERE id = :id"),
                        {"id": str(admin_authored_example_id)},
                    ).scalar()
                    == 1
                )
                assert (
                    conn.execute(
                        text(
                            "SELECT 1 FROM expert_opinions "
                            "WHERE project_id = :project_id AND user_id = :user_id"
                        ),
                        {
                            "project_id": str(admin_authored_example_id),
                            "user_id": str(real_admin_id),
                        },
                    ).scalar()
                    == 1
                )
                # AND - the project with an outstanding invitation survives too: the
                # colleague has neither joined nor opined, so membership and opinion
                # alone would have missed this case and deleted the project, taking
                # the invitation down with it via CASCADE.
                assert (
                    conn.execute(
                        text("SELECT 1 FROM projects WHERE id = :id"),
                        {"id": str(pending_invitation_example_id)},
                    ).scalar()
                    == 1
                )
                assert (
                    conn.execute(
                        text(
                            "SELECT 1 FROM invitations "
                            "WHERE project_id = :project_id AND invitee_id = :invitee_id"
                        ),
                        {
                            "project_id": str(pending_invitation_example_id),
                            "invitee_id": str(pending_invitee_id),
                        },
                    ).scalar()
                    == 1
                )
                # AND - the touched example project's stored result is gone: its only
                # opinion belonged to the demo pool, so once that opinion cascaded
                # away with the demo accounts, the result was left describing an
                # expert who no longer has one, and the cleanup discards it.
                assert (
                    conn.execute(
                        text("SELECT 1 FROM calculation_results WHERE project_id = :id"),
                        {"id": str(touched_example_id)},
                    ).scalar()
                    is None
                )
                # AND - the admin-authored example project's stored result survives,
                # because that project never loses its only opinion: the cleanup must
                # not discard a result just because a project was touched by the
                # demo pool's deletion, only when it is left with no opinion at all.
                assert (
                    conn.execute(
                        text("SELECT 1 FROM calculation_results WHERE project_id = :id"),
                        {"id": str(admin_authored_example_id)},
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


class TestClearStaleLikertVerdictsMigration:
    """The migration clearing likert_value/likert_decision for non-Likert projects.

    ``_is_likert_scale`` was fixed in a prior commit to require an empty
    ``scale_unit`` in addition to the 0-100 range. This migration is the one-time
    cleanup for rows a ``recalculate`` wrote before that fix existed.
    """

    def test_upgrade_clears_verdict_only_where_the_new_rule_disagrees(
        self, migration_pg, monkeypatch
    ):
        """A stored verdict is cleared for exactly the rows the new rule rejects.

        Four projects cover the shapes ``_is_likert_scale`` distinguishes: a 0-100
        scale with a non-empty unit, where a verdict was stored under the old rule
        and must now be cleared; a 0-100 scale with an empty unit, a genuine Likert
        project whose verdict must survive; a scale outside 0-100, which never
        received a verdict under either rule and whose NULL row must survive
        untouched; and a 0-100 scale whose unit is a single tab character, which
        ``_is_likert_scale`` also calls empty and whose verdict must equally survive.
        The fourth case is the one a SQL ``TRIM(scale_unit) = ''`` filter gets wrong:
        ``TRIM`` with no explicit character list strips only the plain space, not a
        tab, in both PostgreSQL and SQLite, so it would leave the unit looking
        non-empty and wrongly clear a verdict the application rule calls genuine.
        """
        # GIVEN - a database migrated up to the revision just before this one
        url = _url(migration_pg)
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
        config = Config("alembic.ini")
        engine = create_engine(url)

        try:
            command.upgrade(config, "c4e81f7a9d23")

            admin_id = uuid4()
            percent_project_id = uuid4()
            likert_project_id = uuid4()
            budget_project_id = uuid4()
            tab_project_id = uuid4()
            now = datetime(2026, 1, 1, tzinfo=UTC)

            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO users "
                        "(id, email, hashed_password, first_name, last_name, created_at) "
                        "VALUES (:id, 'admin@example.com', 'hash', 'Admin', 'User', :now)"
                    ),
                    {"id": str(admin_id), "now": now},
                )
                # A flood question measured in percent and a budget question in
                # billions of CZK, the two examples from the bug this fix closed,
                # alongside the genuine 0-100 unitless scale they were confused with,
                # and a 0-100 scale whose unit is a bare tab -- whitespace that
                # Python's str.strip() empties out but SQL's TRIM() does not.
                conn.execute(
                    text(
                        "INSERT INTO projects "
                        "(id, name, admin_id, scale_min, scale_max, scale_unit, "
                        "created_at, updated_at) "
                        "VALUES "
                        "(:percent_id, 'Flood extent', :admin_id, 0, 100, '%', :now, :now), "
                        "(:likert_id, 'Agreement scale', :admin_id, 0, 100, '', :now, :now), "
                        "(:budget_id, 'Reservoir budget', :admin_id, 0, 500, 'CZK bn', "
                        ":now, :now), "
                        "(:tab_id, 'Tab-unit scale', :admin_id, 0, 100, '\t', :now, :now)"
                    ),
                    {
                        "percent_id": str(percent_project_id),
                        "likert_id": str(likert_project_id),
                        "budget_id": str(budget_project_id),
                        "tab_id": str(tab_project_id),
                        "admin_id": str(admin_id),
                        "now": now,
                    },
                )
                # The percent, likert and tab projects each carry a stored verdict,
                # as the old, unit-blind rule would have written for all three. The
                # budget project's row has none, since even the old rule required
                # the 0-100 range and 500 never qualified.
                conn.execute(
                    text(
                        "INSERT INTO calculation_results "
                        "(id, project_id, best_compromise_lower, best_compromise_peak, "
                        "best_compromise_upper, arithmetic_mean_lower, arithmetic_mean_peak, "
                        "arithmetic_mean_upper, median_lower, median_peak, median_upper, "
                        "max_error, num_experts, likert_value, likert_decision, calculated_at) "
                        "VALUES "
                        "(:id1, :percent_id, 30, 50, 70, 30, 50, 70, 30, 50, 70, 5, 3, "
                        "75, 'Agree', :now), "
                        "(:id2, :likert_id, 30, 50, 70, 30, 50, 70, 30, 50, 70, 5, 3, "
                        "75, 'Agree', :now), "
                        "(:id3, :budget_id, 30, 50, 70, 30, 50, 70, 30, 50, 70, 5, 3, "
                        "NULL, NULL, :now), "
                        "(:id4, :tab_id, 30, 50, 70, 30, 50, 70, 30, 50, 70, 5, 3, "
                        "75, 'Agree', :now)"
                    ),
                    {
                        "id1": str(uuid4()),
                        "id2": str(uuid4()),
                        "id3": str(uuid4()),
                        "id4": str(uuid4()),
                        "percent_id": str(percent_project_id),
                        "likert_id": str(likert_project_id),
                        "budget_id": str(budget_project_id),
                        "tab_id": str(tab_project_id),
                        "now": now,
                    },
                )

            # WHEN - this migration is applied. Pinned to its own revision id rather
            # than "head" for the same reason as the migrations above: a later
            # migration landing on top would otherwise silently change what this
            # test exercises.
            command.upgrade(config, "a8d7ba4fcdde")

            # THEN - the percent-scale project's stale verdict is cleared
            with engine.connect() as conn:
                percent_row = conn.execute(
                    text(
                        "SELECT likert_value, likert_decision FROM calculation_results "
                        "WHERE project_id = :id"
                    ),
                    {"id": str(percent_project_id)},
                ).one()
            assert percent_row.likert_value is None
            assert percent_row.likert_decision is None

            # AND - the genuine Likert project's verdict survives untouched
            with engine.connect() as conn:
                likert_row = conn.execute(
                    text(
                        "SELECT likert_value, likert_decision FROM calculation_results "
                        "WHERE project_id = :id"
                    ),
                    {"id": str(likert_project_id)},
                ).one()
            assert likert_row.likert_value == 75
            assert likert_row.likert_decision == "Agree"

            # AND - the tab-unit project's verdict survives too: a bare tab is
            # whitespace under _is_likert_scale's own scale_unit.strip() check, so
            # this project is Likert by the application's rule just as much as the
            # empty-unit one above. SQL's TRIM() strips only the plain space, so a
            # WHERE clause built on TRIM(scale_unit) = '' would have missed this
            # unit and cleared the verdict a Python-side strip() correctly keeps.
            with engine.connect() as conn:
                tab_row = conn.execute(
                    text(
                        "SELECT likert_value, likert_decision FROM calculation_results "
                        "WHERE project_id = :id"
                    ),
                    {"id": str(tab_project_id)},
                ).one()
            assert tab_row.likert_value == 75
            assert tab_row.likert_decision == "Agree"

            # AND - the out-of-range project's row, which never had a verdict, is
            # left alone rather than erroring or acquiring one
            with engine.connect() as conn:
                budget_row = conn.execute(
                    text(
                        "SELECT likert_value, likert_decision FROM calculation_results "
                        "WHERE project_id = :id"
                    ),
                    {"id": str(budget_project_id)},
                ).one()
            assert budget_row.likert_value is None
            assert budget_row.likert_decision is None

            # WHEN - rolled back to its own down_revision (pinned, not "-1"). The
            # downgrade is a documented no-op: the verdict this migration clears is
            # derived data that was never stored anywhere to restore it from.
            command.downgrade(config, "c4e81f7a9d23")

            # THEN - nothing about the data changed; the downgrade did nothing
            with engine.connect() as conn:
                percent_row = conn.execute(
                    text(
                        "SELECT likert_value, likert_decision FROM calculation_results "
                        "WHERE project_id = :id"
                    ),
                    {"id": str(percent_project_id)},
                ).one()
                likert_row = conn.execute(
                    text(
                        "SELECT likert_value, likert_decision FROM calculation_results "
                        "WHERE project_id = :id"
                    ),
                    {"id": str(likert_project_id)},
                ).one()
            assert percent_row.likert_value is None
            assert likert_row.likert_value == 75

            # WHEN - re-applied (idempotent: clearing an already-cleared row and
            # leaving an untouched one alone both repeat cleanly)
            command.upgrade(config, "a8d7ba4fcdde")

            # THEN - both surviving verdicts are still there. The tab-unit project
            # is re-checked alongside the empty-unit one because it is the only one
            # of the two that a TRIM-based filter would get wrong: an empty unit
            # survives TRIM and Python alike, so on its own it cannot tell a
            # correct re-run from a regressed one.
            with engine.connect() as conn:
                likert_row = conn.execute(
                    text(
                        "SELECT likert_value, likert_decision FROM calculation_results "
                        "WHERE project_id = :id"
                    ),
                    {"id": str(likert_project_id)},
                ).one()
                tab_row = conn.execute(
                    text(
                        "SELECT likert_value, likert_decision FROM calculation_results "
                        "WHERE project_id = :id"
                    ),
                    {"id": str(tab_project_id)},
                ).one()
            assert likert_row.likert_value == 75
            assert likert_row.likert_decision == "Agree"
            assert tab_row.likert_value == 75
            assert tab_row.likert_decision == "Agree"
        finally:
            engine.dispose()
