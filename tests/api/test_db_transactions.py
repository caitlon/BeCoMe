"""Tests for transaction and session lifecycle behavior."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from api.db.models import Project, User


class TestTransactionRollback:
    """Tests for transaction rollback behavior."""

    def test_integrity_error_rolls_back_transaction(self, session):
        """
        GIVEN a valid user already in database
        WHEN trying to add duplicate email
        THEN integrity error is raised
        """
        # GIVEN
        user1 = User(
            email="test@example.com",
            hashed_password="hash",
            first_name="Test",
            last_name="User",
        )
        session.add(user1)
        session.commit()

        # WHEN
        user2 = User(
            email="test@example.com",
            hashed_password="hash2",
            first_name="Another",
            last_name="User",
        )
        session.add(user2)

        # THEN
        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()

    def test_session_usable_after_rollback(self, session):
        """
        GIVEN a session that encountered IntegrityError
        WHEN rolled back
        THEN session can be reused for new operations
        """
        # GIVEN - cause an error
        user1 = User(
            email="unique@example.com",
            hashed_password="hash",
            first_name="Test",
            last_name="User",
        )
        session.add(user1)
        session.commit()

        user2 = User(
            email="unique@example.com",
            hashed_password="hash",
            first_name="Dup",
            last_name="User",
        )
        session.add(user2)

        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # WHEN - try new operation
        user3 = User(
            email="different@example.com",
            hashed_password="hash",
            first_name="New",
            last_name="User",
        )
        session.add(user3)
        session.commit()

        # THEN - should succeed
        result = session.exec(select(User).where(User.email == "different@example.com")).first()
        assert result is not None
        assert result.email == "different@example.com"

    def test_flush_without_commit_not_persisted(self, test_engine):
        """
        GIVEN entities flushed but not committed
        WHEN session closes without commit
        THEN changes are not persisted
        """
        from sqlmodel import Session

        user_email = "flush_test@example.com"

        # GIVEN - create and flush without commit
        with Session(test_engine) as session1:
            user = User(
                email=user_email,
                hashed_password="hash",
                first_name="Flush",
                last_name="Test",
            )
            session1.add(user)
            session1.flush()
            # Session closes without commit

        # WHEN - new session checks for user
        with Session(test_engine) as session2:
            result = session2.exec(select(User).where(User.email == user_email)).first()

            # THEN - user should not exist
            assert result is None

    def test_partial_add_rolled_back_on_error(self, session):
        """
        GIVEN multiple entities added to session
        WHEN commit fails due to constraint
        THEN all added entities are rolled back
        """
        # GIVEN - first user commits successfully
        user1 = User(
            email="first@example.com",
            hashed_password="hash",
            first_name="First",
            last_name="User",
        )
        session.add(user1)
        session.commit()

        # Add project (valid) and duplicate user (invalid) together
        project = Project(
            name="Will Be Rolled Back",
            admin_id=user1.id,
        )
        user_duplicate = User(
            email="first@example.com",  # Duplicate
            hashed_password="hash2",
            first_name="Duplicate",
            last_name="User",
        )
        session.add(project)
        session.add(user_duplicate)

        # WHEN
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # THEN - project should not exist
        result = session.exec(select(Project).where(Project.name == "Will Be Rolled Back")).first()
        assert result is None
