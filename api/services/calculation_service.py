"""BeCoMe calculation business logic service."""

from uuid import UUID

from sqlmodel import Session, select

from api.db.models import CalculationResult, ExpertOpinion, Project
from src.calculators.become_calculator import BeCoMeCalculator
from src.interpreters.likert_interpreter import LikertDecisionInterpreter
from src.models.become_result import BeCoMeResult
from src.models.expert_opinion import ExpertOpinion as DomainExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


class CalculationService:
    """Service for BeCoMe calculation operations."""

    LIKERT_SCALE_MIN = 0.0
    LIKERT_SCALE_MAX = 100.0

    def __init__(
        self,
        session: Session,
        calculator: BeCoMeCalculator | None = None,
        likert_interpreter: LikertDecisionInterpreter | None = None,
    ) -> None:
        """Initialize with database session and optional dependencies.

        :param session: SQLModel session for database operations
        :param calculator: BeCoMe calculator instance (default: new instance)
        :param likert_interpreter: Likert interpreter instance (default: new instance)
        """
        self._session = session
        self._calculator = calculator or BeCoMeCalculator()
        self._likert_interpreter = likert_interpreter or LikertDecisionInterpreter()

    def get_result(self, project_id: UUID) -> CalculationResult | None:
        """Get calculation result for a project.

        :param project_id: Project UUID
        :return: CalculationResult if exists, None otherwise
        """
        statement = select(CalculationResult).where(CalculationResult.project_id == project_id)
        return self._session.exec(statement).first()

    def recalculate(self, project_id: UUID) -> CalculationResult | None:
        """Recalculate BeCoMe result for a project.

        Fetches all opinions, runs calculation, and saves result.
        If no opinions exist, deletes any existing result and returns None.

        :param project_id: Project UUID
        :return: CalculationResult if opinions exist, None otherwise
        """
        opinions = self._get_opinions(project_id)

        if not opinions:
            self._delete_result(project_id)
            return None

        domain_opinions = [
            DomainExpertOpinion(
                expert_id=str(op.user_id),
                opinion=FuzzyTriangleNumber(
                    lower_bound=op.lower_bound,
                    peak=op.peak,
                    upper_bound=op.upper_bound,
                ),
            )
            for op in opinions
        ]

        result = self._calculator.calculate_compromise(domain_opinions)

        project = self._session.get(Project, project_id)
        likert_value = None
        likert_decision = None

        if project and self._is_likert_scale(project):
            likert_result = self._likert_interpreter.interpret(result.best_compromise)
            likert_value = likert_result.likert_value
            likert_decision = likert_result.decision_text

        return self._save_result(
            project_id=project_id,
            result=result,
            likert_value=likert_value,
            likert_decision=likert_decision,
        )

    def _get_opinions(self, project_id: UUID) -> list[ExpertOpinion]:
        """Get all opinions for a project."""
        statement = select(ExpertOpinion).where(ExpertOpinion.project_id == project_id)
        return list(self._session.exec(statement).all())

    def _is_likert_scale(self, project: Project) -> bool:
        """Check if project uses standard Likert scale (0-100)."""
        return (
            project.scale_min == self.LIKERT_SCALE_MIN
            and project.scale_max == self.LIKERT_SCALE_MAX
        )

    def _save_result(
        self,
        project_id: UUID,
        result: BeCoMeResult,
        likert_value: int | None,
        likert_decision: str | None,
    ) -> CalculationResult:
        """Save or update calculation result."""
        existing = self.get_result(project_id)

        if existing:
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
            self._session.add(existing)
            self._session.commit()
            self._session.refresh(existing)
            return existing

        db_result = CalculationResult(
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
        self._session.add(db_result)
        self._session.commit()
        self._session.refresh(db_result)
        return db_result

    def _delete_result(self, project_id: UUID) -> None:
        """Delete calculation result if exists."""
        existing = self.get_result(project_id)
        if existing:
            self._session.delete(existing)
            self._session.commit()
