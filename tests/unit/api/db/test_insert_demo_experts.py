"""Unit tests for insert_demo_experts, the test-side equivalent of the migration seed.

Production gets the demo pool from the migration
(``migrations/versions/2026_08_22_1200-c4e81f7a9d23_add_example_project_support.py``).
Tests build their schema with ``SQLModel.metadata.create_all``, which carries no data,
so they call ``insert_demo_experts`` instead. Nothing ties the two together, so this
checks the helper reproduces the same properties
``tests/integration/api/db/test_migrations.py::TestExampleProjectSupportMigration``
proves about the migration -- if the two ever drift, every test that calls this helper
would otherwise go on validating a pool shape production does not have.
"""

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from api.data.example_project import EXAMPLE_EXPERTS
from api.db.models import User
from tests.shared.helpers import insert_demo_experts


@pytest.fixture
def session():
    """In-memory SQLite session with all tables created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


class TestInsertDemoExperts:
    """insert_demo_experts, checked against the migration's own proven properties."""

    def test_creates_the_full_pool_already_verified(self, session):
        """Row count, the exact email set, is_demo, and email_verified_at all match.

        A NULL ``email_verified_at`` is what registration treats as an unfinished
        signup (see ``RegistrationService``), so a verified pool is a security
        property of this helper, not incidental shape.
        """
        # GIVEN / WHEN
        insert_demo_experts(session)

        # THEN
        users = session.exec(select(User)).all()
        assert len(users) == len(EXAMPLE_EXPERTS)
        assert {user.email for user in users} == {expert.email for expert in EXAMPLE_EXPERTS}
        assert all(user.is_demo is True for user in users)
        assert all(user.email_verified_at is not None for user in users)
