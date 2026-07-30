"""User business logic service."""

import logging
from uuid import UUID

from sqlmodel import Session, select

from api.auth.password import hash_password, verify_password
from api.db.models import User
from api.exceptions import InvalidCredentialsError, UserExistsError
from api.services.base import BaseService
from api.services.user_cache import UserCacheStore

logger = logging.getLogger("api.service.user")

# Precomputed bcrypt hash verified when an account is missing, so a login for an unknown
# email costs the same time as a wrong password and cannot be told apart by timing.
_DUMMY_PASSWORD_HASH = hash_password("not-a-real-password-timing-equalizer")


class UserService(BaseService):
    """Service for user-related operations."""

    def __init__(self, session: Session, user_cache: UserCacheStore | None = None) -> None:
        """Initialize with a DB session and an optional user cache.

        :param session: SQLModel session for database operations.
        :param user_cache: Cache to invalidate on mutations; ``None`` disables it.
        """
        super().__init__(session)
        self._user_cache = user_cache

    def _invalidate_cache(self, user_id: UUID) -> None:
        """Drop the cached snapshot for ``user_id`` when a cache is configured.

        :param user_id: ID of the user whose cached snapshot should be dropped.
        """
        if self._user_cache is not None:
            self._user_cache.invalidate(user_id)

    def create_user(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str | None = None,
    ) -> User:
        """Create a new user account.

        :param email: User email address (will be normalized to lowercase)
        :param password: Plain text password (will be hashed)
        :param first_name: User's first name
        :param last_name: User's last name (optional)
        :return: Created User instance
        :raises UserExistsError: If email already registered
        """
        normalized_email = email.lower()
        existing = self.get_by_email(normalized_email)
        if existing:
            raise UserExistsError(f"User with email {normalized_email} already exists")

        user = User(
            email=normalized_email,
            hashed_password=hash_password(password),
            first_name=first_name,
            last_name=last_name,
        )
        saved = self._save_and_refresh(user)
        logger.info(
            "User created",
            extra={
                "event": "user_created",
                "user_id": str(saved.id),
            },
        )
        return saved

    def overwrite_unverified_account(
        self,
        user: User,
        password: str,
        first_name: str,
        last_name: str,
    ) -> User:
        """Replace an unverified account's credentials and names with a newer signup.

        Nobody has proven control of the address yet, so the newest registrant's
        details win. See :class:`~api.services.registration_service.RegistrationService`
        for why that is the safe resolution rather than a resend.

        :param user: The existing, still-unverified account.
        :param password: Plain text password from the new registration (will be hashed)
        :param first_name: First name from the new registration
        :param last_name: Last name from the new registration
        :return: The updated User instance
        :raises ValueError: If the account's address is already verified. Overwriting
            one would hand an attacker a live account, so the precondition is checked
            here as well as at the call site.
        """
        if user.email_verified_at is not None:
            raise ValueError("refusing to overwrite an account whose address is verified")

        user.hashed_password = hash_password(password)
        user.first_name = first_name
        user.last_name = last_name
        saved = self._save_and_refresh(user)
        self._invalidate_cache(saved.id)
        logger.info(
            "Unverified account overwritten by a new registration",
            extra={
                "event": "unverified_account_overwritten",
                "user_id": str(saved.id),
            },
        )
        return saved

    def get_by_email(self, email: str) -> User | None:
        """Find user by email address.

        :param email: Email to search for (case-insensitive)
        :return: User if found, None otherwise
        """
        statement = select(User).where(User.email == email.lower())
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
            # Run a bcrypt verification anyway so a missing account is indistinguishable
            # from a wrong password by response time (no user-enumeration oracle).
            verify_password(password, _DUMMY_PASSWORD_HASH)
            raise InvalidCredentialsError(
                "Invalid email or password",
                email=email,
                reason="user_not_found",
            )
        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError(
                "Invalid email or password",
                email=email,
                reason="invalid_password",
            )
        return user

    def update_user(
        self,
        user: User,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        """Update user profile fields.

        :param user: User to update
        :param first_name: New first name (optional)
        :param last_name: New last name (optional)
        :return: Updated User instance
        """
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name

        saved = self._save_and_refresh(user)
        self._invalidate_cache(saved.id)
        return saved

    def verify_current_password(self, user: User, current_password: str) -> None:
        """Check a password against the stored hash without writing anything.

        Split out of :meth:`change_password` so a caller can place its own side effects
        between the check and the write -- the password-change route revokes existing
        sessions in that gap, which must not happen when the check fails.

        :param user: User whose password to verify
        :param current_password: Password to compare against the stored hash
        :raises InvalidCredentialsError: If current password is incorrect
        """
        if not verify_password(current_password, user.hashed_password):
            raise InvalidCredentialsError(
                "Current password is incorrect",
                reason="invalid_current_password",
            )

    def set_password(self, user: User, new_password: str) -> User:
        """Store a new password hash without verifying the previous one.

        :param user: User to update
        :param new_password: New password
        :return: Updated User instance
        """
        user.hashed_password = hash_password(new_password)
        saved = self._save_and_refresh(user)
        self._invalidate_cache(saved.id)
        return saved

    def change_password(self, user: User, current_password: str, new_password: str) -> User:
        """Change user password.

        :param user: User to update
        :param current_password: Current password for verification
        :param new_password: New password
        :return: Updated User instance
        :raises InvalidCredentialsError: If current password is incorrect
        """
        self.verify_current_password(user, current_password)
        return self.set_password(user, new_password)

    def delete_user(self, user: User) -> None:
        """Delete user account.

        :param user: User to delete
        """
        user_id = user.id
        self._delete_and_commit(user)
        self._invalidate_cache(user_id)
        logger.info(
            "User deleted",
            extra={"event": "user_deleted", "user_id": str(user_id)},
        )

    def update_photo_url(self, user: User, photo_key: str | None) -> User:
        """Update the user's stored profile photo key.

        :param user: User to update
        :param photo_key: New storage object key, or None to remove the photo
        :return: Updated User instance
        """
        user.photo_url = photo_key
        saved = self._save_and_refresh(user)
        self._invalidate_cache(saved.id)
        return saved
