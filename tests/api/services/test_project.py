"""Unit tests for ProjectService."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from api.db.models import MemberRole, Project, ProjectMember
from api.exceptions import MemberNotFoundError, ProjectNotFoundError, ScaleRangeError
from api.schemas.project import ProjectCreate, ProjectUpdate
from api.services.base import BaseService
from api.services.project_service import ProjectService


class TestBaseService:
    """Tests for BaseService base class."""

    def test_session_property_returns_session(self):
        """Session property returns the injected session."""
        # GIVEN
        mock_session = MagicMock()
        service = BaseService(mock_session)

        # WHEN
        result = service.session

        # THEN
        assert result is mock_session


class TestProjectServiceCreateProject:
    """Tests for ProjectService.create_project method."""

    def test_creates_project_with_admin_membership(self):
        """Project is created and user becomes admin."""
        # GIVEN
        mock_session = MagicMock()
        service = ProjectService(mock_session)
        user_id = uuid4()
        data = ProjectCreate(name="Test Project", scale_min=0, scale_max=100)

        # WHEN
        project = service.create_project(user_id, data)

        # THEN
        assert project.name == "Test Project"
        assert project.admin_id == user_id
        assert mock_session.add.call_count == 2  # project + membership
        mock_session.flush.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    def test_creates_project_with_description(self):
        """Project is created with optional description."""
        # GIVEN
        mock_session = MagicMock()
        service = ProjectService(mock_session)
        user_id = uuid4()
        data = ProjectCreate(
            name="Described Project",
            description="A test description",
            scale_min=1,
            scale_max=10,
            scale_unit="points",
        )

        # WHEN
        project = service.create_project(user_id, data)

        # THEN
        assert project.name == "Described Project"
        assert project.description == "A test description"
        assert project.scale_min == 1
        assert project.scale_max == 10
        assert project.scale_unit == "points"


class TestProjectServiceGetProject:
    """Tests for ProjectService.get_project method."""

    def test_returns_project_when_found(self):
        """Returns project when ID exists."""
        # GIVEN
        project_id = uuid4()
        expected_project = Project(
            id=project_id,
            name="Found Project",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        mock_session.get.return_value = expected_project
        service = ProjectService(mock_session)

        # WHEN
        result = service.get_project(project_id)

        # THEN
        assert result == expected_project
        mock_session.get.assert_called_once_with(Project, project_id)

    def test_returns_none_when_not_found(self):
        """Returns None when project doesn't exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.get.return_value = None
        service = ProjectService(mock_session)

        # WHEN
        result = service.get_project(uuid4())

        # THEN
        assert result is None


