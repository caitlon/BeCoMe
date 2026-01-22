"""User business logic service."""

from uuid import UUID

from sqlmodel import select

from api.auth.password import hash_password, verify_password
from api.db.models import User
from api.exceptions import InvalidCredentialsError, UserExistsError
from api.services.base import BaseService


class UserService(BaseService):
    """Service for user-related operations."""

    def create_user(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str | None = None,
    ) -> User:
        """Create a new user account.

        :param email: User email address
        :param password: Plain text password (will be hashed)
        :param first_name: User's first name
        :param last_name: User's last name (optional)
        :return: Created User instance
        :raises UserExistsError: If email already registered
        """
        existing = self.get_by_email(email)
        if existing:
            raise UserExistsError(f"User with email {email} already exists")

        user = User(
            email=email,
            hashed_password=hash_password(password),
            first_name=first_name,
            last_name=last_name,
        )
        self._session.add(user)
        self._session.commit()
        self._session.refresh(user)
        return user

    def get_by_email(self, email: str) -> User | None:
        """Find user by email address.

        :param email: Email to search for
        :return: User if found, None otherwise
        """
        statement = select(User).where(User.email == email)
        return self._session.exec(statement).first()

    def get_by_id(self, user_id: UUID) -> User | None:
        """Find user by ID.

        :param user_id: User UUID
        :return: User if found, None otherwise
        """
        return self._session.get(User, user_id)

    def authenticate(self, email: str, password: str) -> User:
        """Authenticate user with email and password.

        :param email: User email
        :param password: Plain text password
        :return: Authenticated User
        :raises InvalidCredentialsError: If email not found or password incorrect
        """
        user = self.get_by_email(email)
        if not user:
            raise InvalidCredentialsError("Invalid email or password")
        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Invalid email or password")
        return user

    def update_user(
        self,
        user: User,
        first_name: str | None = None,
        last_name: str | None = None,
        photo_url: str | None = None,
    ) -> User:
        """Update user profile fields.

        :param user: User to update
        :param first_name: New first name (optional)
        :param last_name: New last name (optional)
        :param photo_url: New photo URL (optional)
        :return: Updated User instance
        """
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if photo_url is not None:
            user.photo_url = photo_url

        self._session.add(user)
        self._session.commit()
        self._session.refresh(user)
        return user

    def change_password(self, user: User, current_password: str, new_password: str) -> User:
        """Change user password.

        :param user: User to update
        :param current_password: Current password for verification
        :param new_password: New password
        :return: Updated User instance
        :raises InvalidCredentialsError: If current password is incorrect
        """
        if not verify_password(current_password, user.hashed_password):
            raise InvalidCredentialsError("Current password is incorrect")

        user.hashed_password = hash_password(new_password)
        self._session.add(user)
        self._session.commit()
        self._session.refresh(user)
        return user

    def delete_user(self, user: User) -> None:
        """Delete user account.

        :param user: User to delete
        """
        self._session.delete(user)
        self._session.commit()
