"""Unit tests for InvitationService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from api.db.models import Invitation, MemberRole, Project, ProjectMember, User
from api.exceptions import (
    InvitationAlreadyUsedError,
    InvitationExpiredError,
    InvitationNotFoundError,
    UserAlreadyMemberError,
)
from api.services.invitation_service import InvitationService


class TestInvitationServiceCreateInvitation:
    """Tests for InvitationService.create_invitation method."""

    def test_creates_invitation_with_default_expiration(self):
        """Invitation is created with default 7-day expiration."""
        # GIVEN
        mock_session = MagicMock()
        service = InvitationService(mock_session)
        project_id = uuid4()

        # WHEN
        invitation = service.create_invitation(project_id)

        # THEN
        assert invitation.project_id == project_id
        assert invitation.expires_at > datetime.now(UTC)
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    def test_creates_invitation_with_custom_expiration(self):
        """Invitation is created with custom expiration days."""
        # GIVEN
        mock_session = MagicMock()
        service = InvitationService(mock_session)
        project_id = uuid4()

        # WHEN
        invitation = service.create_invitation(project_id, expires_in_days=30)

        # THEN
        assert invitation.project_id == project_id
        # Check expiration is approximately 30 days from now
        expected_min = datetime.now(UTC) + timedelta(days=29)
        expected_max = datetime.now(UTC) + timedelta(days=31)
        assert expected_min < invitation.expires_at < expected_max


class TestInvitationServiceGetInvitationByToken:
    """Tests for InvitationService.get_invitation_by_token method."""

    def test_returns_invitation_when_found(self):
        """Returns invitation when token exists."""
        # GIVEN
        token = uuid4()
        expected_invitation = Invitation(
            id=uuid4(),
            project_id=uuid4(),
            token=token,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = expected_invitation
        service = InvitationService(mock_session)

        # WHEN
        result = service.get_invitation_by_token(token)

        # THEN
        assert result == expected_invitation

    def test_returns_none_when_not_found(self):
        """Returns None when token doesn't exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = InvitationService(mock_session)

        # WHEN
        result = service.get_invitation_by_token(uuid4())

        # THEN
        assert result is None


