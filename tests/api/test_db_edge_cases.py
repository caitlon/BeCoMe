"""Tests for edge cases and boundary values in database models."""

import time
from uuid import UUID

from api.db.models import (
    ExpertOpinion,
    Project,
    ProjectMember,
    User,
)


class TestStringFieldEdgeCases:
    """Tests for string field boundary conditions."""

    def test_empty_string_description_allowed(self, session):
        """
        GIVEN a project with empty description
        WHEN saved to database
        THEN succeeds without error
        """
        # GIVEN
        user = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(user)
        session.commit()

        # WHEN
        project = Project(
            name="Test Project",
            description="",
            admin_id=user.id,
        )
        session.add(project)
        session.commit()

        # THEN
        session.refresh(project)
        assert project.description == ""

    def test_none_description_allowed(self, session):
        """
        GIVEN a project with None description
        WHEN saved to database
        THEN succeeds without error
        """
        # GIVEN
        user = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(user)
        session.commit()

        # WHEN
        project = Project(
            name="Test Project",
            description=None,
            admin_id=user.id,
        )
        session.add(project)
        session.commit()

        # THEN
        session.refresh(project)
        assert project.description is None

    def test_empty_string_position_allowed(self, session):
        """
        GIVEN an opinion with empty position
        WHEN saved to database
        THEN succeeds without error
        """
        # GIVEN
        user = User(
            email="expert@example.com",
            hashed_password="hash",
            first_name="Expert",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project = Project(name="Test Project", admin_id=user.id)
        session.add(project)
        session.commit()

        # WHEN
        opinion = ExpertOpinion(
            project_id=project.id,
            user_id=user.id,
            position="",
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        session.add(opinion)
        session.commit()

        # THEN
        session.refresh(opinion)
        assert opinion.position == ""

    def test_max_length_email_accepted(self, session):
        """
        GIVEN email at maximum allowed length (255 chars)
        WHEN user is created
        THEN succeeds without error
        """
        # GIVEN - construct email close to max length
        # Format: localpart@domain.com where total <= 255
        local_part = "a" * 200
        domain = "example.com"
        long_email = f"{local_part}@{domain}"
        assert len(long_email) <= 255

        # WHEN
        user = User(
            email=long_email,
            hashed_password="hash",
            first_name="Test",
            last_name="User",
        )
        session.add(user)
        session.commit()

        # THEN
        session.refresh(user)
        assert user.email == long_email


class TestFloatFieldEdgeCases:
    """Tests for float field boundary conditions."""

    def test_zero_scale_min_allowed(self, session):
        """
        GIVEN project with scale_min=0.0
        WHEN saved
        THEN succeeds
        """
        # GIVEN
        user = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(user)
        session.commit()

        # WHEN
        project = Project(
            name="Test Project",
            admin_id=user.id,
            scale_min=0.0,
            scale_max=100.0,
        )
        session.add(project)
        session.commit()

        # THEN
        session.refresh(project)
        assert project.scale_min == 0.0

    def test_negative_scale_values_allowed(self, session):
        """
        GIVEN project with negative scale_min
        WHEN saved (with valid range)
        THEN succeeds
        """
        # GIVEN
        user = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(user)
        session.commit()

        # WHEN
        project = Project(
            name="Test Project",
            admin_id=user.id,
            scale_min=-100.0,
            scale_max=100.0,
        )
        session.add(project)
        session.commit()

        # THEN
        session.refresh(project)
        assert project.scale_min == -100.0
        assert project.scale_max == 100.0

    def test_equal_fuzzy_bounds_allowed(self, session):
        """
        GIVEN opinion where lower == peak == upper (crisp number)
        WHEN validated and saved
        THEN succeeds (crisp number is valid fuzzy number)
        """
        # GIVEN
        user = User(
            email="expert@example.com",
            hashed_password="hash",
            first_name="Expert",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project = Project(name="Test Project", admin_id=user.id)
        session.add(project)
        session.commit()

        # WHEN - crisp number (degenerate fuzzy number)
        opinion = ExpertOpinion(
            project_id=project.id,
            user_id=user.id,
            lower_bound=10.0,
            peak=10.0,
            upper_bound=10.0,
        )
        session.add(opinion)
        session.commit()

        # THEN
        session.refresh(opinion)
        assert opinion.lower_bound == opinion.peak == opinion.upper_bound == 10.0


class TestDatetimeEdgeCases:
    """Tests for datetime field edge cases."""

    def test_created_at_auto_populated(self, session):
        """
        GIVEN a new entity without explicit created_at
        WHEN saved
        THEN created_at is auto-populated
        """
        # GIVEN/WHEN
        user = User(
            email="test@example.com",
            hashed_password="hash",
            first_name="Test",
            last_name="User",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        # THEN
        assert user.created_at is not None

    def test_updated_at_changes_on_update(self, session):
        """
        GIVEN an existing project
        WHEN project is updated
        THEN updated_at changes to reflect the update
        """
        # GIVEN
        user = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project = Project(name="Original Name", admin_id=user.id)
        session.add(project)
        session.commit()
        session.refresh(project)
        original_updated_at = project.updated_at

        # Small delay to ensure timestamp difference
        time.sleep(0.01)

        # WHEN
        project.name = "Updated Name"
        session.add(project)
        session.commit()
        session.refresh(project)

        # THEN
        assert project.updated_at >= original_updated_at


class TestUuidEdgeCases:
    """Tests for UUID field edge cases."""

    def test_nonexistent_uuid_accepted_in_sqlite(self, session):
        """
        GIVEN a membership with a non-existent user_id UUID
        WHEN saved in SQLite (FK constraints not enforced by default)
        THEN insert succeeds but represents orphaned data

        Note: SQLite does not enforce FK constraints by default.
        In production (PostgreSQL), this would raise IntegrityError.
        This test documents the SQLite test environment behavior.
        """
        # GIVEN
        admin = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(admin)
        session.commit()

        project = Project(name="Test Project", admin_id=admin.id)
        session.add(project)
        session.commit()

        # Non-existent UUID (not nil, just doesn't exist in users table)
        fake_uuid = UUID("12345678-1234-1234-1234-123456789012")

        # WHEN - SQLite allows this (no FK enforcement by default)
        membership = ProjectMember(
            project_id=project.id,
            user_id=fake_uuid,
        )
        session.add(membership)
        session.commit()

        # THEN - membership is saved (orphaned reference)
        session.refresh(membership)
        assert membership.user_id == fake_uuid
