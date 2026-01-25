"""Tests for expert opinion schemas."""

import math
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.db.models import ExpertOpinion, User
from api.schemas.opinion import OpinionCreate, OpinionResponse


class TestOpinionCreateValidation:
    """Validation tests for OpinionCreate schema."""

    def test_valid_opinion_accepted(self):
        """
        GIVEN valid fuzzy number values
        WHEN OpinionCreate is created
        THEN no validation error is raised
        """
        # WHEN/THEN
        opinion = OpinionCreate(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        assert opinion.lower_bound == 5.0
        assert opinion.peak == 10.0
        assert opinion.upper_bound == 15.0

    def test_nan_value_rejected(self):
        """
        GIVEN NaN value in fuzzy number
        WHEN OpinionCreate is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="finite"):
            OpinionCreate(lower_bound=5.0, peak=math.nan, upper_bound=15.0)

    def test_infinity_value_rejected(self):
        """
        GIVEN infinity value in fuzzy number
        WHEN OpinionCreate is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="finite"):
            OpinionCreate(lower_bound=5.0, peak=10.0, upper_bound=math.inf)

    def test_invalid_constraints_rejected(self):
        """
        GIVEN invalid fuzzy constraints (lower > peak)
        WHEN OpinionCreate is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="lower <= peak <= upper"):
            OpinionCreate(lower_bound=15.0, peak=10.0, upper_bound=20.0)


class TestOpinionCreateSanitization:
    """Tests for OpinionCreate position sanitization."""

    def test_html_in_position_sanitized(self):
        """
        GIVEN position with HTML tags
        WHEN OpinionCreate is created
        THEN HTML is removed from position
        """
        # WHEN
        opinion = OpinionCreate(
            position="<script>bad</script>Analyst",
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )

        # THEN
        assert opinion.position == "badAnalyst"

    def test_empty_position_preserved(self):
        """
        GIVEN empty position (default)
        WHEN OpinionCreate is created
        THEN position remains empty string
        """
        # WHEN
        opinion = OpinionCreate(
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )

        # THEN
        assert opinion.position == ""


class TestOpinionResponseFromModel:
    """Tests for OpinionResponse.from_model method."""

    def test_creates_response_from_models(self):
        """
        GIVEN ExpertOpinion and User models
        WHEN from_model is called
        THEN OpinionResponse is created with correct values
        """
        # GIVEN
        user_id = uuid4()
        opinion_id = uuid4()
        created_at = datetime.now(UTC)
        updated_at = datetime.now(UTC)

        user = User(
            id=user_id,
            email="expert@example.com",
            hashed_password="hash",
            first_name="Jane",
            last_name="Doe",
        )
        opinion = ExpertOpinion(
            id=opinion_id,
            project_id=uuid4(),
            user_id=user_id,
            position="Senior Analyst",
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
            created_at=created_at,
            updated_at=updated_at,
        )

        # WHEN
        response = OpinionResponse.from_model(opinion, user)

        # THEN
        assert response.id == str(opinion_id)
        assert response.user_id == str(user_id)
        assert response.user_email == "expert@example.com"
        assert response.user_first_name == "Jane"
        assert response.user_last_name == "Doe"
        assert response.position == "Senior Analyst"
        assert response.lower_bound == 5.0
        assert response.peak == 10.0
        assert response.upper_bound == 15.0
        assert response.created_at == created_at
        assert response.updated_at == updated_at

    def test_centroid_calculated_correctly(self):
        """
        GIVEN ExpertOpinion model
        WHEN from_model is called
        THEN centroid is calculated as (lower + peak + upper) / 3
        """
        # GIVEN
        user = User(
            id=uuid4(),
            email="expert@example.com",
            hashed_password="hash",
            first_name="Jane",
        )
        opinion = ExpertOpinion(
            id=uuid4(),
            project_id=uuid4(),
            user_id=user.id,
            lower_bound=0.0,
            peak=6.0,
            upper_bound=12.0,
        )
        expected_centroid = (0.0 + 6.0 + 12.0) / 3

        # WHEN
        response = OpinionResponse.from_model(opinion, user)

        # THEN
        assert response.centroid == expected_centroid

    def test_handles_none_last_name(self):
        """
        GIVEN User with None last_name
        WHEN from_model is called
        THEN response has None user_last_name
        """
        # GIVEN
        user = User(
            id=uuid4(),
            email="expert@example.com",
            hashed_password="hash",
            first_name="Jane",
            last_name=None,
        )
        opinion = ExpertOpinion(
            id=uuid4(),
            project_id=uuid4(),
            user_id=user.id,
            lower_bound=5.0,
            peak=10.0,
            upper_bound=15.0,
        )

        # WHEN
        response = OpinionResponse.from_model(opinion, user)

        # THEN
        assert response.user_last_name is None
