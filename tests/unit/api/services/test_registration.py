"""Unit tests for RegistrationService."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from api.db.models import User
from api.services.registration_service import RegistrationService
from api.services.user_service import UserService

SUBMISSION = {
    "email": "someone@example.com",
    "password": "SubmittedPass1!",
    "first_name": "Sub",
    "last_name": "Mitted",
}


def _account(verified: bool) -> User:
    """Build a stored account, verified or not."""
    return User(
        id=uuid4(),
        email="someone@example.com",
        hashed_password="stored-hash",
        first_name="Stored",
        last_name="Owner",
        email_verified_at=datetime(2026, 1, 1, tzinfo=UTC) if verified else None,
    )


class TestFreeAddress:
    """An address nobody holds becomes a new, unverified account."""

    def test_creates_the_account_and_returns_it_for_activation(self):
        # GIVEN
        users = MagicMock(spec=UserService)
        users.get_by_email.return_value = None
        created = _account(verified=False)
        users.create_user.return_value = created

        # WHEN
        result = RegistrationService(users).register(**SUBMISSION)

        # THEN
        assert result is created
        users.create_user.assert_called_once_with(**SUBMISSION)
        users.overwrite_unverified_account.assert_not_called()


class TestTakenUnverifiedAddress:
    """A repeat signup on an address nobody has activated replaces what it holds."""

    def test_overwrites_the_account_and_returns_it_for_activation(self):
        # GIVEN
        users = MagicMock(spec=UserService)
        existing = _account(verified=False)
        users.get_by_email.return_value = existing
        users.overwrite_unverified_account.return_value = existing

        # WHEN
        result = RegistrationService(users).register(**SUBMISSION)

        # THEN
        assert result is existing
        users.create_user.assert_not_called()
        users.overwrite_unverified_account.assert_called_once_with(
            existing,
            password=SUBMISSION["password"],
            first_name=SUBMISSION["first_name"],
            last_name=SUBMISSION["last_name"],
        )


class TestTakenVerifiedAddress:
    """A signup on a live account writes nothing."""

    def test_writes_nothing_and_reports_no_account_to_activate(self):
        # GIVEN
        users = MagicMock(spec=UserService)
        users.get_by_email.return_value = _account(verified=True)

        # WHEN
        with patch("api.services.registration_service.hash_password"):
            result = RegistrationService(users).register(**SUBMISSION)

        # THEN
        assert result is None
        users.create_user.assert_not_called()
        users.overwrite_unverified_account.assert_not_called()

    def test_still_runs_bcrypt_so_the_branch_cannot_be_timed(self):
        """The branch that stores nothing must cost what the storing branches cost.

        Dropping this apparently useless hash would make the endpoint answer a live
        address hundreds of milliseconds faster than a free one, re-leaking by timing
        exactly what the identical response body hides.
        """
        # GIVEN
        users = MagicMock(spec=UserService)
        users.get_by_email.return_value = _account(verified=True)

        # WHEN
        with patch("api.services.registration_service.hash_password") as mock_hash:
            RegistrationService(users).register(**SUBMISSION)

        # THEN
        mock_hash.assert_called_once_with(SUBMISSION["password"])
