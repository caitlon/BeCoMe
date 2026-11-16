"""PostgreSQL integration tests for database operations.

These tests require PostgreSQL to be installed and available.
They will be skipped if pg_ctl is not found in PATH.

Run with: uv run pytest tests/integration/api/db/test_postgres_integration.py -v
"""

import shutil
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlmodel import Session, SQLModel, select

from api.db.models import (
    CalculationResult,
    EmailVerificationToken,
    ExpertOpinion,
    MemberRole,
    Project,
    ProjectMember,
    User,
)
from api.exceptions import ProjectNotFoundError, ProjectOwnershipChangedError
from api.services.calculation_service import CalculationService
from api.services.opinion_service import OpinionService
from api.services.project_membership_service import ProjectMembershipService
from api.services.project_service import ProjectService
from api.services.user_service import UserService
from tests.shared.helpers import add_project

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

        project = add_project(pg_session, admin, name="Test Project")
        pg_session.commit()

        # Non-existent user UUID
        fake_user_id = uuid4()

        # WHEN/THEN: PostgreSQL enforces FK constraint
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

        project = add_project(pg_session, admin, name="Test Project")
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

        # THEN: all related records should be deleted
        assert pg_session.get(ProjectMember, membership_id) is None
        assert pg_session.get(ExpertOpinion, opinion_id) is None
        assert pg_session.get(CalculationResult, result_id) is None

    def test_cascade_delete_verification_token_with_fk_enforcement(self, pg_session):
        """
        GIVEN a user with an email verification token
        WHEN the user is deleted in PostgreSQL
        THEN the token is cascade deleted
        """
        # GIVEN
        user = User(
            email="verify@example.com",
            hashed_password="hash",
            first_name="Verify",
            last_name="User",
        )
        pg_session.add(user)
        pg_session.commit()

        token = EmailVerificationToken(
            user_id=user.id,
            token_hash="e" * 64,
            hashed_password="hash",
            first_name="Test",
            last_name="User",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        pg_session.add(token)
        pg_session.commit()
        token_id = token.id

        # WHEN
        pg_session.delete(user)
        pg_session.commit()

        # THEN: the token is cascade deleted
        assert pg_session.get(EmailVerificationToken, token_id) is None

    def test_deleting_admin_with_project_is_restricted(self, pg_session):
        """
        GIVEN a user who admins a project
        WHEN the user is deleted in PostgreSQL
        THEN IntegrityError is raised (ON DELETE RESTRICT on projects.admin_id)

        This is the database backstop behind the API's 409: erasing an owner must
        not silently cascade away the project and other experts' contributions.
        """
        # GIVEN
        admin = User(
            email="restrict-admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        pg_session.add(admin)
        pg_session.commit()

        add_project(pg_session, admin, name="Owned Project")
        pg_session.commit()

        # WHEN/THEN: RESTRICT blocks deleting an owner who still has a project
        pg_session.delete(admin)
        with pytest.raises(IntegrityError):
            pg_session.commit()
        pg_session.rollback()


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

        # WHEN: 5 threads try to create user with same email
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_user_in_thread) for _ in range(5)]
            for future in as_completed(futures):
                if future.result() == "success":
                    results["success"] += 1
                else:
                    results["errors"] += 1

        # THEN: exactly one should succeed
        assert results["success"] == 1
        assert results["errors"] == 4


