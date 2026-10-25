"""Unit tests for OpinionService."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from api.db.models import ExpertOpinion, Project, User
from api.exceptions import OpinionNotFoundError, ValuesOutOfRangeError
from api.services.calculation_service import CalculationService
from api.services.opinion_service import OpinionService


class TestOpinionServiceGetOpinionsForProject:
    """Tests for OpinionService.get_opinions_for_project method."""

    def test_returns_empty_list_when_no_opinions(self):
        """Returns empty list for project without opinions."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = []
        service = OpinionService(mock_session)
        project_id = uuid4()

        # WHEN
        result = service.get_opinions_for_project(project_id)

        # THEN
        assert result == []

    def test_returns_opinions_with_users(self):
        """Returns list of OpinionWithUser instances."""
        # GIVEN
        project_id = uuid4()
        user = User(
            id=uuid4(),
            email="expert@example.com",
            first_name="Test",
            hashed_password="hash",
        )
        opinion = ExpertOpinion(
            id=uuid4(),
            project_id=project_id,
            user_id=user.id,
            position="Expert",
            lower_bound=20.0,
            peak=50.0,
            upper_bound=80.0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = [(opinion, user)]
        service = OpinionService(mock_session)

        # WHEN
        result = service.get_opinions_for_project(project_id)

        # THEN
        assert len(result) == 1
        assert result[0].opinion == opinion
        assert result[0].user == user


class TestOpinionServiceGetUserOpinion:
    """Tests for OpinionService.get_user_opinion method."""

    def test_returns_opinion_when_found(self):
        """Returns opinion when user has submitted one."""
        # GIVEN
        project_id = uuid4()
        user_id = uuid4()
        expected = ExpertOpinion(
            id=uuid4(),
            project_id=project_id,
            user_id=user_id,
            position="Expert",
            lower_bound=20.0,
            peak=50.0,
            upper_bound=80.0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = expected
        service = OpinionService(mock_session)

        # WHEN
        result = service.get_user_opinion(project_id, user_id)

        # THEN
        assert result == expected

    def test_returns_none_when_not_found(self):
        """Returns None when user has no opinion."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = OpinionService(mock_session)

        # WHEN
        result = service.get_user_opinion(uuid4(), uuid4())

        # THEN
        assert result is None


class TestOpinionServiceUpsertOpinion:
    """Tests for OpinionService.upsert_opinion method."""

    def test_creates_new_opinion(self):
        """Creates new opinion when user has none."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = OpinionService(mock_session)
        project_id = uuid4()
        user_id = uuid4()

        # WHEN
        result = service.upsert_opinion(
            project_id=project_id,
            user_id=user_id,
            position="Chairman",
            lower_bound=30.0,
            peak=60.0,
            upper_bound=90.0,
        )

        # THEN
        assert result.is_new is True
        assert result.opinion.project_id == project_id
        assert result.opinion.user_id == user_id
        assert result.opinion.position == "Chairman"
        assert result.opinion.lower_bound == 30.0
        assert result.opinion.peak == 60.0
        assert result.opinion.upper_bound == 90.0
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    def test_updates_existing_opinion(self):
        """Updates existing opinion when user already has one."""
        # GIVEN
        project_id = uuid4()
        user_id = uuid4()
        existing = ExpertOpinion(
            id=uuid4(),
            project_id=project_id,
            user_id=user_id,
            position="Expert",
            lower_bound=20.0,
            peak=50.0,
            upper_bound=80.0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = existing
        service = OpinionService(mock_session)

        # WHEN
        result = service.upsert_opinion(
            project_id=project_id,
            user_id=user_id,
            position="Senior Expert",
            lower_bound=40.0,
            peak=70.0,
            upper_bound=95.0,
        )

        # THEN
        assert result.is_new is False
        assert result.opinion.position == "Senior Expert"
        assert result.opinion.lower_bound == 40.0
        assert result.opinion.peak == 70.0
        assert result.opinion.upper_bound == 95.0
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @staticmethod
    def _upsert(service, project_id, user_id, calculation_service=None):
        return service.upsert_opinion(
            project_id=project_id,
            user_id=user_id,
            position="Expert",
            lower_bound=10.0,
            peak=20.0,
            upper_bound=30.0,
            calculation_service=calculation_service,
        )

    def test_stages_recalculation_between_flush_and_commit(self):
        """The result is staged after the opinion is flushed, in the one commit."""
        # GIVEN
        project_id = uuid4()
        calls = MagicMock()
        calls.session.exec.return_value.first.return_value = None
        service = OpinionService(calls.session)

        # WHEN
        self._upsert(service, project_id, uuid4(), calls.calculation_service)

        # THEN
        expected = [
            "session.add",
            "session.flush",
            "calculation_service.stage_recalculation",
            "session.commit",
            "session.refresh",
        ]
        assert [c[0] for c in calls.mock_calls if c[0] in expected] == expected
        calls.calculation_service.stage_recalculation.assert_called_once_with(project_id)
        calls.session.commit.assert_called_once()

    def test_failed_recalculation_commits_nothing(self):
        """An error while staging the result propagates before the commit."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        calculation_service = MagicMock(spec=CalculationService)
        calculation_service.stage_recalculation.side_effect = RuntimeError("boom")
        service = OpinionService(mock_session)

        # WHEN / THEN
        with pytest.raises(RuntimeError, match="boom"):
            self._upsert(service, uuid4(), uuid4(), calculation_service)
        mock_session.commit.assert_not_called()

    def test_without_a_calculation_service_commits_once_and_stages_nothing(self):
        """Callers that recalculate themselves get one commit and no recalculation."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = OpinionService(mock_session)

        # WHEN
        self._upsert(service, uuid4(), uuid4())

        # THEN
        mock_session.commit.assert_called_once()
        mock_session.flush.assert_called_once()


class TestOpinionServiceDeleteOpinion:
    """Tests for OpinionService.delete_opinion method."""

    def test_deletes_existing_opinion(self):
        """Deletes opinion when it exists."""
        # GIVEN
        project_id = uuid4()
        user_id = uuid4()
        existing = ExpertOpinion(
            id=uuid4(),
            project_id=project_id,
            user_id=user_id,
            position="Expert",
            lower_bound=20.0,
            peak=50.0,
            upper_bound=80.0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = existing
        service = OpinionService(mock_session)

        # WHEN
        service.delete_opinion(project_id, user_id)

        # THEN
        mock_session.delete.assert_called_once_with(existing)
        mock_session.commit.assert_called_once()

    def test_raises_when_opinion_not_found(self):
        """Raises OpinionNotFoundError when opinion doesn't exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = OpinionService(mock_session)

        # WHEN/THEN
        with pytest.raises(OpinionNotFoundError):
            service.delete_opinion(uuid4(), uuid4())

    def test_stages_recalculation_between_flush_and_commit(self):
        """The result is staged after the opinion is flushed out, in the one commit."""
        # GIVEN
        project_id = uuid4()
        existing = ExpertOpinion(
            id=uuid4(),
            project_id=project_id,
            user_id=uuid4(),
            position="Expert",
            lower_bound=20.0,
            peak=50.0,
            upper_bound=80.0,
        )
        calls = MagicMock()
        calls.session.exec.return_value.first.return_value = existing
        service = OpinionService(calls.session)

        # WHEN
        service.delete_opinion(project_id, existing.user_id, calls.calculation_service)

        # THEN
        expected = [
            "session.delete",
            "session.flush",
            "calculation_service.stage_recalculation",
            "session.commit",
        ]
        assert [c[0] for c in calls.mock_calls if c[0] in expected] == expected
        calls.calculation_service.stage_recalculation.assert_called_once_with(project_id)
        calls.session.commit.assert_called_once()

    def test_failed_recalculation_commits_nothing(self):
        """An error while staging the result propagates before the commit."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = MagicMock(spec=ExpertOpinion)
        calculation_service = MagicMock(spec=CalculationService)
        calculation_service.stage_recalculation.side_effect = RuntimeError("boom")
        service = OpinionService(mock_session)

        # WHEN / THEN
        with pytest.raises(RuntimeError, match="boom"):
            service.delete_opinion(uuid4(), uuid4(), calculation_service)
        mock_session.commit.assert_not_called()

    def test_without_a_calculation_service_commits_once_and_stages_nothing(self):
        """Without a calculation service the opinion goes in one commit, nothing recalculated."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = MagicMock(spec=ExpertOpinion)
        service = OpinionService(mock_session)

        # WHEN
        service.delete_opinion(uuid4(), uuid4())

        # THEN
        mock_session.commit.assert_called_once()


class TestOpinionServiceValidateValuesInRange:
    """Tests for OpinionService.validate_values_in_range method."""

    def test_passes_when_all_values_in_range(self):
        """No exception when all values are within project scale."""
        # GIVEN
        project = Project(
            id=uuid4(),
            name="Test",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        service = OpinionService(mock_session)

        # WHEN/THEN: no exception raised
        service.validate_values_in_range(project, 20.0, 50.0, 80.0)

    def test_raises_error_when_lower_bound_below_min(self):
        """ValuesOutOfRangeError raised when lower_bound < scale_min."""
        # GIVEN
        project = Project(
            id=uuid4(),
            name="Test",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        service = OpinionService(mock_session)

        # WHEN/THEN
        with pytest.raises(ValuesOutOfRangeError, match="within project scale"):
            service.validate_values_in_range(project, -5.0, 50.0, 80.0)

    def test_raises_error_when_peak_below_min(self):
        """ValuesOutOfRangeError raised when peak < scale_min."""
        # GIVEN
        project = Project(
            id=uuid4(),
            name="Test",
            admin_id=uuid4(),
            scale_min=10,
            scale_max=100,
        )
        mock_session = MagicMock()
        service = OpinionService(mock_session)

        # WHEN/THEN
        with pytest.raises(ValuesOutOfRangeError, match="within project scale"):
            service.validate_values_in_range(project, 15.0, 5.0, 80.0)

    def test_raises_error_when_upper_bound_above_max(self):
        """ValuesOutOfRangeError raised when upper_bound > scale_max."""
        # GIVEN
        project = Project(
            id=uuid4(),
            name="Test",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        service = OpinionService(mock_session)

        # WHEN/THEN
        with pytest.raises(ValuesOutOfRangeError, match="within project scale"):
            service.validate_values_in_range(project, 20.0, 50.0, 150.0)

    def test_passes_for_boundary_values(self):
        """No exception when values equal scale boundaries."""
        # GIVEN
        project = Project(
            id=uuid4(),
            name="Test",
            admin_id=uuid4(),
            scale_min=0,
            scale_max=100,
        )
        mock_session = MagicMock()
        service = OpinionService(mock_session)

        # WHEN/THEN: no exception raised for boundary values
        service.validate_values_in_range(project, 0.0, 50.0, 100.0)
