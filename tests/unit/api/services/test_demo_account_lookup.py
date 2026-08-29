"""A demo account must be invisible to every lookup that resolves an email address.

Demo accounts exist only to hold the opinions in the seeded example project, and each
of them sits in the example project of every user on the platform. A lookup that could
find one would let an outsider invite it into a real project, or claim it outright and
read every one of those projects through the branch of registration that treats a
known-but-unverified address as an unfinished signup. Four call sites resolve an
address, and all four go through one helper so a fifth cannot forget.
"""

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, col, create_engine, select

from api.auth.password import hash_password
from api.data.example_project import EXAMPLE_EXPERTS
from api.db.models import Project, User
from api.exceptions import UserNotFoundForInvitationError
from api.services.email_verification_service import EmailVerificationService
from api.services.invitation_service import InvitationService
from api.services.password_reset_service import PasswordResetService
from api.services.query_helpers import select_account_by_email
from api.services.registration_service import RegistrationService
from api.services.user_service import UserService
from tests.shared.helpers import insert_demo_experts

DEMO_EMAIL = EXAMPLE_EXPERTS[0].email
REAL_EMAIL = "real.person@example.com"


@pytest.fixture
def session():
    """In-memory SQLite session holding the demo pool and one real account."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        insert_demo_experts(db_session)
        db_session.add(
            User(
                email=REAL_EMAIL,
                hashed_password=hash_password("RealPassword1!"),
                first_name="Real",
                last_name="Person",
            )
        )
        db_session.commit()
        yield db_session
    engine.dispose()


class TestUserServiceLookup:
    """UserService.get_by_email, which registration and login both go through."""

    def test_demo_account_is_not_found(self, session):
        """The address answers exactly as an address nobody registered."""
        # GIVEN
        service = UserService(session)

        # WHEN
        found = service.get_by_email(DEMO_EMAIL)

        # THEN
        assert found is None

    def test_real_account_is_still_found(self, session):
        """The exclusion must not swallow ordinary accounts."""
        # GIVEN
        service = UserService(session)

        # WHEN
        found = service.get_by_email(REAL_EMAIL)

        # THEN
        assert found is not None
        assert found.email == REAL_EMAIL


class TestInvitationLookup:
    """InvitationService.invite_by_email."""

    def test_demo_account_cannot_be_invited(self, session):
        """Inviting a demo expert fails the way an unknown address fails."""
        # GIVEN
        owner = session.exec(select(User).where(User.email == REAL_EMAIL)).first()
        project = Project(name="Real project", admin_id=owner.id)
        session.add(project)
        session.commit()
        session.refresh(project)
        service = InvitationService(session)

        # WHEN/THEN
        with pytest.raises(UserNotFoundForInvitationError):
            service.invite_by_email(
                project_id=project.id,
                inviter_id=owner.id,
                invitee_email=DEMO_EMAIL,
            )


class TestPasswordResetLookup:
    """PasswordResetService.create_reset_token."""

    def test_demo_account_gets_no_reset_token(self, session):
        """No token is minted, so no reset link can ever be produced."""
        # GIVEN
        service = PasswordResetService(session)

        # WHEN
        token = service.create_reset_token(DEMO_EMAIL)

        # THEN
        assert token is None


class TestVerificationLookup:
    """EmailVerificationService.find_unverified_account."""

    def test_demo_account_is_not_pending(self, session):
        """Resending an activation link to a demo address finds nothing to resend."""
        # GIVEN
        service = EmailVerificationService(session)

        # WHEN
        found = service.find_unverified_account(DEMO_EMAIL)

        # THEN
        assert found is None


class TestSelectAccountByEmailHelper:
    """select_account_by_email itself, the one statement all four call sites share.

    ``test_demo_account_is_not_pending`` above exercises this helper only by
    accident: a demo account is inserted already verified, so
    ``find_unverified_account`` returns None from its own already-verified branch
    before the helper's exclusion is ever consulted. Reverting
    ``EmailVerificationService._get_user_by_email`` to an inline query that skips
    the ``is_demo`` filter would leave that test green. Driving the helper
    directly closes that gap for all four call sites at once, since none of them
    do anything but pass its result through.
    """

    def test_demo_address_yields_nothing_and_real_address_is_found(self, session):
        """The exclusion sits in the statement, not in any one caller."""
        # GIVEN/WHEN
        demo_result = session.exec(select_account_by_email(DEMO_EMAIL)).first()
        real_result = session.exec(select_account_by_email(REAL_EMAIL)).first()

        # THEN
        assert demo_result is None
        assert real_result is not None
        assert real_result.email == REAL_EMAIL


class TestRegistrationAgainstDemoAddress:
    """RegistrationService.register, driven with a demo expert's own address.

    This is the spec's central takeover scenario, exercised through the real
    service stack rather than through the shared lookup alone. The address is
    safe today only because three separate mechanisms line up:
    ``select_account_by_email`` excludes it, so registration treats it as free;
    the INSERT that follows then loses to the unique index the demo row already
    occupies; and ``RegistrationService._create_account`` catches that
    ``IntegrityError`` alongside ``UserExistsError`` and rolls back. Narrowing
    that except clause later, to ``UserExistsError`` alone say, would make
    the address claimable while every test above stays green, since none of them
    drives a write through a real database.
    """

    def test_demo_account_cannot_be_registered(self, session):
        """A registration submission against a demo address changes nothing."""
        # GIVEN: the demo account and pool as the fixture seeded them
        demo_before = session.exec(select(User).where(User.email == DEMO_EMAIL)).one()
        demo_count_before = len(session.exec(select(User).where(col(User.is_demo).is_(True))).all())

        # WHEN: someone registers using that address
        result = RegistrationService(UserService(session)).register(
            email=DEMO_EMAIL,
            password="AttackerPass1!",
            first_name="Attacker",
            last_name="Name",
        )

        # THEN: there is no account to activate, the same answer a taken-and-verified
        # address gets
        assert result.user is None
        assert result.created is False

        # AND: no account was created; the demo pool is exactly as large as before
        demo_count_after = len(session.exec(select(User).where(col(User.is_demo).is_(True))).all())
        assert demo_count_after == demo_count_before

        # AND: the demo account's own stored fields were never touched
        demo_after = session.get(User, demo_before.id)
        assert demo_after.hashed_password == demo_before.hashed_password
        assert demo_after.first_name == demo_before.first_name
        assert demo_after.last_name == demo_before.last_name
        assert demo_after.email_verified_at == demo_before.email_verified_at
