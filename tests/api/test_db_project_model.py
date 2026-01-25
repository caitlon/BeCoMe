"""Tests for Project, ProjectMember, and Invitation models."""

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from api.db.models import Invitation, MemberRole, Project, ProjectMember, User


class TestProjectModel:
    """Tests for Project model."""

    def test_scale_min_greater_than_scale_max_raises_error(self):
        """
        GIVEN scale_min >= scale_max
        WHEN Project is validated
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match=r"scale_min .* must be less than scale_max"):
            Project.model_validate(
                {
                    "name": "Test Project",
                    "admin_id": uuid4(),
                    "scale_min": 100.0,
                    "scale_max": 50.0,
                }
            )

    def test_scale_min_equals_scale_max_raises_error(self):
        """
        GIVEN scale_min == scale_max
        WHEN Project is validated
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match=r"scale_min .* must be less than scale_max"):
            Project.model_validate(
                {
                    "name": "Test Project",
                    "admin_id": uuid4(),
                    "scale_min": 50.0,
                    "scale_max": 50.0,
                }
            )

    def test_valid_scale_range_passes_validation(self):
        """
        GIVEN valid scale range (min < max)
        WHEN Project is validated
        THEN Project is created successfully
        """
        # WHEN
        project = Project.model_validate(
            {
                "name": "Test Project",
                "admin_id": uuid4(),
                "scale_min": 0.0,
                "scale_max": 100.0,
            }
        )

        # THEN
        assert project.scale_min == 0.0
        assert project.scale_max == 100.0

    def test_create_project_with_admin(self, session):
        # GIVEN
        admin = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(admin)
        session.commit()

        # WHEN
        project = Project(
            name="Test Project",
            description="A test project",
            admin_id=admin.id,
            scale_min=1.0,
            scale_max=10.0,
            scale_unit="points",
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        # THEN
        assert project.id is not None
        assert project.name == "Test Project"
        assert project.admin_id == admin.id
        assert project.scale_min == 1.0
        assert project.scale_max == 10.0


class TestProjectMemberModel:
    """Tests for ProjectMember model."""

    def test_add_member_to_project(self, session):
        # GIVEN
        admin = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        expert = User(
            email="expert@example.com",
            hashed_password="hash",
            first_name="Expert",
            last_name="User",
        )
        session.add_all([admin, expert])
        session.commit()

        project = Project(name="Test Project", admin_id=admin.id)
        session.add(project)
        session.commit()

        # WHEN
        membership = ProjectMember(
            project_id=project.id,
            user_id=expert.id,
            role=MemberRole.EXPERT,
        )
        session.add(membership)
        session.commit()

        # THEN
        assert membership.role == MemberRole.EXPERT
        assert membership.project_id == project.id
        assert membership.user_id == expert.id

    def test_member_role_enum(self):
        # GIVEN/WHEN/THEN
        assert MemberRole.ADMIN.value == "admin"
        assert MemberRole.EXPERT.value == "expert"

    def test_duplicate_membership_fails(self, session):
        # GIVEN
        user = User(
            email="user@example.com",
            hashed_password="hash",
            first_name="Test",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project = Project(name="Test Project", admin_id=user.id)
        session.add(project)
        session.commit()

        member1 = ProjectMember(
            project_id=project.id,
            user_id=user.id,
            role=MemberRole.ADMIN,
        )
        session.add(member1)
        session.commit()

        # WHEN/THEN - adding same user to same project should fail
        member2 = ProjectMember(
            project_id=project.id,
            user_id=user.id,
            role=MemberRole.EXPERT,
        )
        session.add(member2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_user_can_be_member_of_multiple_projects(self, session):
        # GIVEN
        user = User(
            email="user@example.com",
            hashed_password="hash",
            first_name="Test",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project1 = Project(name="Project 1", admin_id=user.id)
        project2 = Project(name="Project 2", admin_id=user.id)
        session.add_all([project1, project2])
        session.commit()

        # WHEN
        member1 = ProjectMember(project_id=project1.id, user_id=user.id)
        member2 = ProjectMember(project_id=project2.id, user_id=user.id)
        session.add_all([member1, member2])
        session.commit()

        # THEN
        session.refresh(user)
        assert len(user.memberships) == 2


class TestInvitationModel:
    """Tests for Invitation model (email-based)."""

    def test_create_invitation(self, session):
        # GIVEN
        admin = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        invitee = User(
            email="invitee@example.com",
            hashed_password="hash",
            first_name="Invitee",
            last_name="User",
        )
        session.add_all([admin, invitee])
        session.commit()

        project = Project(name="Test Project", admin_id=admin.id)
        session.add(project)
        session.commit()

        # WHEN
        invitation = Invitation(
            project_id=project.id,
            invitee_id=invitee.id,
            inviter_id=admin.id,
        )
        session.add(invitation)
        session.commit()
        session.refresh(invitation)

        # THEN
        assert invitation.id is not None
        assert invitation.invitee_id == invitee.id
        assert invitation.inviter_id == admin.id
        assert invitation.created_at is not None

    def test_invitation_unique_per_project_invitee(self, session):
        # GIVEN
        admin = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        invitee = User(
            email="invitee@example.com",
            hashed_password="hash",
            first_name="Invitee",
            last_name="User",
        )
        session.add_all([admin, invitee])
        session.commit()

        project = Project(name="Test Project", admin_id=admin.id)
        session.add(project)
        session.commit()

        inv1 = Invitation(
            project_id=project.id,
            invitee_id=invitee.id,
            inviter_id=admin.id,
        )
        session.add(inv1)
        session.commit()

        # WHEN/THEN - duplicate invitation to same user for same project should fail
        inv2 = Invitation(
            project_id=project.id,
            invitee_id=invitee.id,
            inviter_id=admin.id,
        )
        session.add(inv2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_same_user_can_be_invited_to_different_projects(self, session):
        # GIVEN
        admin = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        invitee = User(
            email="invitee@example.com",
            hashed_password="hash",
            first_name="Invitee",
            last_name="User",
        )
        session.add_all([admin, invitee])
        session.commit()

        project1 = Project(name="Project 1", admin_id=admin.id)
        project2 = Project(name="Project 2", admin_id=admin.id)
        session.add_all([project1, project2])
        session.commit()

        # WHEN
        inv1 = Invitation(
            project_id=project1.id,
            invitee_id=invitee.id,
            inviter_id=admin.id,
        )
        inv2 = Invitation(
            project_id=project2.id,
            invitee_id=invitee.id,
            inviter_id=admin.id,
        )
        session.add_all([inv1, inv2])
        session.commit()

        # THEN
        assert inv1.id is not None
        assert inv2.id is not None
