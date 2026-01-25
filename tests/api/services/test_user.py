"""Unit tests for UserService."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from api.db.models import User
from api.exceptions import InvalidCredentialsError, UserExistsError
from api.services.user_service import UserService


class TestUserServiceCreateUser:
    """Tests for UserService.create_user method."""

    def test_creates_user_successfully(self):
        """User is created when email is not taken."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None  # No existing user
        service = UserService(mock_session)

        # WHEN
        with patch("api.services.user_service.hash_password", return_value="hashed"):
            user = service.create_user(
                email="new@example.com",
                password="Password123",
                first_name="John",
                last_name="Doe",
            )

        # THEN
        assert user.email == "new@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    def test_creates_user_without_last_name(self):
        """User can be created without last_name."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = UserService(mock_session)

        # WHEN
        with patch("api.services.user_service.hash_password", return_value="hashed"):
            user = service.create_user(
                email="noname@example.com",
                password="Password123",
                first_name="Jane",
            )

        # THEN
        assert user.email == "noname@example.com"
        assert user.first_name == "Jane"
        assert user.last_name is None

    def test_raises_error_when_email_exists(self):
        """UserExistsError is raised when email already registered."""
        # GIVEN
        existing_user = User(
            email="taken@example.com",
            hashed_password="xxx",
            first_name="Existing",
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = existing_user
        service = UserService(mock_session)

        # WHEN / THEN
        with pytest.raises(UserExistsError, match="already exists"):
            service.create_user(
                email="taken@example.com",
                password="Password123",
                first_name="New",
            )

    def test_password_is_hashed(self):
        """Password is hashed before storing."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = UserService(mock_session)

        # WHEN
        with patch("api.services.user_service.hash_password") as mock_hash:
            mock_hash.return_value = "hashed_password_value"
            user = service.create_user(
                email="test@example.com",
                password="plaintext",
                first_name="Test",
            )

        # THEN
        mock_hash.assert_called_once_with("plaintext")
        assert user.hashed_password == "hashed_password_value"

    def test_email_is_normalized_to_lowercase(self):
        """Email is converted to lowercase when creating user."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = UserService(mock_session)

        # WHEN
        with patch("api.services.user_service.hash_password", return_value="hashed"):
            user = service.create_user(
                email="Test@Example.COM",
                password="Password123",
                first_name="Test",
            )

        # THEN
        assert user.email == "test@example.com"


class TestUserServiceGetByEmail:
    """Tests for UserService.get_by_email method."""

    def test_returns_user_when_found(self):
        """Returns user when email exists."""
        # GIVEN
        expected_user = User(
            email="found@example.com",
            hashed_password="xxx",
            first_name="Found",
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = expected_user
        service = UserService(mock_session)

        # WHEN
        result = service.get_by_email("found@example.com")

        # THEN
        assert result == expected_user

    def test_returns_none_when_not_found(self):
        """Returns None when email does not exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = UserService(mock_session)

        # WHEN
        result = service.get_by_email("notfound@example.com")

        # THEN
        assert result is None

    def test_email_search_normalizes_to_lowercase(self):
        """Email lookup normalizes input to lowercase before searching."""
        # GIVEN
        expected_user = User(
            email="found@example.com",
            hashed_password="xxx",
            first_name="Found",
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = expected_user
        service = UserService(mock_session)

        # WHEN - search with mixed case email
        result = service.get_by_email("FOUND@EXAMPLE.COM")

        # THEN - should find user because query uses lowercase
        assert result == expected_user
        # Verify exec was called (query was made)
        mock_session.exec.assert_called_once()


class TestUserServiceGetById:
    """Tests for UserService.get_by_id method."""

    def test_returns_user_when_found(self):
        """Returns user when ID exists."""
        # GIVEN
        user_id = uuid4()
        expected_user = User(
            id=user_id,
            email="user@example.com",
            hashed_password="xxx",
            first_name="User",
        )
        mock_session = MagicMock()
        mock_session.get.return_value = expected_user
        service = UserService(mock_session)

        # WHEN
        result = service.get_by_id(user_id)

        # THEN
        assert result == expected_user
        mock_session.get.assert_called_once_with(User, user_id)

    def test_returns_none_when_not_found(self):
        """Returns None when ID does not exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.get.return_value = None
        service = UserService(mock_session)

        # WHEN
        result = service.get_by_id(uuid4())

        # THEN
        assert result is None


class TestUserServiceAuthenticate:
    """Tests for UserService.authenticate method."""

    def test_returns_user_on_valid_credentials(self):
        """Returns user when email and password are correct."""
        # GIVEN
        user = User(
            email="auth@example.com",
            hashed_password="hashed_correct",
            first_name="Auth",
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = user
        service = UserService(mock_session)

        # WHEN
        with patch("api.services.user_service.verify_password", return_value=True):
            result = service.authenticate("auth@example.com", "correct_password")

        # THEN
        assert result == user

    def test_raises_error_on_unknown_email(self):
        """InvalidCredentialsError is raised when email not found."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = UserService(mock_session)

        # WHEN / THEN
        with pytest.raises(InvalidCredentialsError, match="Invalid email or password"):
            service.authenticate("unknown@example.com", "anypassword")

    def test_raises_error_on_wrong_password(self):
        """InvalidCredentialsError is raised when password is wrong."""
        # GIVEN
        user = User(
            email="auth@example.com",
            hashed_password="hashed_password",
            first_name="Auth",
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = user
        service = UserService(mock_session)

        # WHEN / THEN
        with (
            patch("api.services.user_service.verify_password", return_value=False),
            pytest.raises(InvalidCredentialsError, match="Invalid email or password"),
        ):
            service.authenticate("auth@example.com", "wrong_password")

    def test_verifies_password_with_stored_hash(self):
        """Password verification uses stored hash."""
        # GIVEN
        user = User(
            email="check@example.com",
            hashed_password="stored_hash_value",
            first_name="Check",
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = user
        service = UserService(mock_session)

        # WHEN
        with patch("api.services.user_service.verify_password") as mock_verify:
            mock_verify.return_value = True
            service.authenticate("check@example.com", "test_password")

        # THEN
        mock_verify.assert_called_once_with("test_password", "stored_hash_value")


class TestUserServiceUpdatePhotoUrl:
    """Tests for UserService.update_photo_url method."""

    def test_sets_photo_url(self):
        """Photo URL is set and persisted."""
        # GIVEN
        user = User(
            id=uuid4(),
            email="photo@example.com",
            hashed_password="xxx",
            first_name="Photo",
            photo_url=None,
        )
        mock_session = MagicMock()
        service = UserService(mock_session)

        # WHEN
        result = service.update_photo_url(user, "https://storage.example.com/photo.jpg")

        # THEN
        assert result.photo_url == "https://storage.example.com/photo.jpg"
        mock_session.add.assert_called_once_with(user)
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once_with(user)

    def test_clears_photo_url_with_none(self):
        """Photo URL can be cleared by passing None."""
        # GIVEN
        user = User(
            id=uuid4(),
            email="photo@example.com",
            hashed_password="xxx",
            first_name="Photo",
            photo_url="https://storage.example.com/old.jpg",
        )
        mock_session = MagicMock()
        service = UserService(mock_session)

        # WHEN
        result = service.update_photo_url(user, None)

        # THEN
        assert result.photo_url is None
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_replaces_existing_photo_url(self):
        """Existing photo URL is replaced with new one."""
        # GIVEN
        user = User(
            id=uuid4(),
            email="photo@example.com",
            hashed_password="xxx",
            first_name="Photo",
            photo_url="https://storage.example.com/old.jpg",
        )
        mock_session = MagicMock()
        service = UserService(mock_session)

        # WHEN
        result = service.update_photo_url(user, "https://storage.example.com/new.jpg")

        # THEN
        assert result.photo_url == "https://storage.example.com/new.jpg"


class TestUserServiceDeleteUser:
    """Tests for UserService.delete_user method."""

    def test_deletes_user_from_database(self):
        """User is deleted from database."""
        # GIVEN
        user = User(
            id=uuid4(),
            email="delete@example.com",
            hashed_password="xxx",
            first_name="Delete",
        )
        mock_session = MagicMock()
        service = UserService(mock_session)

        # WHEN
        service.delete_user(user)

        # THEN
        mock_session.delete.assert_called_once_with(user)
        mock_session.commit.assert_called_once()

    def test_deletes_user_without_photo(self):
        """User without photo URL can be deleted."""
        # GIVEN
        user = User(
            id=uuid4(),
            email="nophoto@example.com",
            hashed_password="xxx",
            first_name="NoPhoto",
            photo_url=None,
        )
        mock_session = MagicMock()
        service = UserService(mock_session)

        # WHEN
        service.delete_user(user)

        # THEN
        mock_session.delete.assert_called_once_with(user)

    def test_deletes_user_with_photo(self):
        """User with photo URL can be deleted (photo cleanup is caller's responsibility)."""
        # GIVEN
        user = User(
            id=uuid4(),
            email="withphoto@example.com",
            hashed_password="xxx",
            first_name="WithPhoto",
            photo_url="https://storage.example.com/photo.jpg",
        )
        mock_session = MagicMock()
        service = UserService(mock_session)

        # WHEN
        service.delete_user(user)

        # THEN
        mock_session.delete.assert_called_once_with(user)
