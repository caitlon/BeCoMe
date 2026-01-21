"""Expert opinion business logic service."""

from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, col, select

from api.db.models import ExpertOpinion, User
from api.exceptions import OpinionNotFoundError


class OpinionService:
    """Service for expert opinion operations."""

    def __init__(self, session: Session) -> None:
        """Initialize with database session.

        :param session: SQLModel session for database operations
        """
        self._session = session

    def get_opinions_for_project(self, project_id: UUID) -> list[tuple[ExpertOpinion, User]]:
        """Get all opinions for a project with user details.

        :param project_id: Project UUID
        :return: List of (opinion, user) tuples ordered by creation date
        """
        statement = (
            select(ExpertOpinion, User)
            .join(User, ExpertOpinion.user_id == User.id)  # type: ignore[arg-type]
            .where(ExpertOpinion.project_id == project_id)
            .order_by(col(ExpertOpinion.created_at))
        )
        return list(self._session.exec(statement).all())

    def get_user_opinion(self, project_id: UUID, user_id: UUID) -> ExpertOpinion | None:
        """Get user's opinion for a project.

        :param project_id: Project UUID
        :param user_id: User UUID
        :return: Opinion if exists, None otherwise
        """
        statement = select(ExpertOpinion).where(
            ExpertOpinion.project_id == project_id,
            ExpertOpinion.user_id == user_id,
        )
        return self._session.exec(statement).first()

    def upsert_opinion(
        self,
        project_id: UUID,
        user_id: UUID,
        position: str,
        lower_bound: float,
        peak: float,
        upper_bound: float,
    ) -> tuple[ExpertOpinion, bool]:
        """Create or update user's opinion for a project.

        :param project_id: Project UUID
        :param user_id: User UUID
        :param position: Expert's position/role
        :param lower_bound: Fuzzy number lower bound
        :param peak: Fuzzy number peak
        :param upper_bound: Fuzzy number upper bound
        :return: Tuple of (opinion, is_new) where is_new indicates creation
        """
        existing = self.get_user_opinion(project_id, user_id)

        if existing:
            existing.position = position
            existing.lower_bound = lower_bound
            existing.peak = peak
            existing.upper_bound = upper_bound
            self._session.add(existing)
            self._session.commit()
            self._session.refresh(existing)
            return existing, False

        opinion = ExpertOpinion(
            project_id=project_id,
            user_id=user_id,
            position=position,
            lower_bound=lower_bound,
            peak=peak,
            upper_bound=upper_bound,
        )
        self._session.add(opinion)
        self._session.commit()
        self._session.refresh(opinion)
        return opinion, True

    def delete_opinion(self, project_id: UUID, user_id: UUID) -> None:
        """Delete user's opinion for a project.

        :param project_id: Project UUID
        :param user_id: User UUID
        :raises OpinionNotFoundError: If opinion doesn't exist
        """
        opinion = self.get_user_opinion(project_id, user_id)
        if not opinion:
            raise OpinionNotFoundError("Opinion not found")

        self._session.delete(opinion)
        self._session.commit()

    def count_opinions(self, project_id: UUID) -> int:
        """Count opinions for a project.

        :param project_id: Project UUID
        :return: Number of opinions
        """
        statement = (
            select(func.count())
            .select_from(ExpertOpinion)
            .where(ExpertOpinion.project_id == project_id)
        )
        return self._session.exec(statement).one()
