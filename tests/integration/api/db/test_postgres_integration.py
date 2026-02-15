"""PostgreSQL integration tests for database operations.

These tests require PostgreSQL to be installed and available.
They will be skipped if pg_ctl is not found in PATH.

Run with: uv run pytest tests/integration/api/db/test_postgres_integration.py -v
"""

import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlmodel import SQLModel, select

from api.db.models import (
    CalculationResult,
    ExpertOpinion,
    MemberRole,
    Project,
    ProjectMember,
    User,
)

# Skip all tests in this module if PostgreSQL is not installed
pytestmark = pytest.mark.skipif(
    not shutil.which("pg_ctl"),
    reason="PostgreSQL not installed (pg_ctl not found in PATH)",
)


def load_schema(**kwargs):
    """Initialize database with SQLModel schema."""
    connection = (
        f"postgresql+psycopg2://{kwargs['user']}:"
        f"@{kwargs['host']}:{kwargs['port']}/{kwargs['dbname']}"
    )
    engine = create_engine(connection)
    SQLModel.metadata.create_all(engine)
    engine.dispose()


# Import factories only if PostgreSQL is available
try:
    from pytest_postgresql import factories

    postgresql_proc = factories.postgresql_proc(load=[load_schema])
    postgresql = factories.postgresql("postgresql_proc")
except ImportError:
    postgresql_proc = None
    postgresql = None


@pytest.fixture
def pg_engine(postgresql):
    """Create PostgreSQL engine for testing."""
    connection = (
        f"postgresql+psycopg2://{postgresql.info.user}:"
        f"@{postgresql.info.host}:{postgresql.info.port}/"
        f"{postgresql.info.dbname}"
    )
    engine = create_engine(connection)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    """PostgreSQL session for integration tests."""
    session = scoped_session(sessionmaker(bind=pg_engine))
    yield session
    session.rollback()
    session.close()


class TestForeignKeyEnforcement:
    """Tests for PostgreSQL foreign key constraint enforcement."""

    def test_foreign_key_constraint_enforced(self, pg_session):
        """
        GIVEN a membership with non-existent user_id
        WHEN saved to PostgreSQL
        THEN IntegrityError is raised (FK constraint violation)
        """
        # GIVEN
        admin = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        pg_session.add(admin)
        pg_session.commit()

        project = Project(name="Test Project", admin_id=admin.id)
        pg_session.add(project)
        pg_session.commit()

        # Non-existent user UUID
        fake_user_id = uuid4()

        # WHEN/THEN - PostgreSQL enforces FK constraint
        membership = ProjectMember(
            project_id=project.id,
            user_id=fake_user_id,
            role=MemberRole.EXPERT,
        )
        pg_session.add(membership)
        with pytest.raises(IntegrityError):
            pg_session.commit()
        pg_session.rollback()

    def test_cascade_delete_with_fk_enforcement(self, pg_session):
        """
        GIVEN a project with members, opinions, and result
        WHEN the project is deleted in PostgreSQL
        THEN all related records are cascade deleted
        """
        # GIVEN
        admin = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        expert = User(
            email="expert@example.com",
            hashed_password="hash",
            first_name="Expert",
            last_name="User",
        )
        pg_session.add_all([admin, expert])
        pg_session.commit()

        project = Project(name="Test Project", admin_id=admin.id)
        pg_session.add(project)
        pg_session.commit()

        membership = ProjectMember(
            project_id=project.id,
            user_id=expert.id,
            role=MemberRole.EXPERT,
        )
        opinion = ExpertOpinion(
            project_id=project.id,
            user_id=expert.id,
            position="Expert",
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        result = CalculationResult(
            project_id=project.id,
            best_compromise_lower=5.0,
            best_compromise_peak=10.0,
            best_compromise_upper=15.0,
            arithmetic_mean_lower=5.0,
            arithmetic_mean_peak=10.0,
            arithmetic_mean_upper=15.0,
            median_lower=5.0,
            median_peak=10.0,
            median_upper=15.0,
            max_error=0.5,
            num_experts=1,
        )
        pg_session.add_all([membership, opinion, result])
        pg_session.commit()

        membership_id = membership.id
        opinion_id = opinion.id
        result_id = result.id

        # WHEN
        pg_session.delete(project)
        pg_session.commit()

        # THEN - all related records should be deleted
        assert pg_session.get(ProjectMember, membership_id) is None
        assert pg_session.get(ExpertOpinion, opinion_id) is None
        assert pg_session.get(CalculationResult, result_id) is None


class TestConcurrentAccess:
    """Tests for concurrent database access patterns."""

    def test_concurrent_unique_constraint_violation(self, pg_engine):
        """
        GIVEN multiple threads trying to create user with same email
        WHEN executed concurrently
        THEN only one succeeds, others raise IntegrityError

        Note: Each thread needs its own session for proper isolation.
        """
        email = "concurrent@example.com"
        results = {"success": 0, "errors": 0}

        def create_user_in_thread():
            """Create user in a separate session."""
            session = scoped_session(sessionmaker(bind=pg_engine))
            try:
                user = User(
                    email=email,
                    hashed_password="hash",
                    first_name="Test",
                    last_name="User",
                )
                session.add(user)
                session.commit()
                return "success"
            except IntegrityError:
                session.rollback()
                return "error"
            finally:
                session.close()

        # WHEN - 5 threads try to create user with same email
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_user_in_thread) for _ in range(5)]
            for future in as_completed(futures):
                if future.result() == "success":
                    results["success"] += 1
                else:
                    results["errors"] += 1

        # THEN - exactly one should succeed
        assert results["success"] == 1
        assert results["errors"] == 4


