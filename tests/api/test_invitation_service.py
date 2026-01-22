"""Unit tests for InvitationService (email-based)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from api.db.models import Invitation, MemberRole, Project, ProjectMember, User
from api.exceptions import (
    InvitationNotFoundError,
    UserAlreadyMemberError,
)
from api.services.invitation_service import (
    AlreadyInvitedError,
    InvitationService,
    UserNotFoundError,
)


class TestInvitationServiceInviteByEmail:
    """Tests for InvitationService.invite_by_email method."""

    def test_creates_invitation_for_existing_user(self):
        """Invitation is created when user with email exists."""
        # GIVEN
        project_id = uuid4()
        inviter_id = uuid4()
        invitee = User(
            id=uuid4(),
            email="invitee@example.com",
            hashed_password="hash",
            first_name="Invitee",
        )
        mock_session = MagicMock()
        # First exec: find user by email
        # Second exec: check existing membership
        # Third exec: check existing invitation
        mock_session.exec.return_value.first.side_effect = [invitee, None, None]
        service = InvitationService(mock_session)

        # WHEN
        invitation, returned_user = service.invite_by_email(
            project_id, inviter_id, "invitee@example.com"
        )

        # THEN
        assert invitation.project_id == project_id
        assert invitation.invitee_id == invitee.id
        assert invitation.inviter_id == inviter_id
        assert returned_user == invitee
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_email_lookup_is_case_insensitive(self):
        """Invitation finds user when email has different case."""
        # GIVEN
        project_id = uuid4()
        inviter_id = uuid4()
        invitee = User(
            id=uuid4(),
            email="invitee@example.com",  # lowercase in DB
            hashed_password="hash",
            first_name="Invitee",
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.side_effect = [invitee, None, None]
        service = InvitationService(mock_session)

        # WHEN - invite with mixed case email
        invitation, returned_user = service.invite_by_email(
            project_id, inviter_id, "Invitee@Example.COM"
        )

        # THEN - user is found despite different case
        assert returned_user == invitee
        assert invitation.invitee_id == invitee.id
        mock_session.add.assert_called_once()

    def test_raises_error_when_user_not_found(self):
        """UserNotFoundError is raised when email doesn't exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = InvitationService(mock_session)

        # WHEN / THEN
        with pytest.raises(UserNotFoundError, match="No user found"):
            service.invite_by_email(uuid4(), uuid4(), "nonexistent@example.com")

    def test_raises_error_when_user_already_member(self):
        """UserAlreadyMemberError is raised when user is already a member."""
        # GIVEN
        invitee = User(
            id=uuid4(),
            email="invitee@example.com",
            hashed_password="hash",
            first_name="Invitee",
        )
        existing_membership = ProjectMember(
            id=uuid4(),
            project_id=uuid4(),
            user_id=invitee.id,
            role=MemberRole.EXPERT,
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.side_effect = [invitee, existing_membership]
        service = InvitationService(mock_session)

        # WHEN / THEN
        with pytest.raises(UserAlreadyMemberError, match="already a member"):
            service.invite_by_email(uuid4(), uuid4(), "invitee@example.com")

    def test_raises_error_when_already_invited(self):
        """AlreadyInvitedError is raised when user has pending invitation."""
        # GIVEN
        invitee = User(
            id=uuid4(),
            email="invitee@example.com",
            hashed_password="hash",
            first_name="Invitee",
        )
        existing_invitation = Invitation(
            id=uuid4(),
            project_id=uuid4(),
            invitee_id=invitee.id,
            inviter_id=uuid4(),
        )
        mock_session = MagicMock()
        # User found, no membership, but existing invitation
        mock_session.exec.return_value.first.side_effect = [invitee, None, existing_invitation]
        service = InvitationService(mock_session)

        # WHEN / THEN
        with pytest.raises(AlreadyInvitedError, match="pending invitation"):
            service.invite_by_email(uuid4(), uuid4(), "invitee@example.com")


class TestInvitationServiceGetInvitationById:
    """Tests for InvitationService.get_invitation_by_id method."""

    def test_returns_invitation_when_found(self):
        """Returns invitation when ID exists."""
        # GIVEN
        invitation_id = uuid4()
        expected_invitation = Invitation(
            id=invitation_id,
            project_id=uuid4(),
            invitee_id=uuid4(),
            inviter_id=uuid4(),
        )
        mock_session = MagicMock()
        mock_session.get.return_value = expected_invitation
        service = InvitationService(mock_session)

        # WHEN
        result = service.get_invitation_by_id(invitation_id)

        # THEN
        assert result == expected_invitation
        mock_session.get.assert_called_once_with(Invitation, invitation_id)

    def test_returns_none_when_not_found(self):
        """Returns None when ID doesn't exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.get.return_value = None
        service = InvitationService(mock_session)

        # WHEN
        result = service.get_invitation_by_id(uuid4())

        # THEN
        assert result is None


class TestInvitationServiceAcceptInvitation:
    """Tests for InvitationService.accept_invitation method."""

    def test_accepts_invitation_and_adds_membership(self):
        """User is added to project when accepting invitation."""
        # GIVEN
        invitation_id = uuid4()
        user_id = uuid4()
        project_id = uuid4()
        invitation = Invitation(
            id=invitation_id,
            project_id=project_id,
            invitee_id=user_id,
            inviter_id=uuid4(),
        )
        mock_session = MagicMock()
        mock_session.get.return_value = invitation
        mock_session.exec.return_value.first.return_value = None  # No existing membership
        service = InvitationService(mock_session)

        # WHEN
        membership = service.accept_invitation(invitation_id, user_id)

        # THEN
        assert membership.project_id == project_id
        assert membership.user_id == user_id
        assert membership.role == MemberRole.EXPERT
        mock_session.delete.assert_called_once_with(invitation)
        mock_session.commit.assert_called_once()

    def test_raises_error_when_invitation_not_found(self):
        """InvitationNotFoundError is raised when invitation doesn't exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.get.return_value = None
        service = InvitationService(mock_session)

        # WHEN / THEN
        with pytest.raises(InvitationNotFoundError, match="not found"):
            service.accept_invitation(uuid4(), uuid4())

    def test_raises_error_when_invitation_not_for_user(self):
        """InvitationNotFoundError is raised when invitation is for different user."""
        # GIVEN
        invitation = Invitation(
            id=uuid4(),
            project_id=uuid4(),
            invitee_id=uuid4(),  # Different user
            inviter_id=uuid4(),
        )
        mock_session = MagicMock()
        mock_session.get.return_value = invitation
        service = InvitationService(mock_session)

        # WHEN / THEN
        with pytest.raises(InvitationNotFoundError, match="not found"):
            service.accept_invitation(invitation.id, uuid4())  # Different user_id

    def test_raises_error_when_user_already_member(self):
        """UserAlreadyMemberError is raised when user is already a member."""
        # GIVEN
        user_id = uuid4()
        project_id = uuid4()
        invitation = Invitation(
            id=uuid4(),
            project_id=project_id,
            invitee_id=user_id,
            inviter_id=uuid4(),
        )
        existing_membership = ProjectMember(
            id=uuid4(),
            project_id=project_id,
            user_id=user_id,
            role=MemberRole.EXPERT,
        )
        mock_session = MagicMock()
        mock_session.get.return_value = invitation
        mock_session.exec.return_value.first.return_value = existing_membership
        service = InvitationService(mock_session)

        # WHEN / THEN
        with pytest.raises(UserAlreadyMemberError, match="already a member"):
            service.accept_invitation(invitation.id, user_id)


class TestInvitationServiceDeclineInvitation:
    """Tests for InvitationService.decline_invitation method."""

    def test_deletes_invitation(self):
        """Invitation is deleted when declined."""
        # GIVEN
        invitation_id = uuid4()
        user_id = uuid4()
        invitation = Invitation(
            id=invitation_id,
            project_id=uuid4(),
            invitee_id=user_id,
            inviter_id=uuid4(),
        )
        mock_session = MagicMock()
        mock_session.get.return_value = invitation
        service = InvitationService(mock_session)

        # WHEN
        service.decline_invitation(invitation_id, user_id)

        # THEN
        mock_session.delete.assert_called_once_with(invitation)
        mock_session.commit.assert_called_once()

    def test_raises_error_when_invitation_not_found(self):
        """InvitationNotFoundError is raised when invitation doesn't exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.get.return_value = None
        service = InvitationService(mock_session)

        # WHEN / THEN
        with pytest.raises(InvitationNotFoundError, match="not found"):
            service.decline_invitation(uuid4(), uuid4())

    def test_raises_error_when_invitation_not_for_user(self):
        """InvitationNotFoundError is raised when invitation is for different user."""
        # GIVEN
        invitation = Invitation(
            id=uuid4(),
            project_id=uuid4(),
            invitee_id=uuid4(),  # Different user
            inviter_id=uuid4(),
        )
        mock_session = MagicMock()
        mock_session.get.return_value = invitation
        service = InvitationService(mock_session)

        # WHEN / THEN
        with pytest.raises(InvitationNotFoundError, match="not found"):
            service.decline_invitation(invitation.id, uuid4())


class TestInvitationServiceGetUserInvitations:
    """Tests for InvitationService.get_user_invitations method."""

    def test_returns_empty_list_when_no_invitations(self):
        """Returns empty list when user has no invitations."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = []
        service = InvitationService(mock_session)

        # WHEN
        result = service.get_user_invitations(uuid4())

        # THEN
        assert result == []

    def test_returns_invitations_with_details(self):
        """Returns list of InvitationWithDetails when invitations exist."""
        # GIVEN
        user_id = uuid4()
        project_id = uuid4()
        inviter_id = uuid4()
        invitation = Invitation(
            id=uuid4(),
            project_id=project_id,
            invitee_id=user_id,
            inviter_id=inviter_id,
            created_at=datetime.now(UTC),
        )
        project = Project(
            id=project_id,
            name="Test Project",
            admin_id=inviter_id,
        )
        inviter = User(
            id=inviter_id,
            email="inviter@example.com",
            hashed_password="hash",
            first_name="Inviter",
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = [
            (invitation, project, inviter, 5)  # 5 members
        ]
        service = InvitationService(mock_session)

        # WHEN
        result = service.get_user_invitations(user_id)

        # THEN
        assert len(result) == 1
        assert result[0].invitation == invitation
        assert result[0].project == project
        assert result[0].inviter == inviter
        assert result[0].member_count == 5
