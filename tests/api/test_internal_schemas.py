"""Tests for internal Data Transfer Objects."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from api.db.models import (
    ExpertOpinion,
    Invitation,
    MemberRole,
    Project,
    ProjectMember,
    User,
)
from api.schemas.internal import (
    InvitationDetails,
    MemberWithUser,
    OpinionWithUser,
    ProjectWithMemberCount,
    UpsertResult,
)


class TestInvitationDetails:
    """Tests for InvitationDetails DTO."""

    @pytest.fixture
    def invitation_details(self):
        """Create InvitationDetails for testing."""
        admin = User(
            id=uuid4(),
            email="admin@example.com",
            hashed_password="hash",
            first_name="John",
            last_name="Doe",
        )
        project = Project(
            id=uuid4(),
            name="Test Project",
            admin_id=admin.id,
        )
        invitation = Invitation(
            id=uuid4(),
            project_id=project.id,
            token=uuid4(),
            expires_at=datetime.now(UTC) + timedelta(days=7),
            used_by_id=None,
        )
        return InvitationDetails(invitation=invitation, project=project, admin=admin)

    def test_token_property(self, invitation_details):
        """Token property returns invitation token."""
        assert invitation_details.token == invitation_details.invitation.token

    def test_project_name_property(self, invitation_details):
        """Project name property returns project name."""
        assert invitation_details.project_name == "Test Project"

    def test_admin_name_with_last_name(self, invitation_details):
        """Admin name includes both first and last name."""
        assert invitation_details.admin_name == "John Doe"

    def test_admin_name_without_last_name(self):
        """Admin name returns only first name when last name is None."""
        admin = User(
            id=uuid4(),
            email="admin@example.com",
            hashed_password="hash",
            first_name="John",
            last_name=None,
        )
        project = Project(id=uuid4(), name="Project", admin_id=admin.id)
        invitation = Invitation(
            id=uuid4(),
            project_id=project.id,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        details = InvitationDetails(invitation=invitation, project=project, admin=admin)

        assert details.admin_name == "John"

    def test_expires_at_property(self, invitation_details):
        """Expires at property returns invitation expiration."""
        assert invitation_details.expires_at == invitation_details.invitation.expires_at

    def test_is_used_when_not_used(self, invitation_details):
        """Is used returns False when invitation not used."""
        assert invitation_details.is_used is False

    def test_is_used_when_used(self):
        """Is used returns True when invitation has been used."""
        admin = User(
            id=uuid4(),
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
        )
        project = Project(id=uuid4(), name="Project", admin_id=admin.id)
        invitation = Invitation(
            id=uuid4(),
            project_id=project.id,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            used_by_id=uuid4(),  # Set as used
        )
        details = InvitationDetails(invitation=invitation, project=project, admin=admin)

        assert details.is_used is True


class TestProjectWithMemberCount:
    """Tests for ProjectWithMemberCount DTO."""

    def test_id_property(self):
        """ID property returns project ID."""
        project = Project(id=uuid4(), name="Test", admin_id=uuid4())
        pwmc = ProjectWithMemberCount(project=project, member_count=5)

        assert pwmc.id == project.id

    def test_name_property(self):
        """Name property returns project name."""
        project = Project(id=uuid4(), name="My Project", admin_id=uuid4())
        pwmc = ProjectWithMemberCount(project=project, member_count=3)

        assert pwmc.name == "My Project"


class TestMemberWithUser:
    """Tests for MemberWithUser DTO."""

    @pytest.fixture
    def member_with_user(self):
        """Create MemberWithUser for testing."""
        user = User(
            id=uuid4(),
            email="expert@example.com",
            hashed_password="hash",
            first_name="Jane",
            last_name="Smith",
        )
        membership = ProjectMember(
            id=uuid4(),
            project_id=uuid4(),
            user_id=user.id,
            role=MemberRole.EXPERT,
            joined_at=datetime.now(UTC),
        )
        return MemberWithUser(membership=membership, user=user)

    def test_user_id_property(self, member_with_user):
        """User ID property returns user ID."""
        assert member_with_user.user_id == member_with_user.user.id

    def test_email_property(self, member_with_user):
        """Email property returns user email."""
        assert member_with_user.email == "expert@example.com"

    def test_first_name_property(self, member_with_user):
        """First name property returns user first name."""
        assert member_with_user.first_name == "Jane"

    def test_last_name_property(self, member_with_user):
        """Last name property returns user last name."""
        assert member_with_user.last_name == "Smith"

    def test_role_property(self, member_with_user):
        """Role property returns membership role."""
        assert member_with_user.role == MemberRole.EXPERT

    def test_joined_at_property(self, member_with_user):
        """Joined at property returns join timestamp."""
        assert member_with_user.joined_at == member_with_user.membership.joined_at


class TestOpinionWithUser:
    """Tests for OpinionWithUser DTO."""

    @pytest.fixture
    def opinion_with_user(self):
        """Create OpinionWithUser for testing."""
        user = User(
            id=uuid4(),
            email="expert@example.com",
            hashed_password="hash",
            first_name="Expert",
        )
        opinion = ExpertOpinion(
            id=uuid4(),
            project_id=uuid4(),
            user_id=user.id,
            position="Analyst",
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        return OpinionWithUser(opinion=opinion, user=user)

    def test_opinion_id_property(self, opinion_with_user):
        """Opinion ID property returns opinion ID."""
        assert opinion_with_user.opinion_id == opinion_with_user.opinion.id

    def test_user_id_property(self, opinion_with_user):
        """User ID property returns user ID."""
        assert opinion_with_user.user_id == opinion_with_user.user.id

    def test_position_property(self, opinion_with_user):
        """Position property returns expert position."""
        assert opinion_with_user.position == "Analyst"

    def test_lower_bound_property(self, opinion_with_user):
        """Lower bound property returns opinion lower bound."""
        assert opinion_with_user.lower_bound == 5.0

    def test_peak_property(self, opinion_with_user):
        """Peak property returns opinion peak."""
        assert opinion_with_user.peak == 10.0

    def test_upper_bound_property(self, opinion_with_user):
        """Upper bound property returns opinion upper bound."""
        assert opinion_with_user.upper_bound == 15.0


class TestUpsertResult:
    """Tests for UpsertResult DTO."""

    def test_opinion_id_property(self):
        """Opinion ID property returns opinion ID."""
        opinion = ExpertOpinion(
            id=uuid4(),
            project_id=uuid4(),
            user_id=uuid4(),
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        result = UpsertResult(opinion=opinion, is_new=True)

        assert result.opinion_id == opinion.id

    def test_was_created_when_new(self):
        """Was created returns True when is_new is True."""
        opinion = ExpertOpinion(
            id=uuid4(),
            project_id=uuid4(),
            user_id=uuid4(),
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        result = UpsertResult(opinion=opinion, is_new=True)

        assert result.was_created is True
        assert result.was_updated is False

    def test_was_updated_when_not_new(self):
        """Was updated returns True when is_new is False."""
        opinion = ExpertOpinion(
            id=uuid4(),
            project_id=uuid4(),
            user_id=uuid4(),
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        result = UpsertResult(opinion=opinion, is_new=False)

        assert result.was_created is False
        assert result.was_updated is True