class TestConcurrentRecalculation:
    """Tests that concurrent opinion changes in one project leave a complete result."""

    @staticmethod
    def _seed_project(pg_engine) -> tuple[UUID, UUID, UUID]:
        """Commit a project with two experts and return (project_id, user_1_id, user_2_id)."""
        with Session(pg_engine) as setup:
            admin = User(
                email="admin@example.com", hashed_password="x", first_name="A", last_name="A"
            )
            expert_1 = User(
                email="one@example.com", hashed_password="x", first_name="One", last_name="One"
            )
            expert_2 = User(
                email="two@example.com", hashed_password="x", first_name="Two", last_name="Two"
            )
            setup.add_all([admin, expert_1, expert_2])
            setup.flush()
            project = add_project(setup, admin, name="Concurrent")
            setup.commit()
            return project.id, expert_1.id, expert_2.id

    @staticmethod
    def _open_session(pg_engine) -> Session:
        """Open a session that fails on a lock wait instead of hanging a broken run."""
        session = Session(pg_engine)
        session.exec(text("SET lock_timeout = '5s'"))
        return session

    @staticmethod
    def _flush_opinion(session: Session, project_id: UUID, user_id: UUID) -> None:
        """Add an opinion and flush it, which takes a key-share lock on the project row."""
        session.add(
            ExpertOpinion(
                project_id=project_id,
                user_id=user_id,
                position="Expert",
                lower_bound=10.0,
                peak=20.0,
                upper_bound=30.0,
            )
        )
        session.flush()

    @staticmethod
    def _stored_expert_count(pg_engine, project_id: UUID) -> int:
        """Read num_experts of the committed result."""
        with Session(pg_engine) as check:
            return (
                check.exec(
                    select(CalculationResult).where(CalculationResult.project_id == project_id)
                )
                .one()
                .num_experts
            )

    def test_second_recalculation_waits_and_sees_the_first_opinion(self, pg_engine):
        """
        GIVEN two transactions that each add an opinion to the same project
        WHEN the first has staged its recalculation and the second starts its own
        THEN the second waits for the first to commit, so the stored result counts both
        """
        # GIVEN: a project and two experts, committed
        project_id, user_1_id, user_2_id = self._seed_project(pg_engine)

        def second_transaction() -> None:
            with self._open_session(pg_engine) as session:
                self._flush_opinion(session, project_id, user_2_id)
                CalculationService(session).stage_recalculation(project_id)
                session.commit()

        # WHEN: the first transaction holds the project lock while the second tries to run
        with self._open_session(pg_engine) as first, ThreadPoolExecutor(max_workers=1) as executor:
            self._flush_opinion(first, project_id, user_1_id)
            CalculationService(first).stage_recalculation(project_id)
            future = executor.submit(second_transaction)
            time.sleep(1.0)
            still_waiting = not future.done()
            first.commit()
            future.result(timeout=30)

        # THEN
        assert still_waiting
        assert self._stored_expert_count(pg_engine, project_id) == 2

    def test_both_opinions_flushed_before_either_recalculation_does_not_deadlock(self, pg_engine):
        """
        GIVEN two transactions that have both flushed an opinion into the same project
        WHEN each then stages its recalculation
        THEN the second waits for the first without a deadlock, and the result counts both
        """
        # GIVEN: a project and two experts, committed
        project_id, user_1_id, user_2_id = self._seed_project(pg_engine)
        second_flushed = threading.Event()
        go = threading.Event()

        def second_transaction() -> None:
            with self._open_session(pg_engine) as session:
                self._flush_opinion(session, project_id, user_2_id)
                second_flushed.set()
                go.wait(timeout=10)
                CalculationService(session).stage_recalculation(project_id)
                session.commit()

        # WHEN: both opinions are flushed, then the first transaction recalculates
        with self._open_session(pg_engine) as first, ThreadPoolExecutor(max_workers=1) as executor:
            self._flush_opinion(first, project_id, user_1_id)
            future = executor.submit(second_transaction)
            try:
                assert second_flushed.wait(timeout=10)
                CalculationService(first).stage_recalculation(project_id)
            finally:
                go.set()
            time.sleep(1.0)
            still_waiting = not future.done()
            first.commit()
            future.result(timeout=30)

        # THEN
        assert still_waiting
        assert self._stored_expert_count(pg_engine, project_id) == 2

    def test_project_delete_during_opinion_write_does_not_deadlock(self, pg_engine):
        """
        GIVEN a project with a stored result and an opinion write that holds the project lock
        WHEN the project is deleted before that write recalculates
        THEN the delete waits for the write instead of deadlocking, and the project is gone
        """
        # GIVEN: a project with one committed opinion and its stored result
        project_id, user_1_id, user_2_id = self._seed_project(pg_engine)
        with self._open_session(pg_engine) as setup:
            self._flush_opinion(setup, project_id, user_1_id)
            CalculationService(setup).stage_recalculation(project_id)
            setup.commit()
        write_holds_lock = threading.Event()

        def delete_transaction() -> None:
            with self._open_session(pg_engine) as session:
                assert write_holds_lock.wait(timeout=10)
                ProjectService(session).delete_project(project_id)

        # WHEN: the delete starts while the opinion write holds the project lock, and the
        # write then recalculates, which updates the result row
        with self._open_session(pg_engine) as write, ThreadPoolExecutor(max_workers=1) as executor:
            self._flush_opinion(write, project_id, user_2_id)
            write.exec(
                select(Project).where(Project.id == project_id).with_for_update(key_share=True)
            )
            future = executor.submit(delete_transaction)
            write_holds_lock.set()
            time.sleep(0.5)
            CalculationService(write).stage_recalculation(project_id)
            write.commit()
            future.result(timeout=30)

        # THEN
        with Session(pg_engine) as check:
            assert check.get(Project, project_id) is None
            assert (
                check.exec(
                    select(CalculationResult).where(CalculationResult.project_id == project_id)
                ).first()
                is None
            )


