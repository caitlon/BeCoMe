"""Data mappers for transforming between domain and database models."""

from uuid import UUID

from api.db.models import CalculationResult
from src.models.become_result import BeCoMeResult


class BeCoMeResultMapper:
    """Maps BeCoMeResult domain model to CalculationResult database model."""

    @staticmethod
    def to_db_model(
        project_id: UUID,
        result: BeCoMeResult,
        likert_value: int | None = None,
        likert_decision: str | None = None,
    ) -> CalculationResult:
        """Create new CalculationResult from domain BeCoMeResult.

        :param project_id: Project UUID
        :param result: Domain BeCoMeResult from calculator
        :param likert_value: Optional Likert scale value
        :param likert_decision: Optional Likert decision text
        :return: New CalculationResult instance (not yet persisted)
        """
        return CalculationResult(
            project_id=project_id,
            best_compromise_lower=result.best_compromise.lower_bound,
            best_compromise_peak=result.best_compromise.peak,
            best_compromise_upper=result.best_compromise.upper_bound,
            arithmetic_mean_lower=result.arithmetic_mean.lower_bound,
            arithmetic_mean_peak=result.arithmetic_mean.peak,
            arithmetic_mean_upper=result.arithmetic_mean.upper_bound,
            median_lower=result.median.lower_bound,
            median_peak=result.median.peak,
            median_upper=result.median.upper_bound,
            max_error=result.max_error,
            num_experts=result.num_experts,
            likert_value=likert_value,
            likert_decision=likert_decision,
        )

    @staticmethod
    def update_db_model(
        existing: CalculationResult,
        result: BeCoMeResult,
        likert_value: int | None = None,
        likert_decision: str | None = None,
    ) -> CalculationResult:
        """Update existing CalculationResult with new BeCoMeResult values.

        :param existing: Existing CalculationResult to update
        :param result: Domain BeCoMeResult from calculator
        :param likert_value: Optional Likert scale value
        :param likert_decision: Optional Likert decision text
        :return: Updated CalculationResult instance (not yet persisted)
        """
        existing.best_compromise_lower = result.best_compromise.lower_bound
        existing.best_compromise_peak = result.best_compromise.peak
        existing.best_compromise_upper = result.best_compromise.upper_bound
        existing.arithmetic_mean_lower = result.arithmetic_mean.lower_bound
        existing.arithmetic_mean_peak = result.arithmetic_mean.peak
        existing.arithmetic_mean_upper = result.arithmetic_mean.upper_bound
        existing.median_lower = result.median.lower_bound
        existing.median_peak = result.median.peak
        existing.median_upper = result.median.upper_bound
        existing.max_error = result.max_error
        existing.num_experts = result.num_experts
        existing.likert_value = likert_value
        existing.likert_decision = likert_decision
        return existing