class TestSavepointAndPartialRollback:
    """Tests for SAVEPOINT functionality in PostgreSQL."""

    def test_savepoint_partial_rollback(self, pg_session):
        """
        GIVEN a transaction with multiple operations
        WHEN one operation fails within a SAVEPOINT
        THEN only that operation is rolled back, not the entire transaction

        Uses begin_nested() for SAVEPOINT functionality.
        """
        # GIVEN - create first user successfully
        user1 = User(
            email="first@example.com",
            hashed_password="hash",
            first_name="First",
            last_name="User",
        )
        pg_session.add(user1)
        pg_session.commit()

        # WHEN - try to add duplicate in nested transaction (SAVEPOINT)
        # The savepoint allows partial rollback without losing the outer transaction
        try:
            with pg_session.begin_nested():
                user_duplicate = User(
                    email="first@example.com",  # Duplicate
                    hashed_password="hash",
                    first_name="Duplicate",
                    last_name="User",
                )
                pg_session.add(user_duplicate)
                # flush triggers the constraint check
                pg_session.flush()
        except IntegrityError:
            # Savepoint is automatically rolled back by context manager
            pass

        # Add second user after partial rollback - transaction should still work
        user2 = User(
            email="second@example.com",
            hashed_password="hash",
            first_name="Second",
            last_name="User",
        )
        pg_session.add(user2)
        pg_session.commit()

        # THEN - user1 and user2 should exist, duplicate should not
        users = pg_session.execute(select(User)).scalars().all()
        emails = [u.email for u in users]
        assert "first@example.com" in emails
        assert "second@example.com" in emails
        assert len(users) == 2


class TestTransactionIsolation:
    """Tests for transaction isolation in PostgreSQL."""

    def test_read_committed_isolation(self, pg_engine):
        """
        GIVEN two concurrent transactions
        WHEN one commits changes
        THEN the other sees committed changes (read committed)
        """
        # Session 1 creates a user and commits
        session1 = scoped_session(sessionmaker(bind=pg_engine))
        user = User(
            email="isolation@example.com",
            hashed_password="hash",
            first_name="Isolation",
            last_name="Test",
        )
        session1.add(user)
        session1.commit()
        user_id = user.id
        session1.close()

        # Session 2 should see the committed user
        session2 = scoped_session(sessionmaker(bind=pg_engine))
        found_user = session2.get(User, user_id)
        session2.close()

        # THEN
        assert found_user is not None
        assert found_user.email == "isolation@example.com"

    def test_uncommitted_changes_not_visible(self, pg_engine):
        """
        GIVEN a transaction with uncommitted changes
        WHEN another transaction queries
        THEN uncommitted changes are not visible
        """
        # GIVEN - Session 1 creates user but does NOT commit
        session1 = scoped_session(sessionmaker(bind=pg_engine))
        user = User(
            email="uncommitted@example.com",
            hashed_password="hash",
            first_name="Uncommitted",
            last_name="Test",
        )
        session1.add(user)
        session1.flush()  # Write to DB but don't commit

        # WHEN - Session 2 queries for the user
        session2 = scoped_session(sessionmaker(bind=pg_engine))
        found_user = (
            session2.execute(select(User).where(User.email == "uncommitted@example.com"))
            .scalars()
            .first()
        )

        # THEN - uncommitted user is not visible
        assert found_user is None

        # Cleanup
        session2.close()
        session1.rollback()
        session1.close()


class TestPostgreSQLSpecificFeatures:
    """Tests for PostgreSQL-specific features."""

    def test_uuid_generation(self, pg_session):
        """
        GIVEN a model with UUID primary key
        WHEN saved to PostgreSQL
        THEN UUID is properly generated and stored
        """
        # GIVEN/WHEN
        user = User(
            email="uuid@example.com",
            hashed_password="hash",
            first_name="UUID",
            last_name="Test",
        )
        pg_session.add(user)
        pg_session.commit()
        pg_session.refresh(user)

        # THEN
        assert user.id is not None
        assert isinstance(user.id, UUID)

    def test_timestamp_is_set_on_creation(self, pg_session):
        """
        GIVEN a model with timestamp field
        WHEN saved to PostgreSQL
        THEN created_at timestamp is automatically set
        """
        # GIVEN/WHEN
        user = User(
            email="timestamp@example.com",
            hashed_password="hash",
            first_name="Timestamp",
            last_name="Test",
        )
        pg_session.add(user)
        pg_session.commit()
        pg_session.refresh(user)

        # THEN
        assert user.created_at is not None

    def test_pydantic_scale_range_validation(self, pg_session):
        """
        GIVEN a project with invalid scale range (min > max)
        WHEN model_validate is called
        THEN Pydantic ValidationError is raised before reaching database
        """
        from pydantic import ValidationError

        # GIVEN/WHEN/THEN - Pydantic validation catches this before DB
        with pytest.raises(ValidationError, match="scale_min"):
            Project.model_validate(
                {
                    "name": "Invalid Project",
                    "admin_id": "00000000-0000-0000-0000-000000000000",
                    "scale_min": 100.0,
                    "scale_max": 50.0,
                }
            )