class TestProjectDeleteAgainstOpinionWriters:
    """Tests that deleting a project while a writer changes its opinions does not deadlock."""

    @staticmethod
    def _seed_expert_with_opinion(pg_engine) -> tuple[UUID, UUID]:
        """Commit a project, one expert member, the opinion and the result; return the ids."""
        project_id, expert_id, _ = TestConcurrentRecalculation._seed_project(pg_engine)
        with TestConcurrentRecalculation._open_session(pg_engine) as setup:
            setup.add(
                ProjectMember(project_id=project_id, user_id=expert_id, role=MemberRole.EXPERT)
            )
            TestConcurrentRecalculation._flush_opinion(setup, project_id, expert_id)
            CalculationService(setup).stage_recalculation(project_id)
            setup.commit()
        return project_id, expert_id

    @staticmethod
    def _race_with_project_delete(
        pg_engine, monkeypatch, project_id: UUID, write: Callable[[Session], object]
    ) -> list[BaseException]:
        """Run ``write`` and delete the project while the write is about to recalculate.

        The write pauses just before it stages the recalculation, when it has already changed
        its own rows; the delete starts there and takes every lock it can get.

        :return: Errors raised by either transaction
        """
        paused = threading.Event()
        stage = CalculationService.stage_recalculation

        def pausing_stage(service: CalculationService, pid: UUID) -> CalculationResult | None:
            paused.set()
            time.sleep(1.0)
            return stage(service, pid)

        monkeypatch.setattr(CalculationService, "stage_recalculation", pausing_stage)

        def write_transaction() -> None:
            with TestConcurrentRecalculation._open_session(pg_engine) as session:
                write(session)

        def delete_transaction() -> None:
            assert paused.wait(timeout=10)
            with TestConcurrentRecalculation._open_session(pg_engine) as session:
                ProjectService(session).delete_project(project_id)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(write_transaction), executor.submit(delete_transaction)]
            errors = [future.exception(timeout=30) for future in futures]
        return [error for error in errors if error is not None]

    @staticmethod
    def _assert_project_gone(pg_engine, project_id: UUID) -> None:
        """Check that the project and its opinions are deleted."""
        with Session(pg_engine) as check:
            assert check.get(Project, project_id) is None
            assert (
                check.exec(
                    select(ExpertOpinion).where(ExpertOpinion.project_id == project_id)
                ).first()
                is None
            )

    def test_opinion_update(self, pg_engine, monkeypatch):
        """
        GIVEN an expert's committed opinion
        WHEN the expert updates it while the admin deletes the project
        THEN neither transaction deadlocks, and the project is gone
        """
        # GIVEN
        project_id, expert_id = self._seed_expert_with_opinion(pg_engine)

        # WHEN
        errors = self._race_with_project_delete(
            pg_engine,
            monkeypatch,
            project_id,
            lambda session: OpinionService(session).upsert_opinion(
                project_id, expert_id, "Expert", 11.0, 21.0, 31.0, CalculationService(session)
            ),
        )

        # THEN
        assert errors == []
        self._assert_project_gone(pg_engine, project_id)

    def test_opinion_delete(self, pg_engine, monkeypatch):
        """
        GIVEN an expert's committed opinion
        WHEN the expert withdraws it while the admin deletes the project
        THEN neither transaction deadlocks, and the project is gone
        """
        # GIVEN
        project_id, expert_id = self._seed_expert_with_opinion(pg_engine)

        # WHEN
        errors = self._race_with_project_delete(
            pg_engine,
            monkeypatch,
            project_id,
            lambda session: OpinionService(session).delete_opinion(
                project_id, expert_id, CalculationService(session)
            ),
        )

        # THEN
        assert errors == []
        self._assert_project_gone(pg_engine, project_id)

    def test_member_removal(self, pg_engine, monkeypatch):
        """
        GIVEN an expert member with a committed opinion
        WHEN the member is removed while the admin deletes the project
        THEN neither transaction deadlocks, and the project is gone
        """
        # GIVEN
        project_id, expert_id = self._seed_expert_with_opinion(pg_engine)

        # WHEN
        errors = self._race_with_project_delete(
            pg_engine,
            monkeypatch,
            project_id,
            lambda session: ProjectMembershipService(session).remove_member(
                project_id, expert_id, CalculationService(session)
            ),
        )

        # THEN
        assert errors == []
        self._assert_project_gone(pg_engine, project_id)

    def test_account_deletion(self, pg_engine, monkeypatch):
        """
        GIVEN an expert member with a committed opinion
        WHEN the expert deletes the account while the admin deletes the project
        THEN neither transaction deadlocks, and both the project and the account are gone
        """
        # GIVEN
        project_id, expert_id = self._seed_expert_with_opinion(pg_engine)

        # WHEN
        errors = self._race_with_project_delete(
            pg_engine,
            monkeypatch,
            project_id,
            lambda session: UserService(session).delete_user(
                session.get(User, expert_id), CalculationService(session)
            ),
        )

        # THEN
        assert errors == []
        self._assert_project_gone(pg_engine, project_id)
        with Session(pg_engine) as check:
            assert check.get(User, expert_id) is None


