"""Tests for User and PasswordResetToken models."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from api.db.models import PasswordResetToken, User


class TestUserModel:
    """Tests for User model."""

    def test_invalid_email_format_raises_error(self):
        """
        GIVEN invalid email format
        WHEN User is validated
        THEN ValidationError is raised
        """
        from pydantic import ValidationError

        # WHEN/THEN
        with pytest.raises(ValidationError, match="Invalid email format"):
            User.model_validate(
                {
                    "email": "not-an-email",
                    "hashed_password": "hash",
                    "first_name": "Test",
                    "last_name": "User",
                }
            )

    def test_valid_email_passes_validation(self):
        """
        GIVEN valid email format
        WHEN User is validated
        THEN User is created successfully
        """
        # WHEN
        user = User.model_validate(
            {
                "email": "valid@example.com",
                "hashed_password": "hash",
                "first_name": "Test",
                "last_name": "User",
            }
        )

        # THEN
        assert user.email == "valid@example.com"

    def test_create_user(self, session):
        # GIVEN
        user = User(
            email="test@example.com",
            hashed_password="hashed123",
            first_name="John",
            last_name="Doe",
        )

        # WHEN
        session.add(user)
        session.commit()
        session.refresh(user)

        # THEN
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.created_at is not None

    def test_user_email_unique(self, session):
        # GIVEN
        user1 = User(
            email="unique@example.com",
            hashed_password="hash1",
            first_name="First",
            last_name="User",
        )
        user2 = User(
            email="unique@example.com",
            hashed_password="hash2",
            first_name="Second",
            last_name="User",
        )
        session.add(user1)
        session.commit()

        # WHEN/THEN
        session.add(user2)
        with pytest.raises(IntegrityError):
            session.commit()


class TestPasswordResetTokenModel:
    """Tests for PasswordResetToken model."""

    def test_create_reset_token(self, session):
        # GIVEN
        user = User(
            email="user@example.com",
            hashed_password="hash",
            first_name="Test",
            last_name="User",
        )
        session.add(user)
        session.commit()

        # WHEN
        token = PasswordResetToken(
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        session.add(token)
        session.commit()
        session.refresh(token)

        # THEN
        assert token.token is not None
        assert token.used_at is None
        assert token.user_id == user.id

    def test_reset_token_unique(self, session):
        # GIVEN
        user = User(
            email="user@example.com",
            hashed_password="hash",
            first_name="Test",
            last_name="User",
        )
        session.add(user)
        session.commit()

        shared_token = uuid4()

        token1 = PasswordResetToken(
            user_id=user.id,
            token=shared_token,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        session.add(token1)
        session.commit()

        # WHEN/THEN - duplicate token should fail
        token2 = PasswordResetToken(
            user_id=user.id,
            token=shared_token,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        session.add(token2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_user_can_have_multiple_reset_tokens(self, session):
        # GIVEN
        user = User(
            email="user@example.com",
            hashed_password="hash",
            first_name="Test",
            last_name="User",
        )
        session.add(user)
        session.commit()

        # WHEN - multiple tokens for same user (e.g., requested reset twice)
        token1 = PasswordResetToken(
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        token2 = PasswordResetToken(
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        )
        session.add_all([token1, token2])
        session.commit()

        # THEN
        session.refresh(user)
        assert len(user.reset_tokens) == 2
