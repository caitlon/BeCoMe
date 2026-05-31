"""Tests that service-layer business operations emit logs."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from api.schemas.project import ProjectCreate, ProjectUpdate
from api.services.calculation_service import CalculationService
from api.services.invitation_service import InvitationService
from api.services.opinion_service import OpinionService
from api.services.project_service import ProjectService
from api.services.user_service import UserService


class TestProjectServiceLogging:
    """Project mutations are logged at INFO."""

    def test_create_project_logs_event(self):
        """create_project logs a project_created event."""
        # GIVEN
        service = ProjectService(MagicMock())

        # WHEN
        with patch("api.services.project_service.logger") as mock_logger:
            service.create_project(uuid4(), ProjectCreate(name="P", scale_min=0, scale_max=10))

        # THEN
        assert mock_logger.info.call_args[1]["extra"]["event"] == "project_created"

    def test_update_project_logs_event(self):
        """update_project logs a project_updated event."""
        # GIVEN
        service = ProjectService(MagicMock())

        # WHEN
        with patch("api.services.project_service.logger") as mock_logger:
            service.update_project(uuid4(), ProjectUpdate(name="New"))

        # THEN
        assert mock_logger.info.call_args[1]["extra"]["event"] == "project_updated"

    def test_delete_project_logs_event(self):
        """delete_project logs a project_deleted event."""
        # GIVEN
        service = ProjectService(MagicMock())

        # WHEN
        with patch("api.services.project_service.logger") as mock_logger:
            service.delete_project(uuid4())

        # THEN
        assert mock_logger.info.call_args[1]["extra"]["event"] == "project_deleted"


class TestUserServiceLogging:
    """User mutations are logged at INFO without secrets."""

    def test_create_user_logs_event_without_password(self):
        """create_user logs a user_created event and never the password."""
        # GIVEN
        session = MagicMock()
        session.exec.return_value.first.return_value = None
        service = UserService(session)

        # WHEN
        with patch("api.services.user_service.logger") as mock_logger:
            service.create_user("user@example.com", "super-secret-pw", "First")

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["event"] == "user_created"
        assert "super-secret-pw" not in str(mock_logger.info.call_args)

    def test_delete_user_logs_event(self):
        """delete_user logs a user_deleted event."""
        # GIVEN
        service = UserService(MagicMock())

        # WHEN
        with patch("api.services.user_service.logger") as mock_logger:
            service.delete_user(MagicMock())

        # THEN
        assert mock_logger.info.call_args[1]["extra"]["event"] == "user_deleted"


class TestOpinionServiceLogging:
    """Opinion mutations are logged at INFO."""

    def test_upsert_new_opinion_logs_event(self):
        """upsert_opinion logs an opinion_upserted event for a new opinion."""
        # GIVEN
        session = MagicMock()
        session.exec.return_value.first.return_value = None
        service = OpinionService(session)

        # WHEN
        with patch("api.services.opinion_service.logger") as mock_logger:
            service.upsert_opinion(uuid4(), uuid4(), "role", 1.0, 2.0, 3.0)

        # THEN
        assert mock_logger.info.call_args[1]["extra"]["event"] == "opinion_upserted"

    def test_delete_opinion_logs_event(self):
        """delete_opinion logs an opinion_deleted event."""
        # GIVEN
        session = MagicMock()
        session.exec.return_value.first.return_value = MagicMock()
        service = OpinionService(session)

        # WHEN
        with patch("api.services.opinion_service.logger") as mock_logger:
            service.delete_opinion(uuid4(), uuid4())

        # THEN
        assert mock_logger.info.call_args[1]["extra"]["event"] == "opinion_deleted"


class TestInvitationServiceLogging:
    """Invitation lifecycle events are logged at INFO."""

    def test_invite_logs_event(self):
        """invite_by_email logs an invitation_created event."""
        # GIVEN
        session = MagicMock()
        session.exec.return_value.first.side_effect = [MagicMock(), None, None]
        service = InvitationService(session)

        # WHEN
        with patch("api.services.invitation_service.logger") as mock_logger:
            service.invite_by_email(uuid4(), uuid4(), "user@example.com")

        # THEN
        assert mock_logger.info.call_args[1]["extra"]["event"] == "invitation_created"

    def test_accept_logs_event(self):
        """accept_invitation logs an invitation_accepted event."""
        # GIVEN
        session = MagicMock()
        user_id = uuid4()
        invitation = MagicMock()
        invitation.invitee_id = user_id
        session.get.return_value = invitation
        session.exec.return_value.first.return_value = None
        service = InvitationService(session)

        # WHEN
        with patch("api.services.invitation_service.logger") as mock_logger:
            service.accept_invitation(uuid4(), user_id)

        # THEN
        assert mock_logger.info.call_args[1]["extra"]["event"] == "invitation_accepted"

    def test_decline_logs_event(self):
        """decline_invitation logs an invitation_declined event."""
        # GIVEN
        session = MagicMock()
        user_id = uuid4()
        invitation = MagicMock()
        invitation.invitee_id = user_id
        session.get.return_value = invitation
        service = InvitationService(session)

        # WHEN
        with patch("api.services.invitation_service.logger") as mock_logger:
            service.decline_invitation(uuid4(), user_id)

        # THEN
        assert mock_logger.info.call_args[1]["extra"]["event"] == "invitation_declined"


class TestCalculationServiceLogging:
    """Recalculation outcomes are logged at INFO."""

    def test_recalculate_cleared_logs_event(self):
        """recalculate logs a recalculation_cleared event when no opinions exist."""
        # GIVEN
        session = MagicMock()
        session.exec.return_value.all.return_value = []
        session.exec.return_value.first.return_value = None
        service = CalculationService(session)

        # WHEN
        with patch("api.services.calculation_service.logger") as mock_logger:
            service.recalculate(uuid4())

        # THEN
        assert mock_logger.info.call_args[1]["extra"]["event"] == "recalculation_cleared"

    def test_recalculate_completed_logs_event_with_expert_count(self):
        """recalculate logs a recalculation_completed event with the expert count."""
        # GIVEN
        session = MagicMock()
        opinion = MagicMock()
        opinion.user_id = uuid4()
        opinion.lower_bound = 1.0
        opinion.peak = 2.0
        opinion.upper_bound = 3.0
        session.exec.return_value.all.return_value = [opinion]
        session.exec.return_value.first.return_value = None
        project = MagicMock()
        project.scale_min = 1.0
        project.scale_max = 10.0
        session.get.return_value = project
        service = CalculationService(session)

        # WHEN
        with patch("api.services.calculation_service.logger") as mock_logger:
            service.recalculate(uuid4())

        # THEN
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["event"] == "recalculation_completed"
        assert extra["num_experts"] == 1
