"""Unit tests for RegistrationService."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from api.db.models import User
from api.exceptions import UserExistsError
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

    def test_creates_the_account_and_carries_its_credentials_on_the_link(self):
        # GIVEN
        users = MagicMock(spec=UserService)
        users.get_by_email.return_value = None
        created = _account(verified=False)
        users.create_user.return_value = created

        # WHEN
        result = RegistrationService(users).register(**SUBMISSION)

        # THEN
        assert result.user is created
        assert result.created is True
        users.create_user.assert_called_once_with(**SUBMISSION)

        # AND: the link carries the hash the account write already computed, so the
        # branch spends exactly one bcrypt like the other two
        assert result.credentials is not None
        assert result.credentials.hashed_password == created.hashed_password
        assert result.credentials.first_name == SUBMISSION["first_name"]
        assert result.credentials.last_name == SUBMISSION["last_name"]


class TestTakenUnverifiedAddress:
    """A repeat signup on an unactivated address writes nothing."""

    def test_leaves_the_account_alone_and_puts_the_submission_on_the_link(self):
        """The stored account is untouched; the new details ride on the new token.

        Writing them to the account is the account-takeover primitive this design
        exists to remove: the newest submitter would decide what the activation link
        the rightful owner already holds opens.
        """
        # GIVEN
        users = MagicMock(spec=UserService)
        existing = _account(verified=False)
        users.get_by_email.return_value = existing

        # WHEN
        result = RegistrationService(users).register(**SUBMISSION)

        # THEN
        assert result.user is existing
        assert result.created is False
        users.create_user.assert_not_called()
        assert existing.hashed_password == "stored-hash"
        assert existing.first_name == "Stored"

        # AND: the submission is carried by the link instead
        assert result.credentials is not None
        assert result.credentials.hashed_password != "stored-hash"
        assert result.credentials.first_name == SUBMISSION["first_name"]
        assert result.credentials.last_name == SUBMISSION["last_name"]


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
        assert result.user is None
        assert result.created is False
        users.create_user.assert_not_called()

    def test_still_runs_bcrypt_so_the_branch_cannot_be_timed(self):
        """The branch that stores nothing must cost what the storing branches cost.

        The hash has nowhere to go here -- no link is minted -- but skipping it would
        make the endpoint answer a live address hundreds of milliseconds faster than a
        free one, re-leaking by timing exactly what the identical response body hides.
        Carrying it on the result is what keeps it from looking like a line to delete.
        """
        # GIVEN
        users = MagicMock(spec=UserService)
        users.get_by_email.return_value = _account(verified=True)

        # WHEN
        with patch("api.services.registration_service.hash_password") as mock_hash:
            result = RegistrationService(users).register(**SUBMISSION)

        # THEN
        mock_hash.assert_called_once_with(SUBMISSION["password"])
        assert result.credentials.hashed_password is mock_hash.return_value


class TestConcurrentSignupsForOneFreeAddress:
    """Two submissions racing for the same free address still answer uniformly."""

    @pytest.mark.parametrize(
        "failure",
        [
            UserExistsError("User with email someone@example.com already exists"),
            IntegrityError("INSERT INTO users", {}, Exception("duplicate key")),
        ],
        ids=["service_check_lost_the_race", "unique_index_rejected_the_insert"],
    )
    def test_falls_through_to_the_taken_path_instead_of_conflicting(self, failure):
        """Losing the race must not surface as a 409 or a 500 from this endpoint.

        Both of those are answers a caller can tell apart from the uniform 202, which
        would hand back the account-existence bit the flow removes.
        """
        # GIVEN: the address looks free, then the insert loses to a concurrent one
        users = MagicMock(spec=UserService)
        winner = _account(verified=False)
        users.get_by_email.side_effect = [None, winner]
        users.create_user.side_effect = failure

        # WHEN
        result = RegistrationService(users).register(**SUBMISSION)

        # THEN: treated as a second submission on an unactivated address
        assert result.user is winner
        assert result.created is False
        assert result.credentials is not None
        users.session.rollback.assert_called_once()

    def test_treats_a_winner_that_vanished_again_as_nothing_to_activate(self):
        """A row that disappears between the failed insert and the re-read mails a notice.

        Deleting an account in that window is not something the API exposes, but the
        endpoint still has to answer 202 rather than raise.
        """
        # GIVEN
        users = MagicMock(spec=UserService)
        users.get_by_email.side_effect = [None, None]
        users.create_user.side_effect = UserExistsError("already exists")

        # WHEN
        result = RegistrationService(users).register(**SUBMISSION)

        # THEN
        assert result.user is None
        assert result.created is False
