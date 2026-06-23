"""E2E tests for the password reset endpoints.

Black-box only: the real server uses the console email sender, so the raw reset
token never appears in an HTTP response. The token round-trip is covered at the
integration layer; here we assert the publicly observable behaviors.
"""

import pytest

from tests.e2e.conftest import register_user, unique_email

NEW_PASSWORD = "BrandNewPass456!"


@pytest.mark.e2e
class TestForgotPassword:
    """E2E tests for POST /auth/forgot-password."""

    def test_known_and_unknown_email_responses_are_identical(self, http_client):
        """Known and unknown emails both return 202 with the same body."""
        # GIVEN — one registered email and one that was never registered
        email = unique_email("reset-known")
        register_user(http_client, email)

        # WHEN
        known = http_client.post("/auth/forgot-password", json={"email": email})
        unknown = http_client.post(
            "/auth/forgot-password", json={"email": unique_email("reset-ghost")}
        )

        # THEN — indistinguishable (anti-enumeration)
        assert known.status_code == unknown.status_code == 202
        assert known.json() == unknown.json()


@pytest.mark.e2e
class TestResetPassword:
    """E2E tests for POST /auth/reset-password."""

    def test_invalid_token_returns_400(self, http_client):
        """An unknown token is rejected with 400."""
        # WHEN
        response = http_client.post(
            "/auth/reset-password",
            json={"token": "definitely-not-a-real-token", "new_password": NEW_PASSWORD},
        )

        # THEN
        assert response.status_code == 400

    def test_weak_password_returns_422(self, http_client):
        """A weak new password is rejected by validation before any token check."""
        # WHEN
        response = http_client.post(
            "/auth/reset-password",
            json={"token": "any-token", "new_password": "weak"},
        )

        # THEN
        assert response.status_code == 422
