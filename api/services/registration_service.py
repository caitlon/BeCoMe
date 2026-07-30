"""Registration policy for accounts that are activated by email."""

import logging

from api.auth.password import hash_password
from api.db.models import User
from api.services.user_service import UserService

logger = logging.getLogger("api.service.registration")


class RegistrationService:
    """Apply a registration submission to the account store.

    An address can be in one of three states, and the endpoint answers identically for
    all three, so this class holds the branch that decides what actually happens:

    ===================  =========================================================
    Address              Effect
    ===================  =========================================================
    free                 A new, unverified account is created.
    taken, unverified    The stored password and names are replaced by this signup.
    taken, verified      Nothing is written.
    ===================  =========================================================

    The middle row is a security requirement, not a convenience. If a taken but
    unverified address merely re-sent the existing activation link, an attacker could
    pre-register ``victim@example.com`` with a password of their own choosing; the real
    owner would later receive a legitimate-looking activation mail, click it, and land in
    an account whose password the attacker knows. Nobody has proven control of the
    address yet, so the most recent registrant's credentials win and only whoever holds
    the mailbox can turn them into a usable account.

    :param users: User service performing the account writes.
    """

    def __init__(self, users: UserService) -> None:
        """Initialize with the user service the writes go through.

        :param users: User service performing the account writes.
        """
        self._users = users

    def register(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
    ) -> User | None:
        """Apply a registration submission and report what still needs activating.

        Runs bcrypt in every branch, including the one that writes nothing: the two
        writing branches spend 100-300 ms hashing, and a third branch that skipped it
        would answer measurably faster, re-leaking through timing exactly what the
        identical response body hides.

        Blocking work throughout (bcrypt plus the account write), so the caller runs
        this in a worker thread rather than on the event loop.

        :param email: Submitted email address (normalized by the user service).
        :param password: Submitted plain text password.
        :param first_name: Submitted first name.
        :param last_name: Submitted last name.
        :return: The account that now needs an activation link, or None when a verified
            account already owns the address and should get a notice instead.
        """
        existing = self._users.get_by_email(email)

        if existing is None:
            return self._users.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )

        if existing.email_verified_at is None:
            return self._users.overwrite_unverified_account(
                existing,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )

        # Nothing to write. Hash the submitted password and throw the result away so
        # this branch costs what the other two cost -- see the timing note above.
        hash_password(password)
        logger.info(
            "Registration attempted on a verified account",
            extra={"event": "registration_on_verified_account"},
        )
        return None
