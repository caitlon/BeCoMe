"""API tests for /calculate endpoint using reference case studies.

These tests verify that the API returns the same results as the core
BeCoMeCalculator when given the same expert opinion data. The route needs a signed-in
user, so the ``client`` fixture here carries a user's token; ``anonymous_client`` is the
same app without one.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from api.auth.cookies import CSRF_COOKIE
from api.auth.jwt import ALGORITHM, create_access_token
from api.config import get_settings
from api.middleware.rate_limit import LIMIT_STANDARD, limiter
from src.exceptions import BeCoMeError
from tests.integration.api.conftest import (
    DEFAULT_TEST_PASSWORD,
    auth_header,
    register_and_login,
    register_verified,
)
from tests.reference.budget_case import BUDGET_CASE
from tests.reference.floods_case import FLOODS_CASE
from tests.reference.pendlers_case import PENDLERS_CASE

CALCULATE_URL = "/api/v1/calculate"
ONE_EXPERT = {"experts": [{"name": "Solo", "lower": 10.0, "peak": 20.0, "upper": 30.0}]}


@pytest.fixture
def client(client: TestClient) -> TestClient:
    """The shared header-auth client, signed in as a registered user."""
    token = register_and_login(client, "calculator@example.com")
    client.headers.update(auth_header(token))
    return client


@pytest.fixture
def anonymous_client(client: TestClient) -> TestClient:
    """A client for the same app that sends no credentials."""
    return TestClient(client.app)


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
            "api.routes.calculate.BeCoMeCalculator.calculate_compromise",
            side_effect=BeCoMeError(error_message),
        ):
            response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 400
        assert response.json()["detail"] == error_message

    def test_too_many_experts_returns_422(self, client: TestClient):
        """
        GIVEN more experts than the allowed maximum
        WHEN POST /api/v1/calculate is called
        THEN response status is 422 (validation error)
        """
        # GIVEN
        experts = [
            {"name": f"E{i}", "lower": 0.0, "peak": 10.0, "upper": 20.0} for i in range(1001)
        ]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 422


class TestCalculateEdgeCases:
    """Edge case tests for /calculate endpoint."""

    def test_single_expert_returns_same_values_everywhere(self, client: TestClient):
        """
        GIVEN single expert
        WHEN POST /api/v1/calculate is called
        THEN all aggregations return same values and error is zero
        """
        # GIVEN
        experts = [{"name": "Solo", "lower": 10.0, "peak": 20.0, "upper": 30.0}]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        data = response.json()

        assert data["best_compromise"] == data["arithmetic_mean"]
        assert data["best_compromise"] == data["median"]
        assert data["max_error"] == 0.0
        assert data["num_experts"] == 1

    def test_two_experts_uses_even_strategy(self, client: TestClient):
        """
        GIVEN two experts (minimum for even strategy)
        WHEN POST /api/v1/calculate is called
        THEN calculation completes with even number flag
        """
        # GIVEN
        experts = [
            {"name": "E1", "lower": 0.0, "peak": 10.0, "upper": 20.0},
            {"name": "E2", "lower": 20.0, "peak": 30.0, "upper": 40.0},
        ]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert data["num_experts"] == 2

    def test_negative_values_accepted(self, client: TestClient):
        """
        GIVEN negative fuzzy values
        WHEN POST /api/v1/calculate is called
        THEN calculation completes successfully
        """
        # GIVEN
        experts = [
            {"name": "E1", "lower": -30.0, "peak": -20.0, "upper": -10.0},
            {"name": "E2", "lower": -20.0, "peak": -10.0, "upper": 0.0},
        ]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert data["best_compromise"]["peak"] < 0

    def test_zero_values_accepted(self, client: TestClient):
        """
        GIVEN all zero values (degenerate triangle)
        WHEN POST /api/v1/calculate is called
        THEN calculation completes successfully
        """
        # GIVEN
        experts = [
            {"name": "E1", "lower": 0.0, "peak": 0.0, "upper": 0.0},
            {"name": "E2", "lower": 0.0, "peak": 0.0, "upper": 0.0},
        ]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert data["best_compromise"]["peak"] == 0.0
        assert data["best_compromise"]["lower"] == 0.0
        assert data["best_compromise"]["upper"] == 0.0

    def test_many_experts_completes_successfully(self, client: TestClient):
        """
        GIVEN 100 experts
        WHEN POST /api/v1/calculate is called
        THEN calculation completes successfully
        """
        # GIVEN
        experts = [
            {
                "name": f"E{i}",
                "lower": float(i),
                "peak": float(i + 5),
                "upper": float(i + 10),
            }
            for i in range(100)
        ]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        assert response.json()["num_experts"] == 100

    def test_identical_opinions_zero_error(self, client: TestClient):
        """
        GIVEN all identical expert opinions
        WHEN POST /api/v1/calculate is called
        THEN max_error is zero
        """
        # GIVEN
        experts = [{"name": f"E{i}", "lower": 10.0, "peak": 20.0, "upper": 30.0} for i in range(5)]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert data["max_error"] == 0.0

    def test_peak_greater_than_upper_returns_422(self, client: TestClient):
        """
        GIVEN expert data where peak > upper
        WHEN POST /api/v1/calculate is called
        THEN response status is 422 (validation error)
        """
        # GIVEN
        experts = [{"name": "Test", "lower": 5.0, "peak": 20.0, "upper": 15.0}]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 422

    def test_all_constraints_violated_returns_422(self, client: TestClient):
        """
        GIVEN expert data where all constraints violated (lower > peak > upper)
        WHEN POST /api/v1/calculate is called
        THEN response status is 422 (validation error)
        """
        # GIVEN
        experts = [{"name": "Test", "lower": 20.0, "peak": 15.0, "upper": 10.0}]

        # WHEN
        response = client.post("/api/v1/calculate", json={"experts": experts})

        # THEN
        assert response.status_code == 422


def _expired_token_header() -> dict[str, str]:
    """Bearer header carrying a correctly signed access token that ran out a minute ago."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "exp": now - timedelta(minutes=1),
        "iat": now - timedelta(minutes=16),
        "jti": uuid4().hex,
        "sid": uuid4().hex,
        "type": "access",
    }
    return auth_header(jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM))