class TestProjectServiceUpdateProject:
    """Tests for ProjectService.update_project method."""

    def test_updates_project_fields(self):
        """Project fields are updated."""
        # GIVEN
        project_id = uuid4()
        project = Project(
            id=project_id,
            name="Original",
            description=None,
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        mock_session.get.return_value = project
        service = ProjectService(mock_session)
        data = ProjectUpdate(name="Updated", description="New description")

        # WHEN
        result = service.update_project(project_id, data)

        # THEN
        assert result.name == "Updated"
        assert result.description == "New description"
        mock_session.commit.assert_called_once()

    def test_raises_error_when_project_not_found(self):
        """ProjectNotFoundError is raised when project doesn't exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.get.return_value = None
        service = ProjectService(mock_session)
        data = ProjectUpdate(name="Updated")

        # WHEN / THEN
        with pytest.raises(ProjectNotFoundError, match="not found"):
            service.update_project(uuid4(), data)

    def test_validates_scale_range_on_update(self):
        """ScaleRangeError is raised when scale range becomes invalid."""
        # GIVEN
        project_id = uuid4()
        project = Project(
            id=project_id,
            name="Test",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        mock_session.get.return_value = project
        service = ProjectService(mock_session)
        data = ProjectUpdate(scale_min=150)  # Greater than scale_max

        # WHEN / THEN
        with pytest.raises(ScaleRangeError, match="scale_min"):
            service.update_project(project_id, data)

    def test_validates_equal_scale_values(self):
        """ScaleRangeError is raised when scale_min equals scale_max."""
        # GIVEN
        project_id = uuid4()
        project = Project(
            id=project_id,
            name="Test",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        mock_session.get.return_value = project
        service = ProjectService(mock_session)
        data = ProjectUpdate(scale_max=0)  # Equal to scale_min

        # WHEN / THEN
        with pytest.raises(ScaleRangeError, match="scale_min"):
            service.update_project(project_id, data)

    def test_updates_scale_min_only(self):
        """Only scale_min is updated when provided."""
        # GIVEN
        project_id = uuid4()
        project = Project(
            id=project_id,
            name="Test",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        mock_session.get.return_value = project
        service = ProjectService(mock_session)
        data = ProjectUpdate(scale_min=10)  # Valid: 10 < 100

        # WHEN
        result = service.update_project(project_id, data)

        # THEN
        assert result.scale_min == 10
        assert result.scale_max == 100  # Unchanged

    def test_updates_scale_max_only(self):
        """Only scale_max is updated when provided."""
        # GIVEN
        project_id = uuid4()
        project = Project(
            id=project_id,
            name="Test",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        mock_session.get.return_value = project
        service = ProjectService(mock_session)
        data = ProjectUpdate(scale_max=200)  # Valid: 0 < 200

        # WHEN
        result = service.update_project(project_id, data)

        # THEN
        assert result.scale_min == 0  # Unchanged
        assert result.scale_max == 200

    def test_updates_scale_unit_only(self):
        """Only scale_unit is updated when provided."""
        # GIVEN
        project_id = uuid4()
        project = Project(
            id=project_id,
            name="Test",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
            scale_unit="",
        )
        mock_session = MagicMock()
        mock_session.get.return_value = project
        service = ProjectService(mock_session)
        data = ProjectUpdate(scale_unit="points")

        # WHEN
        result = service.update_project(project_id, data)

        # THEN
        assert result.scale_unit == "points"


class TestProjectServiceDeleteProject:
    """Tests for ProjectService.delete_project method."""

    def test_deletes_project(self):
        """Project is deleted."""
        # GIVEN
        project_id = uuid4()
        project = Project(
            id=project_id,
            name="To Delete",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        mock_session.get.return_value = project
        service = ProjectService(mock_session)

        # WHEN
        service.delete_project(project_id)

        # THEN
        mock_session.delete.assert_called_once_with(project)
        mock_session.commit.assert_called_once()

    def test_raises_error_when_not_found(self):
        """ProjectNotFoundError is raised when project doesn't exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.get.return_value = None
        service = ProjectService(mock_session)

        # WHEN / THEN
        with pytest.raises(ProjectNotFoundError, match="not found"):
            service.delete_project(uuid4())


class TestProjectServiceRemoveMember:
    """Tests for ProjectService.remove_member method."""

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
        service = ProjectService(mock_session)

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
        service = ProjectService(mock_session)

        # WHEN / THEN
        with pytest.raises(MemberNotFoundError, match="not a member"):
            service.remove_member(uuid4(), uuid4())


class TestProjectServiceIsMember:
    """Tests for ProjectService.is_member method."""

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
        service = ProjectService(mock_session)

        # WHEN
        result = service.is_member(uuid4(), uuid4())

        # THEN
        assert result is True

    def test_returns_false_when_not_member(self):
        """Returns False when user is not a member."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = ProjectService(mock_session)

        # WHEN
        result = service.is_member(uuid4(), uuid4())

        # THEN
        assert result is False


class TestProjectServiceIsAdmin:
    """Tests for ProjectService.is_admin method."""

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
        service = ProjectService(mock_session)

        # WHEN
        result = service.is_admin(uuid4(), uuid4())

        # THEN
        assert result is True

    def test_returns_false_when_not_admin(self):
        """Returns False when user is not an admin."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = ProjectService(mock_session)

        # WHEN
        result = service.is_admin(uuid4(), uuid4())

        # THEN
        assert result is False

    def test_returns_false_when_expert(self):
        """Returns False when user is expert (not admin)."""
        # GIVEN - is_admin query filters by role=ADMIN, so expert won't match
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = ProjectService(mock_session)

        # WHEN
        result = service.is_admin(uuid4(), uuid4())

        # THEN
        assert result is False
