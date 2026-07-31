"""Registration policy for accounts that are activated by email."""

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from api.auth.password import hash_password
from api.db.models import User
from api.exceptions import UserExistsError
from api.services.email_verification_service import PendingCredentials
from api.services.user_service import UserService


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    """What a registration submission needs the endpoint to do next.

    ``user`` and ``credentials`` are set together: either there is an account waiting
    for an activation link and a submission for that link to carry, or neither.

    :param user: The account that needs an activation link, or None when a verified
        account already owns the address and should get a notice instead.
    :param credentials: The submitted details for the activation link to carry, or
        None when there is nothing to activate.
    :param created: Whether this submission is the one that created the account.
    """

    user: User | None
    credentials: PendingCredentials | None
    created: bool


class RegistrationService:
    """Apply a registration submission to the account store.

    An address can be in one of three states, and the endpoint answers identically for
    all three, so this class holds the branch that decides what actually happens:

    ===================  =========================================================
    Address              Effect
    ===================  =========================================================
    free                 A new, unverified account is created.
    taken, unverified    Nothing is written; the submission rides on its own token.
    taken, verified      Nothing is written.
    ===================  =========================================================

    The middle row is a security requirement. Storing the newest submission's password
    on the account would let anyone take over a pending signup: submit the victim's
    address, wait for the victim to click the activation link they already have, and
    the account opens with the attacker's password. The submission is therefore carried
    by the activation link it minted and applied only when *that* link is redeemed, so
    a link always activates the submission it belongs to and no submitter decides what
    another submitter's link opens.

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
    ) -> RegistrationResult:
        """Apply a registration submission and report what still needs activating.

        Runs bcrypt exactly once in every branch, including the one that writes
        nothing: hashing costs 100-300 ms, so a branch that skipped it would answer
        measurably faster and re-leak through timing exactly what the identical
        response body hides.

        Blocking work throughout (bcrypt plus the account write), so the caller runs
        this in a worker thread rather than on the event loop.

        :param email: Submitted email address (normalized by the user service).
        :param password: Submitted plain text password.
        :param first_name: Submitted first name.
        :param last_name: Submitted last name.
        :return: What the endpoint should mail, and to which account.
        """
        existing = self._users.get_by_email(email)

        if existing is None:
            created = self._create_account(email, password, first_name, last_name)
            if created is not None:
                return RegistrationResult(
                    user=created,
                    credentials=PendingCredentials(
                        hashed_password=created.hashed_password,
                        first_name=first_name,
                        last_name=last_name,
                    ),
                    created=True,
                )
            existing = self._users.get_by_email(email)

        if existing is not None and existing.email_verified_at is None:
            return RegistrationResult(
                user=existing,
                credentials=PendingCredentials(
                    hashed_password=hash_password(password),
                    first_name=first_name,
                    last_name=last_name,
                ),
                created=False,
            )

        # Nothing to write. Hash the submitted password and throw the result away so
        # this branch costs what the other two cost -- see the timing note above.
        hash_password(password)
        return RegistrationResult(user=None, credentials=None, created=False)

    def _create_account(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
    ) -> User | None:
        """Create the account for an address that looked free, if it still is.

        :param email: Submitted email address.
        :param password: Submitted plain text password.
        :param first_name: Submitted first name.
        :param last_name: Submitted last name.
        :return: The new account, or None when a concurrent submission got there
            first and the caller should carry on down the taken-address path.
        """
        try:
            return self._users.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
        except (UserExistsError, IntegrityError):
            # Two submissions raced for the same free address. The duplicate would
            # otherwise surface as a 409 naming the address, or as a 500 from the
            # unique index -- both of them answers this endpoint must never give,
            # since a caller can tell them apart from the uniform 202. Roll the failed
            # insert back so the session is usable and take the taken-address path.
            self._users.session.rollback()
            return None
