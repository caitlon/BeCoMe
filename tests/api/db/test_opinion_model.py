"""Tests for ExpertOpinion and CalculationResult models."""

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from api.db.models import CalculationResult, ExpertOpinion, Project, User


class TestExpertOpinionModel:
    """Tests for ExpertOpinion model."""

    def test_invalid_fuzzy_constraints_raises_error(self):
        """
        GIVEN lower > peak
        WHEN ExpertOpinion is validated
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="lower <= peak <= upper"):
            ExpertOpinion.model_validate(
                {
                    "project_id": uuid4(),
                    "user_id": uuid4(),
                    "lower_bound": 15.0,
                    "peak": 10.0,
                    "upper_bound": 20.0,
                }
            )

    def test_peak_greater_than_upper_raises_error(self):
        """
        GIVEN peak > upper
        WHEN ExpertOpinion is validated
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="lower <= peak <= upper"):
            ExpertOpinion.model_validate(
                {
                    "project_id": uuid4(),
                    "user_id": uuid4(),
                    "lower_bound": 5.0,
                    "peak": 25.0,
                    "upper_bound": 20.0,
                }
            )

    def test_valid_fuzzy_constraints_passes_validation(self):
        """
        GIVEN valid fuzzy constraints (lower <= peak <= upper)
        WHEN ExpertOpinion is validated
        THEN ExpertOpinion is created successfully
        """
        # WHEN
        opinion = ExpertOpinion.model_validate(
            {
                "project_id": uuid4(),
                "user_id": uuid4(),
                "lower_bound": 5.0,
                "peak": 10.0,
                "upper_bound": 15.0,
            }
        )

        # THEN
        assert opinion.lower_bound == 5.0
        assert opinion.peak == 10.0
        assert opinion.upper_bound == 15.0

    def test_create_expert_opinion(self, session):
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

        # WHEN
        opinion = ExpertOpinion(
            project_id=project.id,
            user_id=user.id,
            position="Senior Analyst",
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        session.add(opinion)
        session.commit()

        # THEN
        assert opinion.lower_bound == 5.0
        assert opinion.peak == 10.0
        assert opinion.upper_bound == 15.0

    def test_one_opinion_per_expert_per_project(self, session):
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

        opinion1 = ExpertOpinion(
            project_id=project.id,
            user_id=user.id,
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        session.add(opinion1)
        session.commit()

        # WHEN/THEN - second opinion from same user on same project should fail
        opinion2 = ExpertOpinion(
            project_id=project.id,
            user_id=user.id,
            lower_bound=6.0,
            peak=11.0,
            upper_bound=16.0,
        )
        session.add(opinion2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_expert_can_have_opinions_in_different_projects(self, session):
        # GIVEN
        user = User(
            email="expert@example.com",
            hashed_password="hash",
            first_name="Expert",
            last_name="User",
        )
        session.add(user)
        session.commit()

        project1 = Project(name="Project 1", admin_id=user.id)
        project2 = Project(name="Project 2", admin_id=user.id)
        session.add_all([project1, project2])
        session.commit()

        # WHEN - same user gives opinions in different projects
        opinion1 = ExpertOpinion(
            project_id=project1.id,
            user_id=user.id,
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )
        opinion2 = ExpertOpinion(
            project_id=project2.id,
            user_id=user.id,
            lower_bound=6.0,
            peak=11.0,
            upper_bound=16.0,
        )
        session.add_all([opinion1, opinion2])
        session.commit()

        # THEN
        session.refresh(user)
        assert len(user.opinions) == 2


class TestCalculationResultModel:
    """Tests for CalculationResult model."""

    def test_invalid_best_compromise_raises_error(self):
        """
        GIVEN invalid best_compromise fuzzy constraints
        WHEN CalculationResult is validated
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match=r"best_compromise.*lower <= peak <= upper"):
            CalculationResult.model_validate(
                {
                    "project_id": uuid4(),
                    "best_compromise_lower": 15.0,  # Invalid: lower > peak
                    "best_compromise_peak": 10.0,
                    "best_compromise_upper": 20.0,
                    "arithmetic_mean_lower": 5.0,
                    "arithmetic_mean_peak": 10.0,
                    "arithmetic_mean_upper": 15.0,
                    "median_lower": 5.0,
                    "median_peak": 10.0,
                    "median_upper": 15.0,
                    "max_error": 0.5,
                    "num_experts": 3,
                }
            )

    def test_invalid_arithmetic_mean_raises_error(self):
        """
        GIVEN invalid arithmetic_mean fuzzy constraints
        WHEN CalculationResult is validated
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match=r"arithmetic_mean.*lower <= peak <= upper"):
            CalculationResult.model_validate(
                {
                    "project_id": uuid4(),
                    "best_compromise_lower": 5.0,
                    "best_compromise_peak": 10.0,
                    "best_compromise_upper": 15.0,
                    "arithmetic_mean_lower": 5.0,
                    "arithmetic_mean_peak": 20.0,  # Invalid: peak > upper
                    "arithmetic_mean_upper": 15.0,
                    "median_lower": 5.0,
                    "median_peak": 10.0,
                    "median_upper": 15.0,
                    "max_error": 0.5,
                    "num_experts": 3,
                }
            )

    def test_invalid_median_raises_error(self):
        """
        GIVEN invalid median fuzzy constraints
        WHEN CalculationResult is validated
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match=r"median.*lower <= peak <= upper"):
            CalculationResult.model_validate(
                {
                    "project_id": uuid4(),
                    "best_compromise_lower": 5.0,
                    "best_compromise_peak": 10.0,
                    "best_compromise_upper": 15.0,
                    "arithmetic_mean_lower": 5.0,
                    "arithmetic_mean_peak": 10.0,
                    "arithmetic_mean_upper": 15.0,
                    "median_lower": 20.0,  # Invalid: lower > peak
                    "median_peak": 10.0,
                    "median_upper": 15.0,
                    "max_error": 0.5,
                    "num_experts": 3,
                }
            )

    def test_valid_fuzzy_constraints_passes_validation(self):
        """
        GIVEN valid fuzzy constraints for all fuzzy numbers
        WHEN CalculationResult is validated
        THEN CalculationResult is created successfully
        """
        # WHEN
        result = CalculationResult.model_validate(
            {
                "project_id": uuid4(),
                "best_compromise_lower": 5.0,
                "best_compromise_peak": 10.0,
                "best_compromise_upper": 15.0,
                "arithmetic_mean_lower": 4.0,
                "arithmetic_mean_peak": 9.0,
                "arithmetic_mean_upper": 14.0,
                "median_lower": 6.0,
                "median_peak": 11.0,
                "median_upper": 16.0,
                "max_error": 0.5,
                "num_experts": 3,
            }
        )

        # THEN
        assert result.best_compromise_peak == 10.0
        assert result.arithmetic_mean_peak == 9.0
        assert result.median_peak == 11.0

    def test_create_calculation_result(self, session):
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

        # WHEN
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

        # THEN
        assert result.best_compromise_peak == 10.0
        assert result.num_experts == 3

    def test_project_id_unique(self, session):
        """
        GIVEN a project with an existing calculation result
        WHEN a second result is added for the same project
        THEN IntegrityError is raised due to unique constraint
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

        result1 = CalculationResult(
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
        session.add(result1)
        session.commit()

        # WHEN/THEN
        result2 = CalculationResult(
            project_id=project.id,
            best_compromise_lower=6.0,
            best_compromise_peak=11.0,
            best_compromise_upper=16.0,
            arithmetic_mean_lower=5.5,
            arithmetic_mean_peak=10.5,
            arithmetic_mean_upper=15.5,
            median_lower=6.5,
            median_peak=11.5,
            median_upper=16.5,
            max_error=0.6,
            num_experts=4,
        )
        session.add(result2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
