"""Unit tests for ProjectQueryService."""

from unittest.mock import MagicMock
from uuid import uuid4

from api.db.models import MemberRole, Project
from api.services.project_query_service import ProjectQueryService


class TestProjectQueryServiceGetUserProjectsWithCounts:
    """Tests for ProjectQueryService.get_user_projects_with_counts method."""

    def test_returns_projects_with_member_counts(self):
        """Returns list of projects with their member counts."""
        # GIVEN
        project = Project(
            id=uuid4(),
            name="Test Project",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = [(project, 5)]
        service = ProjectQueryService(mock_session)

        # WHEN
        result = service.get_user_projects_with_counts(uuid4())

        # THEN
        assert len(result) == 1
        assert result[0].project == project
        assert result[0].member_count == 5

    def test_returns_empty_list_when_no_projects(self):
        """Returns empty list when user has no projects."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = []
        service = ProjectQueryService(mock_session)

        # WHEN
        result = service.get_user_projects_with_counts(uuid4())

        # THEN
        assert result == []


class TestProjectQueryServiceGetUserProjectsWithRoles:
    """Tests for ProjectQueryService.get_user_projects_with_roles method."""

    def test_returns_projects_with_roles(self):
        """Returns list of projects with member counts and roles."""
        # GIVEN
        project = Project(
            id=uuid4(),
            name="Test Project",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = [(project, 3, MemberRole.ADMIN)]
        service = ProjectQueryService(mock_session)

        # WHEN
        result = service.get_user_projects_with_roles(uuid4())

        # THEN
        assert len(result) == 1
        assert result[0].project == project
        assert result[0].member_count == 3
        assert result[0].role == MemberRole.ADMIN

    def test_returns_empty_list_when_no_projects(self):
        """Returns empty list when user has no projects."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = []
        service = ProjectQueryService(mock_session)

        # WHEN
        result = service.get_user_projects_with_roles(uuid4())

        # THEN
        assert result == []

    def test_converts_string_role_to_enum(self):
        """Converts string role value to MemberRole enum."""
        # GIVEN
        project = Project(
            id=uuid4(),
            name="Test Project",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        # Some DB drivers return string instead of enum
        mock_session.exec.return_value.all.return_value = [(project, 2, "expert")]
        service = ProjectQueryService(mock_session)

        # WHEN
        result = service.get_user_projects_with_roles(uuid4())

        # THEN
        assert result[0].role == MemberRole.EXPERT
