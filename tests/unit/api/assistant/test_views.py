"""Unit tests for the assistant's allowlisted view models (fakes only, no network)."""

import pytest
from pydantic import ValidationError

from api.assistant.views import FuzzyView, OpinionView, ProjectBrief, ProjectView, ResultView


class TestProjectBriefAllowlist:
    """ProjectBrief keeps only what a project-list row may show the model."""

    def test_drops_fields_outside_the_allowlist(self):
        """
        GIVEN a raw ProjectWithRoleResponse-shaped dict with extra fields
        WHEN ProjectBrief validates it
        THEN only id, name, role, and is_example survive
        """
        # GIVEN
        raw = {
            "id": "p1",
            "name": "Flood risk",
            "role": "admin",
            "is_example": False,
            "admin_id": "u1",
            "member_count": 3,
            "created_at": "2026-01-01T00:00:00",
            "description": None,
            "scale_min": 0.0,
            "scale_max": 100.0,
            "scale_unit": "%",
        }

        # WHEN
        view = ProjectBrief.model_validate(raw)

        # THEN
        assert view.model_dump() == {
            "id": "p1",
            "name": "Flood risk",
            "role": "admin",
            "is_example": False,
        }


class TestProjectViewAllowlist:
    """ProjectView keeps the project's own fields, never who administers it."""

    def test_drops_admin_id_and_member_count(self):
        """
        GIVEN a raw ProjectWithRoleResponse-shaped dict
        WHEN ProjectView validates it
        THEN admin_id and member_count are not on the resulting model
        """
        # GIVEN
        raw = {
            "id": "p1",
            "name": "Flood risk",
            "description": None,
            "scale_min": 0.0,
            "scale_max": 100.0,
            "scale_unit": "%",
            "role": "expert",
            "admin_id": "u1",
            "member_count": 3,
            "created_at": "2026-01-01T00:00:00",
            "is_example": False,
        }

        # WHEN
        view = ProjectView.model_validate(raw)

        # THEN
        dumped = view.model_dump()
        assert "admin_id" not in dumped
        assert "member_count" not in dumped
        assert dumped["scale_unit"] == "%"


class TestOpinionViewAllowlist:
    """OpinionView never carries the identity fields OpinionResponse has."""

    def test_builds_expert_name_from_first_and_last_name(self):
        """
        GIVEN a raw OpinionResponse-shaped dict
        WHEN OpinionView validates it
        THEN expert_name is built and user_email/user_id/user_first_name are dropped
        """
        # GIVEN
        raw = {
            "id": "o1",
            "user_id": "u1",
            "user_email": "alice@example.com",
            "user_first_name": "Alice",
            "user_last_name": "Novak",
            "position": "Flood coordinator",
            "lower_bound": 10.0,
            "peak": 20.0,
            "upper_bound": 30.0,
            "centroid": 20.0,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }

        # WHEN
        view = OpinionView.model_validate(raw)

        # THEN
        assert view.expert_name == "Alice Novak"
        dumped = view.model_dump()
        assert "user_email" not in dumped
        assert "user_id" not in dumped
        assert "user_first_name" not in dumped
        assert "user_last_name" not in dumped

    def test_handles_a_missing_last_name(self):
        """
        GIVEN a raw dict whose user_last_name is None
        WHEN OpinionView validates it
        THEN expert_name is just the first name, with no trailing space
        """
        # GIVEN
        raw = {
            "user_first_name": "Alice",
            "user_last_name": None,
            "position": "Flood coordinator",
            "lower_bound": 10.0,
            "peak": 20.0,
            "upper_bound": 30.0,
            "centroid": 20.0,
        }

        # WHEN
        view = OpinionView.model_validate(raw)

        # THEN
        assert view.expert_name == "Alice"


class TestResultViewAndFuzzyView:
    """ResultView nests FuzzyView for each of the three fuzzy numbers."""

    def test_parses_nested_fuzzy_numbers(self):
        """
        GIVEN a raw CalculationResultResponse-shaped dict
        WHEN ResultView validates it
        THEN each fuzzy number becomes a FuzzyView
        """
        # GIVEN
        raw = {
            "best_compromise": {"lower": 1.0, "peak": 2.0, "upper": 3.0, "centroid": 2.0},
            "arithmetic_mean": {"lower": 1.0, "peak": 2.0, "upper": 3.0, "centroid": 2.0},
            "median": {"lower": 1.0, "peak": 2.0, "upper": 3.0, "centroid": 2.0},
            "max_error": 0.5,
            "num_experts": 4,
            "agreement_level": "high",
            "likert_value": 80,
            "likert_decision": "agree",
            "calculated_at": "2026-01-01T00:00:00",
        }

        # WHEN
        view = ResultView.model_validate(raw)

        # THEN
        assert isinstance(view.best_compromise, FuzzyView)
        assert view.best_compromise.centroid == 2.0
        assert view.agreement_level == "high"

    def test_fuzzy_view_is_frozen(self):
        """
        GIVEN a constructed FuzzyView
        WHEN a field is assigned after construction
        THEN it raises, since these are frozen allowlist views
        """
        # GIVEN
        view = FuzzyView(lower=1.0, peak=2.0, upper=3.0, centroid=2.0)

        # WHEN/THEN
        with pytest.raises(ValidationError):
            view.lower = 5.0