class TestProjectDeleteBeforeWriterLock:
    """Tests that a writer arriving after the project is deleted gets a clean refusal."""

    @staticmethod
    def _seed_expert_member(pg_engine) -> tuple[UUID, UUID]:
        """Commit a project and one expert member who has no opinion; return the ids."""
        project_id, expert_id, _ = TestConcurrentRecalculation._seed_project(pg_engine)
        with Session(pg_engine) as setup:
            setup.add(
                ProjectMember(project_id=project_id, user_id=expert_id, role=MemberRole.EXPERT)
            )
            setup.commit()
        return project_id, expert_id

    @staticmethod
    def _race_delete_before_lock(
        pg_engine, monkeypatch, project_id: UUID, write: Callable[[Session], object]
    ) -> list[BaseException]:
        """Run ``write`` so that the project deletion commits just before its first lock.

        The write stops at its first ``lock_project`` call, which is where a request lands
        after its membership check passed; the delete runs to its commit there, and only then
        does the write take the lock.

        :return: Errors raised by either transaction
        """
        at_lock = threading.Event()
        deleted = threading.Event()
        lock = CalculationService.lock_project

        def waiting_lock(service: CalculationService, pid: UUID) -> bool:
            if not at_lock.is_set():
                at_lock.set()
                assert deleted.wait(timeout=10)
            return lock(service, pid)

        monkeypatch.setattr(CalculationService, "lock_project", waiting_lock)

        def write_transaction() -> None:
            with TestConcurrentRecalculation._open_session(pg_engine) as session:
                write(session)

        def delete_transaction() -> None:
            assert at_lock.wait(timeout=10)
            try:
                with TestConcurrentRecalculation._open_session(pg_engine) as session:
                    ProjectService(session).delete_project(project_id)
            finally:
                deleted.set()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(write_transaction), executor.submit(delete_transaction)]
            errors = [future.exception(timeout=30) for future in futures]
        return [error for error in errors if error is not None]

    @pytest.mark.parametrize("with_opinion", [False, True])
    def test_opinion_update(self, pg_engine, monkeypatch, with_opinion):
        """
        GIVEN an expert member, with or without a committed opinion
        WHEN the project is deleted after the expert's request passed its membership check
        THEN the update is refused as project-not-found and leaves no opinion behind
        """
        # GIVEN
        if with_opinion:
            project_id, expert_id = (
                TestProjectDeleteAgainstOpinionWriters._seed_expert_with_opinion(pg_engine)
            )
        else:
            project_id, expert_id = self._seed_expert_member(pg_engine)

        # WHEN
        errors = self._race_delete_before_lock(
            pg_engine,
            monkeypatch,
            project_id,
            lambda session: OpinionService(session).upsert_opinion(
                project_id, expert_id, "Expert", 11.0, 21.0, 31.0, CalculationService(session)
            ),
        )

        # THEN
        assert [type(error) for error in errors] == [ProjectNotFoundError]
        TestProjectDeleteAgainstOpinionWriters._assert_project_gone(pg_engine, project_id)

    def test_opinion_delete(self, pg_engine, monkeypatch):
        """
        GIVEN an expert's committed opinion
        WHEN the project is deleted after the expert's withdrawal passed its membership check
        THEN the withdrawal is refused as project-not-found
        """
        # GIVEN
        project_id, expert_id = TestProjectDeleteAgainstOpinionWriters._seed_expert_with_opinion(
            pg_engine
        )

        # WHEN
        errors = self._race_delete_before_lock(
            pg_engine,
            monkeypatch,
            project_id,
            lambda session: OpinionService(session).delete_opinion(
                project_id, expert_id, CalculationService(session)
            ),
        )

        # THEN
        assert [type(error) for error in errors] == [ProjectNotFoundError]
        TestProjectDeleteAgainstOpinionWriters._assert_project_gone(pg_engine, project_id)

    def test_member_removal(self, pg_engine, monkeypatch):
        """
        GIVEN an expert member with a committed opinion
        WHEN the project is deleted after the admin's removal request passed its checks
        THEN the removal is refused as project-not-found
        """
        # GIVEN
        project_id, expert_id = TestProjectDeleteAgainstOpinionWriters._seed_expert_with_opinion(
            pg_engine
        )

        # WHEN
        errors = self._race_delete_before_lock(
            pg_engine,
            monkeypatch,
            project_id,
            lambda session: ProjectMembershipService(session).remove_member(
                project_id, expert_id, CalculationService(session)
            ),
        )

        # THEN
        assert [type(error) for error in errors] == [ProjectNotFoundError]
        TestProjectDeleteAgainstOpinionWriters._assert_project_gone(pg_engine, project_id)

    def test_account_deletion(self, pg_engine, monkeypatch):
        """
        GIVEN an expert member with a committed opinion
        WHEN the project is deleted after the expert's account deletion listed its projects
        THEN the account deletion still succeeds, and both the project and the account are gone
        """
        # GIVEN
        project_id, expert_id = TestProjectDeleteAgainstOpinionWriters._seed_expert_with_opinion(
            pg_engine
        )

        # WHEN
        errors = self._race_delete_before_lock(
            pg_engine,
            monkeypatch,
            project_id,
            lambda session: UserService(session).delete_user(
                session.get(User, expert_id), CalculationService(session)
            ),
        )

        # THEN
        assert errors == []
        TestProjectDeleteAgainstOpinionWriters._assert_project_gone(pg_engine, project_id)
        with Session(pg_engine) as check:
            assert check.get(User, expert_id) is None


