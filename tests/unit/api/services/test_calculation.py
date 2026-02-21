"""Unit tests for CalculationService."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from api.db.models import CalculationResult, ExpertOpinion, Project
from api.services.calculation_service import CalculationService


class TestCalculationServiceGetResult:
    """Tests for CalculationService.get_result method."""

    def test_returns_result_when_found(self):
        """Returns calculation result when it exists."""
        # GIVEN
        project_id = uuid4()
        expected = CalculationResult(
            id=uuid4(),
            project_id=project_id,
            best_compromise_lower=30.0,
            best_compromise_peak=50.0,
            best_compromise_upper=70.0,
            arithmetic_mean_lower=25.0,
            arithmetic_mean_peak=50.0,
            arithmetic_mean_upper=75.0,
            median_lower=30.0,
            median_peak=55.0,
            median_upper=80.0,
            max_error=2.5,
            num_experts=3,
            calculated_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = expected
        service = CalculationService(mock_session)

        # WHEN
        result = service.get_result(project_id)

        # THEN
        assert result == expected

    def test_returns_none_when_not_found(self):
        """Returns None when no result exists."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = CalculationService(mock_session)

        # WHEN
        result = service.get_result(uuid4())

        # THEN
        assert result is None


def _build_single_opinion_service(
    lower: float,
    peak: float,
    upper: float,
    *,
    scale_min: float = 0.0,
    scale_max: float = 100.0,
) -> tuple[CalculationService, "uuid4"]:
    """Build a CalculationService with one opinion and a mock session.

    :param lower: Lower bound of fuzzy number
    :param peak: Peak of fuzzy number
    :param upper: Upper bound of fuzzy number
    :param scale_min: Project scale minimum
    :param scale_max: Project scale maximum
    :return: Tuple of (service, project_id)
    """
    project_id = uuid4()
    opinion = ExpertOpinion(
        id=uuid4(),
        project_id=project_id,
        user_id=uuid4(),
        position="Expert",
        lower_bound=lower,
        peak=peak,
        upper_bound=upper,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    project = Project(
        id=project_id,
        name="Test",
        admin_id=uuid4(),
        scale_min=scale_min,
        scale_max=scale_max,
    )
    mock_session = MagicMock()
    mock_session.exec.return_value.all.return_value = [opinion]
    mock_session.exec.return_value.first.return_value = None
    mock_session.get.return_value = project
    return CalculationService(mock_session), project_id


class TestCalculationServiceRecalculate:
    """Tests for CalculationService.recalculate method."""

    def test_deletes_result_when_no_opinions(self):
        """Deletes existing result when all opinions are removed."""
        # GIVEN
        project_id = uuid4()
        existing_result = CalculationResult(
            id=uuid4(),
            project_id=project_id,
            best_compromise_lower=30.0,
            best_compromise_peak=50.0,
            best_compromise_upper=70.0,
            arithmetic_mean_lower=25.0,
            arithmetic_mean_peak=50.0,
            arithmetic_mean_upper=75.0,
            median_lower=30.0,
            median_peak=55.0,
            median_upper=80.0,
            max_error=2.5,
            num_experts=3,
            calculated_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = []
        mock_session.exec.return_value.first.return_value = existing_result
        service = CalculationService(mock_session)

        # WHEN
        result = service.recalculate(project_id)

        # THEN
        assert result is None
        mock_session.delete.assert_called_once_with(existing_result)
        mock_session.commit.assert_called()

    def test_creates_result_with_single_opinion(self):
        """Creates result when single opinion exists."""
        # GIVEN
        service, project_id = _build_single_opinion_service(20.0, 50.0, 80.0)

        # WHEN
        result = service.recalculate(project_id)

        # THEN
        assert result is not None
        assert result.num_experts == 1
        assert result.best_compromise_lower == 20.0
        assert result.best_compromise_peak == 50.0
        assert result.best_compromise_upper == 80.0

    def test_calculates_with_multiple_opinions(self):
        """Creates result with correct calculation for multiple opinions."""
        # GIVEN
        project_id = uuid4()
        opinions = [
            ExpertOpinion(
                id=uuid4(),
                project_id=project_id,
                user_id=uuid4(),
                position="Expert 1",
                lower_bound=20.0,
                peak=40.0,
                upper_bound=60.0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
            ExpertOpinion(
                id=uuid4(),
                project_id=project_id,
                user_id=uuid4(),
                position="Expert 2",
                lower_bound=30.0,
                peak=50.0,
                upper_bound=70.0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
            ExpertOpinion(
                id=uuid4(),
                project_id=project_id,
                user_id=uuid4(),
                position="Expert 3",
                lower_bound=40.0,
                peak=60.0,
                upper_bound=80.0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
        ]
        project = Project(
            id=project_id,
            name="Test",
            admin_id=uuid4(),
            scale_min=0.0,
            scale_max=100.0,
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = opinions
        mock_session.exec.return_value.first.return_value = None
        mock_session.get.return_value = project
        service = CalculationService(mock_session)

        # WHEN
        result = service.recalculate(project_id)

        # THEN
        assert result is not None
        assert result.num_experts == 3
        mock_session.add.assert_called()

    def test_adds_likert_interpretation_for_standard_scale(self):
        """Adds Likert interpretation for 0-100 scale projects."""
        # GIVEN
        service, project_id = _build_single_opinion_service(70.0, 80.0, 90.0)

        # WHEN
        result = service.recalculate(project_id)

        # THEN
        assert result is not None
        assert result.likert_value is not None
        assert result.likert_decision is not None

    def test_skips_likert_for_non_standard_scale(self):
        """Skips Likert interpretation for non 0-100 scale."""
        # GIVEN
        service, project_id = _build_single_opinion_service(
            3.0, 4.0, 5.0, scale_min=1.0, scale_max=5.0
        )

        # WHEN
        result = service.recalculate(project_id)

        # THEN
        assert result is not None
        assert result.likert_value is None
        assert result.likert_decision is None

    def test_updates_existing_result(self):
        """Updates existing result instead of creating new."""
        # GIVEN
        project_id = uuid4()
        opinion = ExpertOpinion(
            id=uuid4(),
            project_id=project_id,
            user_id=uuid4(),
            position="Expert",
            lower_bound=20.0,
            peak=50.0,
            upper_bound=80.0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        existing_result = CalculationResult(
            id=uuid4(),
            project_id=project_id,
            best_compromise_lower=10.0,
            best_compromise_peak=30.0,
            best_compromise_upper=50.0,
            arithmetic_mean_lower=10.0,
            arithmetic_mean_peak=30.0,
            arithmetic_mean_upper=50.0,
            median_lower=10.0,
            median_peak=30.0,
            median_upper=50.0,
            max_error=1.0,
            num_experts=1,
            calculated_at=datetime.now(UTC),
        )
        project = Project(
            id=project_id,
            name="Test",
            admin_id=uuid4(),
            scale_min=0.0,
            scale_max=100.0,
        )

        mock_session = MagicMock()
        # First call for opinions, second for existing result
        mock_session.exec.return_value.all.return_value = [opinion]
        mock_session.exec.return_value.first.return_value = existing_result
        mock_session.get.return_value = project
        service = CalculationService(mock_session)

        # WHEN
        result = service.recalculate(project_id)

        # THEN
        assert result is existing_result
        assert result.best_compromise_lower == 20.0
        assert result.best_compromise_peak == 50.0
        assert result.best_compromise_upper == 80.0
        mock_session.add.assert_called()
        mock_session.commit.assert_called()