class TestRequiresSignIn:
    """POST /calculate answers only a signed-in user."""

    @pytest.mark.parametrize(
        "headers",
        [
            pytest.param({}, id="no-credentials"),
            pytest.param(auth_header("not-a-token"), id="malformed-token"),
            pytest.param(_expired_token_header(), id="expired-token"),
            pytest.param(auth_header(create_access_token(uuid4())), id="unknown-user"),
        ],
    )
    def test_request_without_a_valid_session_is_refused(
        self, anonymous_client: TestClient, headers: dict[str, str]
    ):
        """
        GIVEN a request with no credentials, or with a token that does not identify a user
        WHEN POST /api/v1/calculate is called
        THEN response status is 401 and the calculator is never reached
        """
        # WHEN
        with patch(
            "api.routes.calculate.BeCoMeCalculator.calculate_compromise"
        ) as calculate_compromise:
            response = anonymous_client.post(CALCULATE_URL, json=ONE_EXPERT, headers=headers)

        # THEN
        assert response.status_code == 401
        calculate_compromise.assert_not_called()

    def test_bearer_token_is_accepted(self, client: TestClient):
        """
        GIVEN a signed-in user sending a Bearer token
        WHEN POST /api/v1/calculate is called
        THEN response status is 200
        """
        # WHEN
        response = client.post(CALCULATE_URL, json=ONE_EXPERT)

        # THEN
        assert response.status_code == 200


