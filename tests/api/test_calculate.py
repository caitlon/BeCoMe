"""API tests for /calculate endpoint using reference case studies.

These tests verify that the API returns the same results as the core
BeCoMeCalculator when given the same expert opinion data.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.exceptions import BeCoMeError
from tests.reference.budget_case import BUDGET_CASE
from tests.reference.floods_case import FLOODS_CASE
from tests.reference.pendlers_case import PENDLERS_CASE


def _opinions_to_api_format(opinions: list) -> list[dict]:
    """Convert ExpertOpinion objects to API request format."""
    return [
        {
            "name": op.expert_id,
            "lower": op.opinion.lower_bound,
            "peak": op.opinion.peak,
            "upper": op.opinion.upper_bound,
        }
        for op in opinions
    ]


class TestBudgetCase:
    """API tests using Budget case study (22 experts, even number)."""

    def test_budget_case_returns_correct_best_compromise(self, client: TestClient):
        """
        GIVEN expert opinions from budget case study
        WHEN POST /api/v1/calculate is called
        THEN response contains correct best compromise values
        """
        # GIVEN
        experts = _opinions_to_api_format(BUDGET_CASE["opinions"])
        expected = BUDGET_CASE["expected_result"]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        data = response.json()

        assert data["best_compromise"]["lower"] == pytest.approx(
            expected["best_compromise_lower"], rel=1e-6
        )
        assert data["best_compromise"]["peak"] == pytest.approx(
            expected["best_compromise_peak"], rel=1e-6
        )
        assert data["best_compromise"]["upper"] == pytest.approx(
            expected["best_compromise_upper"], rel=1e-6
        )

    def test_budget_case_returns_correct_arithmetic_mean(self, client: TestClient):
        """
        GIVEN expert opinions from budget case study
        WHEN POST /api/v1/calculate is called
        THEN response contains correct arithmetic mean values
        """
        # GIVEN
        experts = _opinions_to_api_format(BUDGET_CASE["opinions"])
        expected = BUDGET_CASE["expected_result"]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        data = response.json()

        assert data["arithmetic_mean"]["lower"] == pytest.approx(expected["mean_lower"], rel=1e-6)
        assert data["arithmetic_mean"]["peak"] == pytest.approx(expected["mean_peak"], rel=1e-6)
        assert data["arithmetic_mean"]["upper"] == pytest.approx(expected["mean_upper"], rel=1e-6)

    def test_budget_case_returns_correct_median(self, client: TestClient):
        """
        GIVEN expert opinions from budget case study
        WHEN POST /api/v1/calculate is called
        THEN response contains correct median values
        """
        # GIVEN
        experts = _opinions_to_api_format(BUDGET_CASE["opinions"])
        expected = BUDGET_CASE["expected_result"]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        data = response.json()

        assert data["median"]["lower"] == pytest.approx(expected["median_lower"], rel=1e-6)
        assert data["median"]["peak"] == pytest.approx(expected["median_peak"], rel=1e-6)
        assert data["median"]["upper"] == pytest.approx(expected["median_upper"], rel=1e-6)

    def test_budget_case_returns_correct_metadata(self, client: TestClient):
        """
        GIVEN expert opinions from budget case study
        WHEN POST /api/v1/calculate is called
        THEN response contains correct metadata (num_experts, max_error)
        """
        # GIVEN
        experts = _opinions_to_api_format(BUDGET_CASE["opinions"])
        expected = BUDGET_CASE["expected_result"]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        data = response.json()

        assert data["num_experts"] == expected["num_experts"]
        assert data["max_error"] == pytest.approx(expected["max_error"], rel=1e-2)


class TestFloodsCase:
    """API tests using Floods case study (13 experts, odd number)."""

    def test_floods_case_returns_correct_best_compromise(self, client: TestClient):
        """
        GIVEN expert opinions from floods case study
        WHEN POST /api/v1/calculate is called
        THEN response contains correct best compromise values
        """
        # GIVEN
        experts = _opinions_to_api_format(FLOODS_CASE["opinions"])
        expected = FLOODS_CASE["expected_result"]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        data = response.json()

        assert data["best_compromise"]["lower"] == pytest.approx(
            expected["best_compromise_lower"], rel=1e-6
        )
        assert data["best_compromise"]["peak"] == pytest.approx(
            expected["best_compromise_peak"], rel=1e-6
        )
        assert data["best_compromise"]["upper"] == pytest.approx(
            expected["best_compromise_upper"], rel=1e-6
        )

    def test_floods_case_returns_correct_metadata(self, client: TestClient):
        """
        GIVEN expert opinions from floods case study (odd number)
        WHEN POST /api/v1/calculate is called
        THEN response contains correct metadata (num_experts, max_error)
        """
        # GIVEN
        experts = _opinions_to_api_format(FLOODS_CASE["opinions"])
        expected = FLOODS_CASE["expected_result"]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        data = response.json()

        assert data["num_experts"] == expected["num_experts"]
        assert data["max_error"] == pytest.approx(expected["max_error"], rel=1e-2)


class TestPendlersCase:
    """API tests using Pendlers case study (22 experts, Likert scale)."""

    def test_pendlers_case_returns_correct_best_compromise(self, client: TestClient):
        """
        GIVEN expert opinions from pendlers case study (Likert scale)
        WHEN POST /api/v1/calculate is called
        THEN response contains correct best compromise values
        """
        # GIVEN
        experts = _opinions_to_api_format(PENDLERS_CASE["opinions"])
        expected = PENDLERS_CASE["expected_result"]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        data = response.json()

        assert data["best_compromise"]["lower"] == pytest.approx(
            expected["best_compromise_lower"], rel=1e-6
        )
        assert data["best_compromise"]["peak"] == pytest.approx(
            expected["best_compromise_peak"], rel=1e-6
        )
        assert data["best_compromise"]["upper"] == pytest.approx(
            expected["best_compromise_upper"], rel=1e-6
        )

    def test_pendlers_case_crisp_values_equal(self, client: TestClient):
        """
        GIVEN Likert scale data (crisp values where lower=peak=upper)
        WHEN POST /api/v1/calculate is called
        THEN all bounds in best_compromise are equal
        """
        # GIVEN
        experts = _opinions_to_api_format(PENDLERS_CASE["opinions"])

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        data = response.json()

        bc = data["best_compromise"]
        assert bc["lower"] == pytest.approx(bc["peak"], rel=1e-6)
        assert bc["peak"] == pytest.approx(bc["upper"], rel=1e-6)


class TestValidation:
    """API validation tests."""

    def test_empty_experts_list_returns_422(self, client: TestClient):
        """
        GIVEN an empty experts list
        WHEN POST /api/v1/calculate is called
        THEN response status is 422 (validation error)
        """
        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": []})

        # THEN
        assert response.status_code == 422

    def test_invalid_fuzzy_constraints_returns_422(self, client: TestClient):
        """
        GIVEN expert data where lower > peak
        WHEN POST /api/v1/calculate is called
        THEN response status is 422 (validation error)
        """
        # GIVEN
        experts = [{"name": "Test", "lower": 10.0, "peak": 5.0, "upper": 15.0}]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 422

    def test_missing_required_field_returns_422(self, client: TestClient):
        """
        GIVEN expert data missing required field
        WHEN POST /api/v1/calculate is called
        THEN response status is 422 (validation error)
        """
        # GIVEN
        experts = [{"name": "Test", "lower": 5.0, "peak": 10.0}]  # missing 'upper'

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 422

    def test_become_error_returns_400(self, client: TestClient):
        """
        GIVEN calculator raises BeCoMeError
        WHEN POST /api/v1/calculate is called
        THEN response status is 400 with error message
        """
        # GIVEN
        experts = [{"name": "Test", "lower": 5.0, "peak": 10.0, "upper": 15.0}]
        error_message = "Calculation failed"

        # WHEN
        with patch(
            "api.main.BeCoMeCalculator.calculate_compromise",
            side_effect=BeCoMeError(error_message),
        ):
            response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 400
        assert response.json()["detail"] == error_message
