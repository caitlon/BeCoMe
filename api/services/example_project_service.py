"""Seeding of the worked example project handed to every activated account."""

import logging
from uuid import UUID

from sqlmodel import Session, col, select

from api.data.example_project import (
    EXAMPLE_EXPERTS,
    EXAMPLE_PROJECT_TEXT,
    EXAMPLE_SCALE_MAX,
    EXAMPLE_SCALE_MIN,
    EXAMPLE_SCALE_UNIT,
)
from api.db.models import ExpertOpinion, MemberRole, Project, ProjectMember, User
from api.services.base import BaseService
from api.services.calculation_service import CalculationService

logger = logging.getLogger("api.service.example_project")

_DEFAULT_LANGUAGE = "en"


class ExampleProjectService(BaseService):
    """Give a newly activated account one finished project to look at.

    The project is real in every respect except its origin: real rows, the real
    calculator, the real detail page, and the ordinary delete flow, since the account
    that receives it is its admin. What makes it an example is the ``is_example``
    flag, which the UI reads to show a badge and a banner.

    The owner's own opinion is deliberately left out. The project opens with the 13
    opinions of the published Floods panel and the compromise they produce, so adding
    a fourteenth and watching that compromise move is the first thing the account can
    do -- and it is the one demonstration of the method that needs no explanation.

    :param session: Session the writes go through.
    :param calculation_service: Service that computes the opening result; defaults to
        one built on the same session.
    """

    def __init__(
        self,
        session: Session,
        calculation_service: CalculationService | None = None,
    ) -> None:
        """Initialize with the session and the calculator to open the project with.

        :param session: Session the writes go through.
        :param calculation_service: Calculation service, or None to build one.
        """
        super().__init__(session)
        self._calculations = calculation_service or CalculationService(session)

    def seed_for(self, user_id: UUID, language: str = _DEFAULT_LANGUAGE) -> Project | None:
        """Create the example project for an account, if it does not have one.

        :param user_id: The account that becomes the project's admin.
        :param language: UI language the stored text is written in; anything the
            content is not authored in falls back to English.
        :return: The created project, or None when nothing was seeded.
        """
        if self._already_seeded(user_id):
            logger.debug(
                "Example project already present",
                extra={"event": "example_project_skipped", "reason": "already_seeded"},
            )
            return None
        if not self._demo_pool_present():
            # The pool comes from the migration that introduced it. Without it the
            # opinions below would violate their foreign key, so refuse the whole
            # seed and say so rather than failing halfway through it.
            logger.warning(
                "Demo expert pool is missing, skipping the example project",
                extra={"event": "example_project_skipped", "reason": "missing_pool"},
            )
            return None

        text = EXAMPLE_PROJECT_TEXT.get(language, EXAMPLE_PROJECT_TEXT[_DEFAULT_LANGUAGE])
        project = Project(
            name=text.name,
            description=text.description,
            admin_id=user_id,
            scale_min=EXAMPLE_SCALE_MIN,
            scale_max=EXAMPLE_SCALE_MAX,
            scale_unit=EXAMPLE_SCALE_UNIT,
            is_example=True,
        )
        self._session.add(project)
        self._session.flush()

        self._session.add(
            ProjectMember(project_id=project.id, user_id=user_id, role=MemberRole.ADMIN)
        )
        for expert in EXAMPLE_EXPERTS:
            self._session.add(
                ProjectMember(
                    project_id=project.id,
                    user_id=expert.user_id,
                    role=MemberRole.EXPERT,
                )
            )
            self._session.add(
                ExpertOpinion(
                    project_id=project.id,
                    user_id=expert.user_id,
                    position=expert.position(language),
                    lower_bound=expert.lower_bound,
                    peak=expert.peak,
                    upper_bound=expert.upper_bound,
                )
            )
        self._session.commit()

        self._calculations.recalculate(project.id)
        self._session.refresh(project)
        logger.info(
            "Example project seeded",
            extra={
                "event": "example_project_seeded",
                "project_id": str(project.id),
                "user_id": str(user_id),
            },
        )
        return project

    def _already_seeded(self, user_id: UUID) -> bool:
        """Report whether the account already owns an example project.

        :param user_id: Account to check.
        :return: True when an example project is already there.
        """
        statement = select(Project).where(
            Project.admin_id == user_id, col(Project.is_example).is_(True)
        )
        return self._session.exec(statement).first() is not None

    def _demo_pool_present(self) -> bool:
        """Report whether every demo account the seed references exists.

        :return: True when all of them are in the database.
        """
        statement = select(User.id).where(
            col(User.id).in_([expert.user_id for expert in EXAMPLE_EXPERTS])
        )
        return len(self._session.exec(statement).all()) == len(EXAMPLE_EXPERTS)