class TestTransferOwnershipStatementOrder:
    """Tests the statements a project ownership transfer sends, and their order."""

    # Membership ids that sort either side of each other, since the ORM flushes the rows
    # of one table in primary-key order.
    LOW_ID = UUID(int=1)
    HIGH_ID = UUID(int=2**128 - 2)

    @staticmethod
    def _seed(pg_engine, old_admin_membership_id: UUID, new_admin_membership_id: UUID):
        """Commit a project with an admin and an expert member; return (project_id, expert_id)."""
        with Session(pg_engine) as setup:
            admin = User(
                email="admin@example.com", hashed_password="x", first_name="A", last_name="A"
            )
            expert = User(
                email="expert@example.com", hashed_password="x", first_name="E", last_name="E"
            )
            setup.add_all([admin, expert])
            setup.flush()
            project = Project(name="Transfer", admin_id=admin.id)
            setup.add(project)
            setup.flush()
            setup.add_all(
                [
                    ProjectMember(
                        id=old_admin_membership_id,
                        project_id=project.id,
                        user_id=admin.id,
                        role=MemberRole.ADMIN,
                    ),
                    ProjectMember(
                        id=new_admin_membership_id,
                        project_id=project.id,
                        user_id=expert.id,
                        role=MemberRole.EXPERT,
                    ),
                ]
            )
            setup.commit()
            return project.id, expert.id

    @staticmethod
    def _transfer_statements(pg_engine, project_id: UUID, new_admin_id: UUID) -> list[tuple]:
        """Run the transfer and return the (statement, parameters) pairs it sent."""
        sent: list[tuple] = []

        def record(_conn, _cursor, statement, parameters, _context, _executemany):
            sent.append((statement, parameters))

        with Session(pg_engine) as session:
            # Loaded in the transferring session before recording starts, as the route's
            # dependency does, so the first recorded statement is the transfer's own.
            project = session.get(Project, project_id)
            event.listen(pg_engine, "before_cursor_execute", record)
            try:
                ProjectService(session).transfer_ownership(project, new_admin_id)
            finally:
                event.remove(pg_engine, "before_cursor_execute", record)
        return sent

    @staticmethod
    def _assert_ownership_settled(pg_engine, project_id: UUID, admin_id: UUID):
        """Assert, from a fresh session, that exactly one member holds ADMIN and it is the owner."""
        with Session(pg_engine) as check:
            project = check.get(Project, project_id)
            members = check.exec(
                select(ProjectMember).where(ProjectMember.project_id == project_id)
            ).all()
            admin_rows = [m for m in members if m.role == MemberRole.ADMIN]
            assert project.admin_id == admin_id
            assert [m.user_id for m in admin_rows] == [admin_id]
            assert all(m.role == MemberRole.EXPERT for m in members if m.user_id != admin_id)

    @staticmethod
    def _role_updates(sent: list[tuple]) -> list[str]:
        """Return the roles written to project_members, in the order they were sent."""
        roles = []
        for statement, parameters in sent:
            if not statement.startswith("UPDATE project_members"):
                continue
            rows = parameters if isinstance(parameters, list) else [parameters]
            roles.extend(row["role"] for row in rows)
        return roles

    @pytest.mark.parametrize(
        ("old_admin_membership_id", "new_admin_membership_id"),
        [(LOW_ID, HIGH_ID), (HIGH_ID, LOW_ID)],
        ids=["new-admin-row-sorts-last", "new-admin-row-sorts-first"],
    )
    def test_old_admin_is_demoted_before_new_admin_is_promoted(
        self, pg_engine, old_admin_membership_id, new_admin_membership_id
    ):
        """
        GIVEN a project whose two membership rows sort in either primary-key order
        WHEN ownership moves to the expert
        THEN the demotion reaches the database before the promotion, so the project never
            has two admin rows at once
        """
        # GIVEN
        project_id, expert_id = self._seed(
            pg_engine, old_admin_membership_id, new_admin_membership_id
        )

        # WHEN
        sent = self._transfer_statements(pg_engine, project_id, expert_id)

        # THEN
        assert self._role_updates(sent) == ["EXPERT", "ADMIN"]
        self._assert_ownership_settled(pg_engine, project_id, expert_id)

    def test_project_row_is_locked_before_any_member_row_is_touched(self, pg_engine):
        """
        GIVEN a project with an admin and an expert member
        WHEN ownership moves to the expert
        THEN the first statement locks the project row with FOR NO KEY UPDATE, the lock a
            project deletion and the opinion and member writers take before member rows
        """
        # GIVEN
        project_id, expert_id = self._seed(pg_engine, self.LOW_ID, self.HIGH_ID)

        # WHEN
        sent = self._transfer_statements(pg_engine, project_id, expert_id)

        # THEN
        first_statement = sent[0][0]
        assert "FROM projects" in first_statement
        assert first_statement.rstrip().endswith("FOR NO KEY UPDATE")
        self._assert_ownership_settled(pg_engine, project_id, expert_id)

    def test_a_transfer_that_lost_the_race_is_refused_and_leaves_one_admin(self, pg_engine):
        """
        GIVEN a request that read the project while X was admin
        AND another transfer that moved the project to Y and committed meanwhile
        WHEN the stale request transfers the project to Z
        THEN it is refused, and Y is still the project's one admin

        Without the check the stale transfer demotes X again, who is no longer admin, and
        promotes Z beside Y, leaving two admin rows.
        """
        # GIVEN
        with Session(pg_engine) as setup:
            users = [
                User(
                    email=f"{name}@example.com",
                    hashed_password="x",
                    first_name=name,
                    last_name=name,
                )
                for name in ("x", "y", "z")
            ]
            setup.add_all(users)
            setup.flush()
            x_id, y_id, z_id = (user.id for user in users)
            project = Project(name="Race", admin_id=x_id)
            setup.add(project)
            setup.flush()
            setup.add_all(
                [
                    ProjectMember(
                        project_id=project.id,
                        user_id=user_id,
                        role=MemberRole.ADMIN if user_id == x_id else MemberRole.EXPERT,
                    )
                    for user_id in (x_id, y_id, z_id)
                ]
            )
            setup.commit()
            project_id = project.id

        with Session(pg_engine) as session_b, Session(pg_engine) as session_a:
            project_b = session_b.get(Project, project_id)
            assert project_b.admin_id == x_id

            # WHEN another request transfers the project to Y and commits first
            ProjectService(session_a).transfer_ownership(session_a.get(Project, project_id), y_id)

            # THEN the stale request is refused
            with pytest.raises(ProjectOwnershipChangedError):
                ProjectService(session_b).transfer_ownership(project_b, z_id)

        self._assert_ownership_settled(pg_engine, project_id, y_id)


