"""Tests for invitation schemas."""

from datetime import UTC, datetime
from uuid import uuid4

from api.db.models import Invitation, Project, User
from api.schemas.invitation import InvitationListItemResponse, InvitationResponse


class TestInvitationResponseFromModel:
    """Tests for InvitationResponse.from_model method."""

    def test_creates_response_from_models(self):
        """
        GIVEN Invitation and User (invitee) models
        WHEN from_model is called
        THEN InvitationResponse is created with correct values
        """
        # GIVEN
        invitation_id = uuid4()
        project_id = uuid4()
        invitee_id = uuid4()
        created_at = datetime.now(UTC)

        invitation = Invitation(
            id=invitation_id,
            project_id=project_id,
            inviter_id=uuid4(),
            invitee_id=invitee_id,
            created_at=created_at,
        )
        invitee = User(
            id=invitee_id,
            email="invitee@example.com",
            hashed_password="hash",
            first_name="Jane",
        )

        # WHEN
        response = InvitationResponse.from_model(invitation, invitee)

        # THEN
        assert response.id == str(invitation_id)
        assert response.project_id == str(project_id)
        assert response.invitee_email == "invitee@example.com"
        assert response.invited_at == created_at


class TestInvitationListItemResponseFromModel:
    """Tests for InvitationListItemResponse.from_model method."""

    def test_creates_response_from_models(self):
        """
        GIVEN Invitation, Project, User (inviter), and member count
        WHEN from_model is called
        THEN InvitationListItemResponse is created with correct values
        """
        # GIVEN
        invitation_id = uuid4()
        project_id = uuid4()
        inviter_id = uuid4()
        created_at = datetime.now(UTC)

        invitation = Invitation(
            id=invitation_id,
            project_id=project_id,
            inviter_id=inviter_id,
            invitee_id=uuid4(),
            created_at=created_at,
        )
        project = Project(
            id=project_id,
            name="Test Project",
            description="Project description",
            scale_min=0.0,
            scale_max=100.0,
            scale_unit="%",
            admin_id=inviter_id,
        )
        inviter = User(
            id=inviter_id,
            email="admin@example.com",
            hashed_password="hash",
            first_name="John",
        )

        # WHEN
        response = InvitationListItemResponse.from_model(
            invitation, project, inviter, member_count=5
        )

        # THEN
        assert response.id == str(invitation_id)
        assert response.project_id == str(project_id)
        assert response.project_name == "Test Project"
        assert response.project_description == "Project description"
        assert response.project_scale_min == 0.0
        assert response.project_scale_max == 100.0
        assert response.project_scale_unit == "%"
        assert response.inviter_email == "admin@example.com"
        assert response.inviter_first_name == "John"
        assert response.current_experts_count == 5
        assert response.invited_at == created_at

    def test_handles_none_description(self):
        """
        GIVEN Project with None description
        WHEN from_model is called
        THEN response has None project_description
        """
        # GIVEN
        invitation = Invitation(
            id=uuid4(),
            project_id=uuid4(),
            inviter_id=uuid4(),
            invitee_id=uuid4(),
        )
        project = Project(
            id=invitation.project_id,
            name="Project",
            description=None,
            scale_min=1.0,
            scale_max=10.0,
            scale_unit="points",
            admin_id=invitation.inviter_id,
        )
        inviter = User(
            id=invitation.inviter_id,
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
        )

        # WHEN
        response = InvitationListItemResponse.from_model(
            invitation, project, inviter, member_count=1
        )

        # THEN
        assert response.project_description is None
