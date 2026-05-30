"""Database-level CHECK constraint enforcement.

These verify the database independently rejects domain-invalid rows, even when a
write bypasses the application-layer Pydantic validators (defense in depth).
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from api.db.models import CalculationResult, ExpertOpinion, Project, User


def _make_user(session) -> User:
    """Persist and return a throwaway user for foreign-key references."""
    user = User(
        email=f"{uuid4().hex}@example.com",
        hashed_password="hash",
        first_name="Test",
        last_name="User",
    )
    session.add(user)
    session.commit()
    return user


def _make_project(session, user: User) -> Project:
    """Persist and return a valid project owned by the given user."""
    project = Project(name="Project", admin_id=user.id, scale_min=0.0, scale_max=100.0)
    session.add(project)
    session.commit()
    return project


def _make_calc(project_id: UUID, **overrides: object) -> CalculationResult:
    """Build a CalculationResult with valid fuzzy ordering; override to break one rule."""
    fields: dict[str, object] = {
        "project_id": project_id,
        "best_compromise_lower": 1.0,
        "best_compromise_peak": 2.0,
        "best_compromise_upper": 3.0,
        "arithmetic_mean_lower": 1.0,
        "arithmetic_mean_peak": 2.0,
        "arithmetic_mean_upper": 3.0,
        "median_lower": 1.0,
        "median_peak": 2.0,
        "median_upper": 3.0,
        "max_error": 0.0,
        "num_experts": 3,
    }
    fields.update(overrides)
    return CalculationResult(**fields)


class TestCheckConstraints:
    """The database enforces the domain CHECK constraints."""

    def test_projects_scale_order_rejected(self, session):
        """
        GIVEN a project row whose scale_min is not below scale_max
        WHEN it is committed
        THEN the database rejects it with IntegrityError
        """
        # GIVEN
        user = _make_user(session)
        project = Project(name="Bad", admin_id=user.id, scale_min=100.0, scale_max=100.0)

        # WHEN / THEN
        session.add(project)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_expert_opinion_fuzzy_order_rejected(self, session):
        """
        GIVEN an expert opinion whose bounds violate lower <= peak <= upper
        WHEN it is committed
        THEN the database rejects it with IntegrityError
        """
        # GIVEN
        user = _make_user(session)
        project = _make_project(session, user)
        opinion = ExpertOpinion(
            project_id=project.id,
            user_id=user.id,
            position="x",
            lower_bound=5.0,
            peak=2.0,
            upper_bound=8.0,
        )

        # WHEN / THEN
        session.add(opinion)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_calculation_num_experts_must_be_positive(self, session):
        """
        GIVEN a calculation result with num_experts = 0
        WHEN it is committed
        THEN the database rejects it with IntegrityError
        """
        # GIVEN
        user = _make_user(session)
        project = _make_project(session, user)

        # WHEN / THEN
        session.add(_make_calc(project.id, num_experts=0))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_calculation_best_compromise_order_rejected(self, session):
        """
        GIVEN a result whose best_compromise bounds violate lower <= peak <= upper
        WHEN it is committed
        THEN the database rejects it with IntegrityError
        """
        # GIVEN
        user = _make_user(session)
        project = _make_project(session, user)

        # WHEN / THEN
        session.add(_make_calc(project.id, best_compromise_lower=5.0))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_calculation_arithmetic_mean_order_rejected(self, session):
        """
        GIVEN a result whose arithmetic_mean bounds violate lower <= peak <= upper
        WHEN it is committed
        THEN the database rejects it with IntegrityError
        """
        # GIVEN
        user = _make_user(session)
        project = _make_project(session, user)

        # WHEN / THEN
        session.add(_make_calc(project.id, arithmetic_mean_lower=5.0))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_calculation_median_order_rejected(self, session):
        """
        GIVEN a result whose median bounds violate lower <= peak <= upper
        WHEN it is committed
        THEN the database rejects it with IntegrityError
        """
        # GIVEN
        user = _make_user(session)
        project = _make_project(session, user)

        # WHEN / THEN
        session.add(_make_calc(project.id, median_lower=5.0))
        with pytest.raises(IntegrityError):
            session.commit()

    @pytest.mark.parametrize("value", [150, -1])
    def test_calculation_likert_value_out_of_range_rejected(self, session, value):
        """
        GIVEN a result with likert_value outside 0..100 (either bound)
        WHEN it is committed
        THEN the database rejects it with IntegrityError
        """
        # GIVEN
        user = _make_user(session)
        project = _make_project(session, user)

        # WHEN / THEN
        session.add(_make_calc(project.id, likert_value=value))
        with pytest.raises(IntegrityError):
            session.commit()