class TestAccountErasureAfterTransfer:
    """Deleting the account of an owner who handed the project over."""

    def test_the_old_owner_can_delete_the_account_and_the_project_keeps_one_admin(self, pg_engine):
        """
        GIVEN an owner who transferred the project to an expert
        WHEN the former owner deletes the account
        THEN both steps succeed, and the project stays with exactly one admin, the expert
        """
        # GIVEN
        with Session(pg_engine) as setup:
            owner = User(
                email="owner@example.com", hashed_password="x", first_name="O", last_name="O"
            )
            expert = User(
                email="expert@example.com", hashed_password="x", first_name="E", last_name="E"
            )
            setup.add_all([owner, expert])
            setup.flush()
            project = add_project(setup, owner, name="Handed over")
            setup.add(
                ProjectMember(project_id=project.id, user_id=expert.id, role=MemberRole.EXPERT)
            )
            setup.commit()
            project_id, owner_id, expert_id = project.id, owner.id, expert.id

        # WHEN
        with Session(pg_engine) as session:
            ProjectService(session).transfer_ownership(session.get(Project, project_id), expert_id)
        with Session(pg_engine) as session:
            UserService(session).delete_user(
                session.get(User, owner_id), CalculationService(session)
            )

        # THEN
        with Session(pg_engine) as check:
            assert check.get(User, owner_id) is None
            assert check.get(Project, project_id).admin_id == expert_id
            members = check.exec(
                select(ProjectMember).where(ProjectMember.project_id == project_id)
            ).all()
            assert [(m.user_id, m.role) for m in members] == [(expert_id, MemberRole.ADMIN)]


