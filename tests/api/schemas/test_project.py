"""Tests for project management schemas."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.db.models import MemberRole, Project, ProjectMember, User
from api.schemas.project import (
    MemberResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ProjectWithRoleResponse,
)


class TestProjectCreate:
    """Tests for ProjectCreate schema."""

    def test_valid_project_accepted(self):
        """
        GIVEN valid project data
        WHEN ProjectCreate is created
        THEN no error is raised
        """
        # WHEN
        project = ProjectCreate(
            name="Test Project",
            description="A description",
            scale_min=0.0,
            scale_max=100.0,
            scale_unit="%",
        )

        # THEN
        assert project.name == "Test Project"
        assert project.scale_min == 0.0
        assert project.scale_max == 100.0

    def test_html_in_name_sanitized(self):
        """
        GIVEN project name with HTML tags
        WHEN ProjectCreate is created
        THEN HTML is removed from name
        """
        # WHEN
        project = ProjectCreate(name="<script>alert('xss')</script>Project")

        # THEN
        assert project.name == "alert('xss')Project"

    def test_html_in_description_sanitized(self):
        """
        GIVEN project description with HTML tags
        WHEN ProjectCreate is created
        THEN HTML is removed from description
        """
        # WHEN
        project = ProjectCreate(
            name="Project",
            description="<b>Bold</b> text",
        )

        # THEN
        assert project.description == "Bold text"

    def test_html_in_scale_unit_sanitized(self):
        """
        GIVEN scale_unit with HTML tags
        WHEN ProjectCreate is created
        THEN HTML is removed from scale_unit
        """
        # WHEN
        project = ProjectCreate(
            name="Project",
            scale_unit="<i>%</i>",
        )

        # THEN
        assert project.scale_unit == "%"

    def test_scale_min_equals_scale_max_rejected(self):
        """
        GIVEN scale_min equals scale_max
        WHEN ProjectCreate is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="scale_min"):
            ProjectCreate(
                name="Project",
                scale_min=50.0,
                scale_max=50.0,
            )

    def test_scale_min_greater_than_scale_max_rejected(self):
        """
        GIVEN scale_min greater than scale_max
        WHEN ProjectCreate is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="scale_min"):
            ProjectCreate(
                name="Project",
                scale_min=100.0,
                scale_max=50.0,
            )


class TestProjectUpdate:
    """Tests for ProjectUpdate schema."""

    def test_valid_partial_update(self):
        """
        GIVEN partial update data
        WHEN ProjectUpdate is created
        THEN only provided fields are set
        """
        # WHEN
        update = ProjectUpdate(name="New Name")

        # THEN
        assert update.name == "New Name"
        assert update.description is None
        assert update.scale_min is None

    def test_html_in_name_sanitized(self):
        """
        GIVEN name with HTML tags
        WHEN ProjectUpdate is created
        THEN HTML is removed
        """
        # WHEN
        update = ProjectUpdate(name="<b>Name</b>")

        # THEN
        assert update.name == "Name"

    def test_html_in_description_sanitized(self):
        """
        GIVEN description with HTML tags
        WHEN ProjectUpdate is created
        THEN HTML is removed
        """
        # WHEN
        update = ProjectUpdate(description="<script>bad</script>Good")

        # THEN
        assert update.description == "badGood"

    def test_none_values_preserved(self):
        """
        GIVEN None values for all fields
        WHEN ProjectUpdate is created
        THEN all fields remain None
        """
        # WHEN
        update = ProjectUpdate()

        # THEN
        assert update.name is None
        assert update.description is None
        assert update.scale_min is None
        assert update.scale_max is None
        assert update.scale_unit is None


class TestProjectResponseFromModel:
    """Tests for ProjectResponse.from_model method."""

    def test_creates_response_from_model(self):
        """
        GIVEN a Project model and member count
        WHEN from_model is called
        THEN ProjectResponse is created with correct values
        """
        # GIVEN
        project_id = uuid4()
        admin_id = uuid4()
        created_at = datetime.now(UTC)
        project = Project(
            id=project_id,
            name="Test Project",
            description="Description",
            scale_min=0.0,
            scale_max=100.0,
            scale_unit="%",
            admin_id=admin_id,
            created_at=created_at,
        )

        # WHEN
        response = ProjectResponse.from_model(project, member_count=5)

        # THEN
        assert response.id == str(project_id)
        assert response.name == "Test Project"
        assert response.description == "Description"
        assert response.scale_min == 0.0
        assert response.scale_max == 100.0
        assert response.scale_unit == "%"
        assert response.admin_id == str(admin_id)
        assert response.created_at == created_at
        assert response.member_count == 5


class TestProjectWithRoleResponseFromModel:
    """Tests for ProjectWithRoleResponse.from_model_with_role method."""

    def test_creates_response_with_role(self):
        """
        GIVEN a Project model, member count, and role
        WHEN from_model_with_role is called
        THEN ProjectWithRoleResponse is created with correct values
        """
        # GIVEN
        project_id = uuid4()
        admin_id = uuid4()
        created_at = datetime.now(UTC)
        project = Project(
            id=project_id,
            name="Test Project",
            description=None,
            scale_min=1.0,
            scale_max=10.0,
            scale_unit="points",
            admin_id=admin_id,
            created_at=created_at,
        )

        # WHEN
        response = ProjectWithRoleResponse.from_model_with_role(
            project, member_count=3, role="admin"
        )

        # THEN
        assert response.id == str(project_id)
        assert response.name == "Test Project"
        assert response.description is None
        assert response.scale_min == 1.0
        assert response.scale_max == 10.0
        assert response.scale_unit == "points"
        assert response.admin_id == str(admin_id)
        assert response.member_count == 3
        assert response.role == "admin"


class TestMemberResponseFromModel:
    """Tests for MemberResponse.from_model method."""

    def test_creates_response_from_models(self):
        """
        GIVEN ProjectMember and User models
        WHEN from_model is called
        THEN MemberResponse is created with correct values
        """
        # GIVEN
        user_id = uuid4()
        joined_at = datetime.now(UTC)

        user = User(
            id=user_id,
            email="expert@example.com",
            hashed_password="hash",
            first_name="Jane",
            last_name="Doe",
        )
        member = ProjectMember(
            id=uuid4(),
            project_id=uuid4(),
            user_id=user_id,
            role=MemberRole.EXPERT,
            joined_at=joined_at,
        )

        # WHEN
        response = MemberResponse.from_model(member, user)

        # THEN
        assert response.user_id == str(user_id)
        assert response.email == "expert@example.com"
        assert response.first_name == "Jane"
        assert response.last_name == "Doe"
        assert response.role == "expert"
        assert response.joined_at == joined_at

    def test_handles_none_last_name(self):
        """
        GIVEN User with None last_name
        WHEN from_model is called
        THEN MemberResponse has None last_name
        """
        # GIVEN
        user_id = uuid4()
        user = User(
            id=user_id,
            email="expert@example.com",
            hashed_password="hash",
            first_name="Jane",
            last_name=None,
        )
        member = ProjectMember(
            id=uuid4(),
            project_id=uuid4(),
            user_id=user_id,
            role=MemberRole.ADMIN,
            joined_at=datetime.now(UTC),
        )

        # WHEN
        response = MemberResponse.from_model(member, user)

        # THEN
        assert response.last_name is None
        assert response.role == "admin"
