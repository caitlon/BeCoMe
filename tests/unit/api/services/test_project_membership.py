"""Unit tests for ProjectMembershipService."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from api.db.models import MemberRole, ProjectMember, User
from api.exceptions import MemberNotFoundError
from api.services.project_membership_service import ProjectMembershipService


class TestProjectMembershipServiceGetMembers:
    """Tests for ProjectMembershipService.get_members method."""

    def test_returns_members_with_user_details(self):
        """Returns list of MemberWithUser instances."""
        # GIVEN
        user = User(
            id=uuid4(),
            email="member@example.com",
            first_name="Test",
            hashed_password="hash",
        )
        membership = ProjectMember(
            project_id=uuid4(),
            user_id=user.id,
            role=MemberRole.EXPERT,
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = [(membership, user)]
        service = ProjectMembershipService(mock_session)

        # WHEN
        result = service.get_members(uuid4())

        # THEN
        assert len(result) == 1
        assert result[0].membership == membership
        assert result[0].user == user

    def test_returns_empty_list_when_no_members(self):
        """Returns empty list when project has no members."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = []
        service = ProjectMembershipService(mock_session)

        # WHEN
        result = service.get_members(uuid4())

        # THEN
        assert result == []


class TestProjectMembershipServiceRemoveMember:
    """Tests for ProjectMembershipService.remove_member method."""

    def test_removes_member(self):
        """Member is removed from project."""
        # GIVEN
        project_id = uuid4()
        user_id = uuid4()
        membership = ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role=MemberRole.EXPERT,
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = membership
        service = ProjectMembershipService(mock_session)

        # WHEN
        service.remove_member(project_id, user_id)

        # THEN
        mock_session.delete.assert_called_once_with(membership)
        mock_session.commit.assert_called_once()

    def test_raises_error_when_not_member(self):
        """MemberNotFoundError is raised when user is not a member."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = ProjectMembershipService(mock_session)

        # WHEN / THEN
        with pytest.raises(MemberNotFoundError, match="not a member"):
            service.remove_member(uuid4(), uuid4())


class TestProjectMembershipServiceIsMember:
    """Tests for ProjectMembershipService.is_member method."""

    def test_returns_true_when_member(self):
        """Returns True when user is a member."""
        # GIVEN
        membership = ProjectMember(
            project_id=uuid4(),
            user_id=uuid4(),
            role=MemberRole.EXPERT,
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = membership
        service = ProjectMembershipService(mock_session)

        # WHEN
        result = service.is_member(uuid4(), uuid4())

        # THEN
        assert result is True

    def test_returns_false_when_not_member(self):
        """Returns False when user is not a member."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = ProjectMembershipService(mock_session)

        # WHEN
        result = service.is_member(uuid4(), uuid4())

        # THEN
        assert result is False


class TestProjectMembershipServiceIsAdmin:
    """Tests for ProjectMembershipService.is_admin method."""

    def test_returns_true_when_admin(self):
        """Returns True when user is an admin."""
        # GIVEN
        membership = ProjectMember(
            project_id=uuid4(),
            user_id=uuid4(),
            role=MemberRole.ADMIN,
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = membership
        service = ProjectMembershipService(mock_session)

        # WHEN
        result = service.is_admin(uuid4(), uuid4())

        # THEN
        assert result is True

    def test_returns_false_when_not_admin(self):
        """Returns False when user is not an admin."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = ProjectMembershipService(mock_session)

        # WHEN
        result = service.is_admin(uuid4(), uuid4())

        # THEN
        assert result is False

    def test_returns_false_when_expert(self):
        """Returns False when user is expert (not admin)."""
        # GIVEN - is_admin query filters by role=ADMIN, so expert won't match
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = ProjectMembershipService(mock_session)

        # WHEN
        result = service.is_admin(uuid4(), uuid4())

        # THEN
        assert result is False


class TestProjectMembershipServiceGetUserRoleInProject:
    """Tests for ProjectMembershipService.get_user_role_in_project method."""

    def test_returns_role_when_member(self):
        """Returns member's role when user is a member."""
        # GIVEN
        membership = ProjectMember(
            project_id=uuid4(),
            user_id=uuid4(),
            role=MemberRole.EXPERT,
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = membership
        service = ProjectMembershipService(mock_session)

        # WHEN
        result = service.get_user_role_in_project(uuid4(), uuid4())

        # THEN
        assert result == MemberRole.EXPERT

    def test_returns_none_when_not_member(self):
        """Returns None when user is not a member."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = ProjectMembershipService(mock_session)

        # WHEN
        result = service.get_user_role_in_project(uuid4(), uuid4())

        # THEN
        assert result is None


class TestProjectMembershipServiceAddMember:
    """Tests for ProjectMembershipService.add_member method."""

    def test_adds_member_with_role(self):
        """Member is added with specified role."""
        # GIVEN
        project_id = uuid4()
        user_id = uuid4()
        mock_session = MagicMock()
        service = ProjectMembershipService(mock_session)

        # WHEN
        result = service.add_member(project_id, user_id, MemberRole.EXPERT)

        # THEN
        assert result.project_id == project_id
        assert result.user_id == user_id
        assert result.role == MemberRole.EXPERT
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