class TestInvitationServiceAcceptInvitation:
    """Tests for InvitationService.accept_invitation method."""

    def test_accepts_valid_invitation(self):
        """User is added to project when accepting valid invitation."""
        # GIVEN
        token = uuid4()
        user_id = uuid4()
        project_id = uuid4()
        invitation = Invitation(
            id=uuid4(),
            project_id=project_id,
            token=token,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            used_by_id=None,
        )
        mock_session = MagicMock()
        # First exec call - get invitation
        # Second exec call - check existing membership
        mock_session.exec.return_value.first.side_effect = [invitation, None]
        service = InvitationService(mock_session)

        # WHEN
        membership = service.accept_invitation(token, user_id)

        # THEN
        assert membership.project_id == project_id
        assert membership.user_id == user_id
        assert membership.role == MemberRole.EXPERT
        assert invitation.used_by_id == user_id
        assert mock_session.add.call_count == 2  # invitation update + membership
        mock_session.commit.assert_called_once()

    def test_raises_error_when_invitation_not_found(self):
        """InvitationNotFoundError is raised when token doesn't exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = InvitationService(mock_session)

        # WHEN / THEN
        with pytest.raises(InvitationNotFoundError, match="not found"):
            service.accept_invitation(uuid4(), uuid4())

    def test_raises_error_when_invitation_already_used(self):
        """InvitationAlreadyUsedError is raised when invitation was used."""
        # GIVEN
        token = uuid4()
        invitation = Invitation(
            id=uuid4(),
            project_id=uuid4(),
            token=token,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            used_by_id=uuid4(),  # Already used
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = invitation
        service = InvitationService(mock_session)

        # WHEN / THEN
        with pytest.raises(InvitationAlreadyUsedError, match="already been used"):
            service.accept_invitation(token, uuid4())

    def test_raises_error_when_invitation_expired(self):
        """InvitationExpiredError is raised when invitation has expired."""
        # GIVEN
        token = uuid4()
        invitation = Invitation(
            id=uuid4(),
            project_id=uuid4(),
            token=token,
            expires_at=datetime.now(UTC) - timedelta(days=1),  # Expired
            used_by_id=None,
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = invitation
        service = InvitationService(mock_session)

        # WHEN / THEN
        with pytest.raises(InvitationExpiredError, match="expired"):
            service.accept_invitation(token, uuid4())

    def test_raises_error_when_user_already_member(self):
        """UserAlreadyMemberError is raised when user is already a member."""
        # GIVEN
        token = uuid4()
        user_id = uuid4()
        project_id = uuid4()
        invitation = Invitation(
            id=uuid4(),
            project_id=project_id,
            token=token,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            used_by_id=None,
        )
        existing_membership = ProjectMember(
            id=uuid4(),
            project_id=project_id,
            user_id=user_id,
            role=MemberRole.EXPERT,
        )
        mock_session = MagicMock()
        # First call returns invitation, second returns existing membership
        mock_session.exec.return_value.first.side_effect = [invitation, existing_membership]
        service = InvitationService(mock_session)

        # WHEN / THEN
        with pytest.raises(UserAlreadyMemberError, match="already a member"):
            service.accept_invitation(token, user_id)


class TestInvitationServiceIsInvitationValid:
    """Tests for InvitationService.is_invitation_valid method."""

    def test_returns_true_for_valid_invitation(self):
        """Returns True when invitation is valid."""
        # GIVEN
        token = uuid4()
        invitation = Invitation(
            id=uuid4(),
            project_id=uuid4(),
            token=token,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            used_by_id=None,
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = invitation
        service = InvitationService(mock_session)

        # WHEN
        result = service.is_invitation_valid(token)

        # THEN
        assert result is True

    def test_returns_false_when_not_found(self):
        """Returns False when invitation doesn't exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = InvitationService(mock_session)

        # WHEN
        result = service.is_invitation_valid(uuid4())

        # THEN
        assert result is False

    def test_returns_false_when_used(self):
        """Returns False when invitation was already used."""
        # GIVEN
        token = uuid4()
        invitation = Invitation(
            id=uuid4(),
            project_id=uuid4(),
            token=token,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            used_by_id=uuid4(),  # Used
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = invitation
        service = InvitationService(mock_session)

        # WHEN
        result = service.is_invitation_valid(token)

        # THEN
        assert result is False

    def test_returns_false_when_expired(self):
        """Returns False when invitation has expired."""
        # GIVEN
        token = uuid4()
        invitation = Invitation(
            id=uuid4(),
            project_id=uuid4(),
            token=token,
            expires_at=datetime.now(UTC) - timedelta(days=1),  # Expired
            used_by_id=None,
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = invitation
        service = InvitationService(mock_session)

        # WHEN
        result = service.is_invitation_valid(token)

        # THEN
        assert result is False


class TestInvitationServiceGetInvitationDetails:
    """Tests for InvitationService.get_invitation_details method."""

    def test_returns_details_when_found(self):
        """Returns invitation, project, and admin when found."""
        # GIVEN
        token = uuid4()
        project_id = uuid4()
        admin_id = uuid4()
        invitation = Invitation(
            id=uuid4(),
            project_id=project_id,
            token=token,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        project = Project(
            id=project_id,
            name="Test Project",
            admin_id=admin_id,
            scale_min=0,
            scale_max=100,
        )
        admin = User(
            id=admin_id,
            email="admin@example.com",
            hashed_password="hashed",
            first_name="Admin",
            last_name="User",
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = (invitation, project, admin)
        service = InvitationService(mock_session)

        # WHEN
        details = service.get_invitation_details(token)

        # THEN
        assert details is not None
        assert details.invitation == invitation
        assert details.project == project
        assert details.admin == admin

    def test_returns_none_when_not_found(self):
        """Returns None when invitation doesn't exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = InvitationService(mock_session)

        # WHEN
        result = service.get_invitation_details(uuid4())

        # THEN
        assert result is None