class TestSavepointAndPartialRollback:
    """Tests for SAVEPOINT functionality in PostgreSQL."""

    def test_savepoint_partial_rollback(self, pg_session):
        """
        GIVEN a transaction with multiple operations
        WHEN one operation fails within a SAVEPOINT
        THEN only that operation is rolled back, not the entire transaction

        Uses begin_nested() for SAVEPOINT functionality.
        """
        # GIVEN: create first user successfully
        user1 = User(
            email="first@example.com",
            hashed_password="hash",
            first_name="First",
            last_name="User",
        )
        pg_session.add(user1)
        pg_session.commit()

        # WHEN: try to add duplicate in nested transaction (SAVEPOINT)
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

        # THEN: user1 and user2 should exist, duplicate should not
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
        # GIVEN: Session 1 creates user but does NOT commit
        session1 = scoped_session(sessionmaker(bind=pg_engine))
        user = User(
            email="uncommitted@example.com",
            hashed_password="hash",
            first_name="Uncommitted",
            last_name="Test",
        )
        session1.add(user)
        session1.flush()  # Write to DB but don't commit

        # WHEN: Session 2 queries for the user
        session2 = scoped_session(sessionmaker(bind=pg_engine))
        found_user = (
            session2.execute(select(User).where(User.email == "uncommitted@example.com"))
            .scalars()
            .first()
        )

        # THEN: uncommitted user is not visible
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
