"""Tests for CASCADE delete behavior in database models."""

from datetime import UTC, datetime, timedelta

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


class TestProjectCascadeDelete:
    """Tests for cascade delete when project is deleted."""

    def test_deleting_project_deletes_members(self, session):
        """
        GIVEN a project with members
        WHEN the project is deleted
        THEN all memberships are deleted via CASCADE
        """
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

        membership = ProjectMember(
            project_id=project.id,
            user_id=expert.id,
            role=MemberRole.EXPERT,
        )
        session.add(membership)
        session.commit()
        membership_id = membership.id

        # WHEN
        session.delete(project)
        session.commit()

        # THEN
        deleted_membership = session.get(ProjectMember, membership_id)
        assert deleted_membership is None

    def test_deleting_project_deletes_invitations(self, session):
        """
        GIVEN a project with pending invitations
        WHEN the project is deleted
        THEN all invitations are deleted via CASCADE
        """
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

        invitation = Invitation(
            project_id=project.id,
            invitee_id=invitee.id,
            inviter_id=admin.id,
        )
        session.add(invitation)
        session.commit()
        invitation_id = invitation.id

        # WHEN
        session.delete(project)
        session.commit()

        # THEN
        deleted_invitation = session.get(Invitation, invitation_id)
        assert deleted_invitation is None

    def test_deleting_project_deletes_opinions(self, session):
        """
        GIVEN a project with expert opinions
        WHEN the project is deleted
        THEN all opinions are deleted via CASCADE
        """
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

        opinion = ExpertOpinion(
            project_id=project.id,
            user_id=user.id,
            position="Analyst",
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        session.add(opinion)
        session.commit()
        opinion_id = opinion.id

        # WHEN
        session.delete(project)
        session.commit()

        # THEN
        deleted_opinion = session.get(ExpertOpinion, opinion_id)
        assert deleted_opinion is None

    def test_deleting_project_deletes_result(self, session):
        """
        GIVEN a project with calculation result
        WHEN the project is deleted
        THEN the result is deleted via CASCADE
        """
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
        result_id = result.id

        # WHEN
        session.delete(project)
        session.commit()

        # THEN
        deleted_result = session.get(CalculationResult, result_id)
        assert deleted_result is None


class TestUserCascadeDelete:
    """Tests for user deletion behavior with passive_deletes=True.

    User relationships use passive_deletes=True, which delegates cascade
    deletion to the database engine. In SQLite (no FK enforcement by default),
    the ORM simply deletes the user row without touching child records.
    In PostgreSQL, the database-level ondelete="CASCADE" handles cleanup.

    For actual CASCADE behavior, see PostgreSQL integration tests:
    test_db_postgres_integration.py::TestCascadeDeleteWithFKEnforcement
    """

    def test_deleting_user_with_memberships_succeeds_in_sqlite(self, session):
        """
        GIVEN a user who is member of projects
        WHEN the user is deleted in SQLite
        THEN deletion succeeds (passive_deletes delegates to DB)

        In PostgreSQL, ProjectMember rows are cascade-deleted by the DB.
        In SQLite without FK enforcement, child rows become orphaned.
        """
        # GIVEN
        admin = User(
            email="admin@example.com",
            hashed_password="hash",
            first_name="Admin",
            last_name="User",
        )
        member = User(
            email="member@example.com",
            hashed_password="hash",
            first_name="Member",
            last_name="User",
        )
        session.add_all([admin, member])
        session.commit()

        project = Project(name="Test Project", admin_id=admin.id)
        session.add(project)
        session.commit()

        membership = ProjectMember(
            project_id=project.id,
            user_id=member.id,
            role=MemberRole.EXPERT,
        )
        session.add(membership)
        session.commit()
        member_id = member.id

        # WHEN
        session.delete(member)
        session.commit()

        # THEN — user is deleted
        assert session.get(User, member_id) is None

    def test_deleting_user_with_opinions_succeeds_in_sqlite(self, session):
        """
        GIVEN a user who submitted opinions
        WHEN the user is deleted in SQLite
        THEN deletion succeeds (passive_deletes delegates to DB)

        In PostgreSQL, ExpertOpinion rows are cascade-deleted by the DB.
        """
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

        opinion = ExpertOpinion(
            project_id=project.id,
            user_id=expert.id,
            position="Analyst",
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        session.add(opinion)
        session.commit()
        expert_id = expert.id

        # WHEN
        session.delete(expert)
        session.commit()

        # THEN — user is deleted
        assert session.get(User, expert_id) is None

    def test_deleting_user_with_reset_tokens_succeeds_in_sqlite(self, session):
        """
        GIVEN a user with password reset tokens
        WHEN the user is deleted in SQLite
        THEN deletion succeeds (passive_deletes delegates to DB)

        In PostgreSQL, PasswordResetToken rows are cascade-deleted by the DB.
        """
        # GIVEN
        user = User(
            email="user@example.com",
            hashed_password="hash",
            first_name="Test",
            last_name="User",
        )
        session.add(user)
        session.commit()

        token = PasswordResetToken(
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        session.add(token)
        session.commit()
        user_id = user.id

        # WHEN
        session.delete(user)
        session.commit()

        # THEN — user is deleted
        assert session.get(User, user_id) is None

    def test_deleting_admin_with_projects_succeeds_in_sqlite(self, session):
        """
        GIVEN a user who owns projects (is admin)
        WHEN the user is deleted in SQLite
        THEN deletion succeeds (passive_deletes delegates to DB)

        In PostgreSQL, Project rows are cascade-deleted by the DB.
        """
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
        admin_id = admin.id

        # WHEN
        session.delete(admin)
        session.commit()

        # THEN — user is deleted
        assert session.get(User, admin_id) is None

    def test_deleting_user_without_relations_succeeds(self, session):
        """
        GIVEN a user with no related records
        WHEN the user is deleted
        THEN deletion succeeds
        """
        # GIVEN
        user = User(
            email="lonely@example.com",
            hashed_password="hash",
            first_name="Lonely",
            last_name="User",
        )
        session.add(user)
        session.commit()
        user_id = user.id

        # WHEN
        session.delete(user)
        session.commit()

        # THEN
        deleted_user = session.get(User, user_id)
        assert deleted_user is None