class TestSessionCookie:
    """The browser's session cookie signs a user in, and the CSRF guard applies as elsewhere."""

    EMAIL = "calculator-cookie@example.com"

    def _sign_in(self, cookie_client: TestClient) -> dict[str, str]:
        """Log in through the cookie flow and return the CSRF header the session expects."""
        register_verified(cookie_client, self.EMAIL)
        cookie_client.post(
            "/api/v1/auth/login",
            data={"username": self.EMAIL, "password": DEFAULT_TEST_PASSWORD},
        )
        return {"X-CSRF-Token": cookie_client.cookies.get(CSRF_COOKIE)}

    def test_cookie_with_csrf_header_is_accepted(self, cookie_client: TestClient):
        """
        GIVEN a user signed in by cookie
        WHEN POST /api/v1/calculate carries the CSRF header
        THEN response status is 200
        """
        # GIVEN
        csrf = self._sign_in(cookie_client)

        # WHEN
        response = cookie_client.post(CALCULATE_URL, json=ONE_EXPERT, headers=csrf)

        # THEN
        assert response.status_code == 200

    def test_cookie_without_csrf_header_is_refused(self, cookie_client: TestClient):
        """
        GIVEN a user signed in by cookie
        WHEN POST /api/v1/calculate carries no CSRF header
        THEN response status is 403
        """
        # GIVEN
        self._sign_in(cookie_client)

        # WHEN
        response = cookie_client.post(CALCULATE_URL, json=ONE_EXPERT)

        # THEN
        assert response.status_code == 403


class TestLimitIsPerUser:
    """With the limiter on, POST /calculate counts requests per signed-in user."""

    ADDRESS = "203.0.113.10"
    OTHER_ADDRESS = "203.0.113.11"

    @pytest.fixture
    def tokens(self, anonymous_client: TestClient) -> tuple[str, str]:
        """Two users' tokens, registered while the limiter is still off."""
        return (
            register_and_login(anonymous_client, "calc-a@example.com"),
            register_and_login(anonymous_client, "calc-b@example.com"),
        )

    @pytest.fixture
    def limited_user_a(self, anonymous_client: TestClient, tokens: tuple[str, str]):
        """Switch the limiter on and spend user A's whole allowance from one address."""
        allowed = int(LIMIT_STANDARD.split("/")[0])
        token_a, _ = tokens
        with patch.object(limiter, "enabled", True):
            limiter.reset()
            try:
                statuses = [
                    self._post(anonymous_client, token_a, self.ADDRESS).status_code
                    for _ in range(allowed)
                ]
                assert statuses == [200] * allowed
                yield
            finally:
                limiter.reset()

    @staticmethod
    def _post(app_client: TestClient, token: str, address: str):
        """POST a one-expert calculation as the token's user, from the given client address."""
        client = TestClient(app_client.app, client=(address, 50000))
        return client.post(CALCULATE_URL, json=ONE_EXPERT, headers=auth_header(token))

    def test_user_over_the_limit_is_refused(
        self, anonymous_client: TestClient, tokens: tuple[str, str], limited_user_a: None
    ):
        """
        GIVEN user A has used the minute's allowance
        WHEN A calls again
        THEN response status is 429
        """
        response = self._post(anonymous_client, tokens[0], self.ADDRESS)

        assert response.status_code == 429

    def test_user_over_the_limit_is_refused_from_another_address(
        self, anonymous_client: TestClient, tokens: tuple[str, str], limited_user_a: None
    ):
        """
        GIVEN user A has used the minute's allowance
        WHEN A calls from a different client address
        THEN response status is 429, because the count follows the user
        """
        response = self._post(anonymous_client, tokens[0], self.OTHER_ADDRESS)

        assert response.status_code == 429

    def test_other_user_on_the_same_address_is_served(
        self, anonymous_client: TestClient, tokens: tuple[str, str], limited_user_a: None
    ):
        """
        GIVEN user A has used the minute's allowance from an address
        WHEN user B calls from that address
        THEN response status is 200
        """
        response = self._post(anonymous_client, tokens[1], self.ADDRESS)

        assert response.status_code == 200
