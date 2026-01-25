"""Tests for model relationships."""

from api.db.models import (
    CalculationResult,
    ExpertOpinion,
    Invitation,
    MemberRole,
    Project,
    ProjectMember,
    User,
)


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
        admin = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        invitee1 = User(
            email="invitee1@example.com",
            hashed_password="hash",
            first_name="Invitee1",
            last_name="User",
        )
        invitee2 = User(
            email="invitee2@example.com",
            hashed_password="hash",
            first_name="Invitee2",
            last_name="User",
        )
        session.add_all([admin, invitee1, invitee2])
        session.commit()

        project = Project(name="Test Project", admin_id=admin.id)
        session.add(project)
        session.commit()

        inv1 = Invitation(
            project_id=project.id,
            invitee_id=invitee1.id,
            inviter_id=admin.id,
        )
        inv2 = Invitation(
            project_id=project.id,
            invitee_id=invitee2.id,
            inviter_id=admin.id,
        )
        session.add_all([inv1, inv2])
        session.commit()

        # WHEN
        session.refresh(project)

        # THEN
        assert len(project.invitations) == 2
