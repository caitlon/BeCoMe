"""A demo account must be invisible to every lookup that resolves an email address.

Demo accounts exist only to hold the opinions in the seeded example project, and each
of them sits in the example project of every user on the platform. A lookup that could
find one would let an outsider invite it into a real project, or -- through the branch
of registration that treats a known-but-unverified address as an unfinished signup --
claim it outright and read every one of those projects. Four call sites resolve an
address, and all four go through one helper so a fifth cannot forget.
"""

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from api.auth.password import hash_password
from api.data.example_project import EXAMPLE_EXPERTS
from api.db.models import Project, User
from api.exceptions import UserNotFoundForInvitationError
from api.services.email_verification_service import EmailVerificationService
from api.services.invitation_service import InvitationService
from api.services.password_reset_service import PasswordResetService
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

        # WHEN / THEN
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
