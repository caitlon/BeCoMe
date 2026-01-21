"""Tests for database models."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from api.db.models import (
    CalculationResult,
    ExpertOpinion,
    Invitation,
    MemberRole,
    PasswordResetToken,
    Project,
    ProjectMember,
    User,
)


class TestUserModel:
    """Tests for User model."""

    def test_invalid_email_format_raises_error(self):
        """
        GIVEN invalid email format
        WHEN User is validated
        THEN ValidationError is raised
        """
        from pydantic import ValidationError

        # WHEN/THEN
        with pytest.raises(ValidationError, match="Invalid email format"):
            User.model_validate(
                {
                    "email": "not-an-email",
                    "hashed_password": "hash",
                    "first_name": "Test",
                }
            )

    def test_valid_email_passes_validation(self):
        """
        GIVEN valid email format
        WHEN User is validated
        THEN User is created successfully
        """
        # WHEN
        user = User.model_validate(
            {
                "email": "valid@example.com",
                "hashed_password": "hash",
                "first_name": "Test",
            }
        )

        # THEN
        assert user.email == "valid@example.com"

    def test_create_user(self, session):
        # GIVEN
        user = User(
            email="test@example.com",
            hashed_password="hashed123",
            first_name="John",
            last_name="Doe",
        )

        # WHEN
        session.add(user)
        session.commit()
        session.refresh(user)

        # THEN
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.created_at is not None

    def test_user_email_unique(self, session):
        # GIVEN
        user1 = User(
            email="unique@example.com",
            hashed_password="hash1",
            first_name="First",
            last_name="User",
        )
        user2 = User(
            email="unique@example.com",
            hashed_password="hash2",
            first_name="Second",
            last_name="User",
        )
        session.add(user1)
        session.commit()

        # WHEN/THEN
        session.add(user2)
        with pytest.raises(IntegrityError):
            session.commit()


class TestProjectModel:
    """Tests for Project model."""

    def test_scale_min_greater_than_scale_max_raises_error(self):
        """
        GIVEN scale_min >= scale_max
        WHEN Project is validated
        THEN ValidationError is raised
        """
        from pydantic import ValidationError

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
        from pydantic import ValidationError

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

    def test_member_role_enum(self, session):
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
    """Tests for Invitation model."""

    def test_create_invitation(self, session):
        # GIVEN
        admin = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(admin)
        session.commit()

        project = Project(name="Test Project", admin_id=admin.id)
        session.add(project)
        session.commit()

        # WHEN
        invitation = Invitation(
            project_id=project.id,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        session.add(invitation)
        session.commit()
        session.refresh(invitation)

        # THEN
        assert invitation.token is not None
        assert invitation.used_by_id is None

    def test_invitation_token_unique(self, session):
        # GIVEN
        admin = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(admin)
        session.commit()

        project = Project(name="Test Project", admin_id=admin.id)
        session.add(project)
        session.commit()

        # Create invitation with specific token
        shared_token = uuid4()

        inv1 = Invitation(
            project_id=project.id,
            token=shared_token,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        session.add(inv1)
        session.commit()

        # WHEN/THEN - duplicate token should fail
        inv2 = Invitation(
            project_id=project.id,
            token=shared_token,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        session.add(inv2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_invitation_can_be_marked_as_used(self, session):
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

        invitation = Invitation(
            project_id=project.id,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        session.add(invitation)
        session.commit()

        # WHEN
        invitation.used_by_id = expert.id
        session.commit()
        session.refresh(invitation)

        # THEN
        assert invitation.used_by_id == expert.id
        assert invitation.used_by_user == expert


class TestExpertOpinionModel:
    """Tests for ExpertOpinion model."""

    def test_invalid_fuzzy_constraints_raises_error(self):
        """
        GIVEN lower > peak
        WHEN ExpertOpinion is validated
        THEN ValidationError is raised
        """
        from pydantic import ValidationError

        # WHEN/THEN
        with pytest.raises(ValidationError, match="lower <= peak <= upper"):
            ExpertOpinion.model_validate(
                {
                    "project_id": uuid4(),
                    "user_id": uuid4(),
                    "lower_bound": 15.0,
                    "peak": 10.0,
                    "upper_bound": 20.0,
                }
            )

    def test_peak_greater_than_upper_raises_error(self):
        """
        GIVEN peak > upper
        WHEN ExpertOpinion is validated
        THEN ValidationError is raised
        """
        from pydantic import ValidationError

        # WHEN/THEN
        with pytest.raises(ValidationError, match="lower <= peak <= upper"):
            ExpertOpinion.model_validate(
                {
                    "project_id": uuid4(),
                    "user_id": uuid4(),
                    "lower_bound": 5.0,
                    "peak": 25.0,
                    "upper_bound": 20.0,
                }
            )

    def test_valid_fuzzy_constraints_passes_validation(self):
        """
        GIVEN valid fuzzy constraints (lower <= peak <= upper)
        WHEN ExpertOpinion is validated
        THEN ExpertOpinion is created successfully
        """
        # WHEN
        opinion = ExpertOpinion.model_validate(
            {
                "project_id": uuid4(),
                "user_id": uuid4(),
                "lower_bound": 5.0,
                "peak": 10.0,
                "upper_bound": 15.0,
            }
        )

        # THEN
        assert opinion.lower_bound == 5.0
        assert opinion.peak == 10.0
        assert opinion.upper_bound == 15.0

    def test_create_expert_opinion(self, session):
        # GIVEN
        user = User(
            email="expert@example.com",
            hashed_password="hash",
            first_name="Expert",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project = Project(name="Test Project", admin_id=user.id)
        session.add(project)
        session.commit()

        # WHEN
        opinion = ExpertOpinion(
            project_id=project.id,
            user_id=user.id,
            position="Senior Analyst",
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        session.add(opinion)
        session.commit()

        # THEN
        assert opinion.lower_bound == 5.0
        assert opinion.peak == 10.0
        assert opinion.upper_bound == 15.0

    def test_one_opinion_per_expert_per_project(self, session):
        # GIVEN
        user = User(
            email="expert@example.com",
            hashed_password="hash",
            first_name="Expert",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project = Project(name="Test Project", admin_id=user.id)
        session.add(project)
        session.commit()

        opinion1 = ExpertOpinion(
            project_id=project.id,
            user_id=user.id,
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        session.add(opinion1)
        session.commit()

        # WHEN/THEN - second opinion from same user on same project should fail
        opinion2 = ExpertOpinion(
            project_id=project.id,
            user_id=user.id,
            lower_bound=6.0,
            peak=11.0,
            upper_bound=16.0,
        )
        session.add(opinion2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_expert_can_have_opinions_in_different_projects(self, session):
        # GIVEN
        user = User(
            email="expert@example.com",
            hashed_password="hash",
            first_name="Expert",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project1 = Project(name="Project 1", admin_id=user.id)
        project2 = Project(name="Project 2", admin_id=user.id)
        session.add_all([project1, project2])
        session.commit()

        # WHEN - same user gives opinions in different projects
        opinion1 = ExpertOpinion(
            project_id=project1.id,
            user_id=user.id,
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        opinion2 = ExpertOpinion(
            project_id=project2.id,
            user_id=user.id,
            lower_bound=6.0,
            peak=11.0,
            upper_bound=16.0,
        )
        session.add_all([opinion1, opinion2])
        session.commit()

        # THEN
        session.refresh(user)
        assert len(user.opinions) == 2


class TestCalculationResultModel:
    """Tests for CalculationResult model."""

    def test_invalid_best_compromise_raises_error(self):
        """
        GIVEN invalid best_compromise fuzzy constraints
        WHEN CalculationResult is validated
        THEN ValidationError is raised
        """
        from pydantic import ValidationError

        # WHEN/THEN
        with pytest.raises(ValidationError, match=r"best_compromise.*lower <= peak <= upper"):
            CalculationResult.model_validate(
                {
                    "project_id": uuid4(),
                    "best_compromise_lower": 15.0,  # Invalid: lower > peak
                    "best_compromise_peak": 10.0,
                    "best_compromise_upper": 20.0,
                    "arithmetic_mean_lower": 5.0,
                    "arithmetic_mean_peak": 10.0,
                    "arithmetic_mean_upper": 15.0,
                    "median_lower": 5.0,
                    "median_peak": 10.0,
                    "median_upper": 15.0,
                    "max_error": 0.5,
                    "num_experts": 3,
                }
            )

    def test_invalid_arithmetic_mean_raises_error(self):
        """
        GIVEN invalid arithmetic_mean fuzzy constraints
        WHEN CalculationResult is validated
        THEN ValidationError is raised
        """
        from pydantic import ValidationError

        # WHEN/THEN
        with pytest.raises(ValidationError, match=r"arithmetic_mean.*lower <= peak <= upper"):
            CalculationResult.model_validate(
                {
                    "project_id": uuid4(),
                    "best_compromise_lower": 5.0,
                    "best_compromise_peak": 10.0,
                    "best_compromise_upper": 15.0,
                    "arithmetic_mean_lower": 5.0,
                    "arithmetic_mean_peak": 20.0,  # Invalid: peak > upper
                    "arithmetic_mean_upper": 15.0,
                    "median_lower": 5.0,
                    "median_peak": 10.0,
                    "median_upper": 15.0,
                    "max_error": 0.5,
                    "num_experts": 3,
                }
            )

    def test_invalid_median_raises_error(self):
        """
        GIVEN invalid median fuzzy constraints
        WHEN CalculationResult is validated
        THEN ValidationError is raised
        """
        from pydantic import ValidationError

        # WHEN/THEN
        with pytest.raises(ValidationError, match=r"median.*lower <= peak <= upper"):
            CalculationResult.model_validate(
                {
                    "project_id": uuid4(),
                    "best_compromise_lower": 5.0,
                    "best_compromise_peak": 10.0,
                    "best_compromise_upper": 15.0,
                    "arithmetic_mean_lower": 5.0,
                    "arithmetic_mean_peak": 10.0,
                    "arithmetic_mean_upper": 15.0,
                    "median_lower": 20.0,  # Invalid: lower > peak
                    "median_peak": 10.0,
                    "median_upper": 15.0,
                    "max_error": 0.5,
                    "num_experts": 3,
                }
            )

    def test_valid_fuzzy_constraints_passes_validation(self):
        """
        GIVEN valid fuzzy constraints for all fuzzy numbers
        WHEN CalculationResult is validated
        THEN CalculationResult is created successfully
        """
        # WHEN
        result = CalculationResult.model_validate(
            {
                "project_id": uuid4(),
                "best_compromise_lower": 5.0,
                "best_compromise_peak": 10.0,
                "best_compromise_upper": 15.0,
                "arithmetic_mean_lower": 4.0,
                "arithmetic_mean_peak": 9.0,
                "arithmetic_mean_upper": 14.0,
                "median_lower": 6.0,
                "median_peak": 11.0,
                "median_upper": 16.0,
                "max_error": 0.5,
                "num_experts": 3,
            }
        )

        # THEN
        assert result.best_compromise_peak == 10.0
        assert result.arithmetic_mean_peak == 9.0
        assert result.median_peak == 11.0

    def test_create_calculation_result(self, session):
        # GIVEN
        user = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project = Project(name="Test Project", admin_id=user.id)
        session.add(project)
        session.commit()

        # WHEN
        result = CalculationResult(
            project_id=project.id,
            best_compromise_lower=5.0,
            best_compromise_peak=10.0,
            best_compromise_upper=15.0,
            arithmetic_mean_lower=4.5,
            arithmetic_mean_peak=9.5,
            arithmetic_mean_upper=14.5,
            median_lower=5.5,
            median_peak=10.5,
            median_upper=15.5,
            max_error=0.5,
            num_experts=3,
        )
        session.add(result)
        session.commit()

        # THEN
        assert result.best_compromise_peak == 10.0
        assert result.num_experts == 3

    def test_project_id_unique(self, session):
        # GIVEN
        user = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project = Project(name="Test Project", admin_id=user.id)
        session.add(project)
        session.commit()

        result1 = CalculationResult(
            project_id=project.id,
            best_compromise_lower=5.0,
            best_compromise_peak=10.0,
            best_compromise_upper=15.0,
            arithmetic_mean_lower=4.5,
            arithmetic_mean_peak=9.5,
            arithmetic_mean_upper=14.5,
            median_lower=5.5,
            median_peak=10.5,
            median_upper=15.5,
            max_error=0.5,
            num_experts=3,
        )
        session.add(result1)
        session.commit()

        # WHEN/THEN
        result2 = CalculationResult(
            project_id=project.id,
            best_compromise_lower=6.0,
            best_compromise_peak=11.0,
            best_compromise_upper=16.0,
            arithmetic_mean_lower=5.5,
            arithmetic_mean_peak=10.5,
            arithmetic_mean_upper=15.5,
            median_lower=6.5,
            median_peak=11.5,
            median_upper=16.5,
            max_error=0.6,
            num_experts=4,
        )
        session.add(result2)
        with pytest.raises(IntegrityError):
            session.commit()


class TestPasswordResetTokenModel:
    """Tests for PasswordResetToken model."""

    def test_create_reset_token(self, session):
        # GIVEN
        user = User(
            email="user@example.com",
            hashed_password="hash",
            first_name="Test",
            last_name="User",
        )
        session.add(user)
        session.commit()

        # WHEN
        token = PasswordResetToken(
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        session.add(token)
        session.commit()
        session.refresh(token)

        # THEN
        assert token.token is not None
        assert token.used_at is None
        assert token.user_id == user.id

    def test_reset_token_unique(self, session):
        # GIVEN
        user = User(
            email="user@example.com",
            hashed_password="hash",
            first_name="Test",
            last_name="User",
        )
        session.add(user)
        session.commit()

        shared_token = uuid4()

        token1 = PasswordResetToken(
            user_id=user.id,
            token=shared_token,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        session.add(token1)
        session.commit()

        # WHEN/THEN - duplicate token should fail
        token2 = PasswordResetToken(
            user_id=user.id,
            token=shared_token,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        session.add(token2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_user_can_have_multiple_reset_tokens(self, session):
        # GIVEN
        user = User(
            email="user@example.com",
            hashed_password="hash",
            first_name="Test",
            last_name="User",
        )
        session.add(user)
        session.commit()

        # WHEN - multiple tokens for same user (e.g., requested reset twice)
        token1 = PasswordResetToken(
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        token2 = PasswordResetToken(
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        )
        session.add_all([token1, token2])
        session.commit()

        # THEN
        session.refresh(user)
        assert len(user.reset_tokens) == 2


class TestRelationships:
    """Tests for model relationships."""

    def test_user_owned_projects(self, session):
        # GIVEN
        user = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project1 = Project(name="Project 1", admin_id=user.id)
        project2 = Project(name="Project 2", admin_id=user.id)
        session.add_all([project1, project2])
        session.commit()

        # WHEN
        session.refresh(user)

        # THEN
        assert len(user.owned_projects) == 2

    def test_project_opinions(self, session):
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

        opinion1 = ExpertOpinion(
            project_id=project.id,
            user_id=admin.id,
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        opinion2 = ExpertOpinion(
            project_id=project.id,
            user_id=expert.id,
            lower_bound=6.0,
            peak=11.0,
            upper_bound=16.0,
        )
        session.add_all([opinion1, opinion2])
        session.commit()

        # WHEN
        session.refresh(project)

        # THEN
        assert len(project.opinions) == 2

    def test_project_members_relationship(self, session):
        # GIVEN
        admin = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        expert1 = User(
            email="expert1@example.com",
            hashed_password="hash",
            first_name="Expert1",
            last_name="User",
        )
        expert2 = User(
            email="expert2@example.com",
            hashed_password="hash",
            first_name="Expert2",
            last_name="User",
        )
        session.add_all([admin, expert1, expert2])
        session.commit()

        project = Project(name="Test Project", admin_id=admin.id)
        session.add(project)
        session.commit()

        member1 = ProjectMember(
            project_id=project.id,
            user_id=expert1.id,
            role=MemberRole.EXPERT,
        )
        member2 = ProjectMember(
            project_id=project.id,
            user_id=expert2.id,
            role=MemberRole.EXPERT,
        )
        session.add_all([member1, member2])
        session.commit()

        # WHEN
        session.refresh(project)

        # THEN
        assert len(project.members) == 2

    def test_project_result_one_to_one(self, session):
        # GIVEN
        user = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project = Project(name="Test Project", admin_id=user.id)
        session.add(project)
        session.commit()

        result = CalculationResult(
            project_id=project.id,
            best_compromise_lower=5.0,
            best_compromise_peak=10.0,
            best_compromise_upper=15.0,
            arithmetic_mean_lower=4.5,
            arithmetic_mean_peak=9.5,
            arithmetic_mean_upper=14.5,
            median_lower=5.5,
            median_peak=10.5,
            median_upper=15.5,
            max_error=0.5,
            num_experts=3,
        )
        session.add(result)
        session.commit()

        # WHEN
        session.refresh(project)

        # THEN - one-to-one relationship returns single object, not list
        assert project.result is not None
        assert project.result.best_compromise_peak == 10.0

    def test_project_invitations_relationship(self, session):
        # GIVEN
        user = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project = Project(name="Test Project", admin_id=user.id)
        session.add(project)
        session.commit()

        inv1 = Invitation(
            project_id=project.id,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        inv2 = Invitation(
            project_id=project.id,
            expires_at=datetime.now(UTC) + timedelta(days=14),
        )
        session.add_all([inv1, inv2])
        session.commit()

        # WHEN
        session.refresh(project)

        # THEN
        assert len(project.invitations) == 2
