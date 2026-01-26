"""BeCoMe calculation business logic service."""

from uuid import UUID

from sqlmodel import Session, select

from api.db.models import CalculationResult, ExpertOpinion, Project
from api.services.base import BaseService
from api.services.mappers import BeCoMeResultMapper
from api.services.protocols import CalculatorProtocol, LikertInterpreterProtocol
from src.calculators.become_calculator import BeCoMeCalculator
from src.interpreters.likert_interpreter import LikertDecisionInterpreter
from src.models.become_result import BeCoMeResult
from src.models.expert_opinion import ExpertOpinion as DomainExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


class CalculationService(BaseService):
    """Service for BeCoMe calculation operations."""

    def __init__(
        self,
        session: Session,
        calculator: CalculatorProtocol | None = None,
        likert_interpreter: LikertInterpreterProtocol | None = None,
        likert_scale_min: float = 0.0,
        likert_scale_max: float = 100.0,
    ) -> None:
        """Initialize with database session and optional dependencies.

        :param session: SQLModel session for database operations
        :param calculator: Calculator implementing CalculatorProtocol
        :param likert_interpreter: Interpreter implementing LikertInterpreterProtocol
        :param likert_scale_min: Minimum value for Likert scale (default: 0.0)
        :param likert_scale_max: Maximum value for Likert scale (default: 100.0)
        """
        super().__init__(session)
        self._calculator: CalculatorProtocol = calculator or BeCoMeCalculator()
        self._likert_interpreter: LikertInterpreterProtocol = (
            likert_interpreter or LikertDecisionInterpreter()
        )
        self._likert_scale_min = likert_scale_min
        self._likert_scale_max = likert_scale_max

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
            project.scale_min == self._likert_scale_min
            and project.scale_max == self._likert_scale_max
        )

    def _save_result(
        self,
        project_id: UUID,
        result: BeCoMeResult,
        likert_value: int | None,
        likert_decision: str | None,
    ) -> CalculationResult:
        """Save or update calculation result using mapper."""
        existing = self.get_result(project_id)

        if existing:
            BeCoMeResultMapper.update_db_model(existing, result, likert_value, likert_decision)
            return self._save_and_refresh(existing)

        db_result = BeCoMeResultMapper.to_db_model(
            project_id, result, likert_value, likert_decision
        )
        return self._save_and_refresh(db_result)

    def _delete_result(self, project_id: UUID) -> None:
        """Delete calculation result if exists."""
        existing = self.get_result(project_id)
        if existing:
            self._delete_and_commit(existing)
