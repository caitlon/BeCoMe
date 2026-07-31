"""E2E tests for error handling and input validation."""

import pytest

from tests.e2e.conftest import (
    DEFAULT_PASSWORD,
    auth_headers,
    create_project,
    register_user,
    unique_email,
)


@pytest.mark.e2e
class TestDuplicateRegistration:
    """Registration with an already-used email must be indistinguishable from a new one."""

    def test_duplicate_registration_is_accepted_like_any_other(self, http_client):
        """Second registration with the same email is accepted with 202, same as the first."""
        # GIVEN — a registered user
        email = unique_email("dup")
        register_user(http_client, email)

        # WHEN — same email registers again
        response = http_client.post(
            "/auth/register",
            json={
                "email": email,
                "password": DEFAULT_PASSWORD,
                "first_name": "Dup",
                "last_name": "User",
            },
        )

        # THEN — the same 202 a free address gets: the endpoint never reveals that an
        # address is taken. The owner is told by email instead.
        assert response.status_code == 202


@pytest.mark.e2e
class TestInvalidFuzzyNumber:
    """Opinions with invalid fuzzy triangle constraints must be rejected."""

    def test_lower_bound_greater_than_peak_rejected(self, http_client):
        """Opinion with lower_bound > peak returns 422."""
        # GIVEN — a user with a project
        email = unique_email("fuzzy")
        token = register_user(http_client, email)
        project = create_project(http_client, token)

        # WHEN — submit opinion where lower > peak
        response = http_client.post(
            f"/projects/{project['id']}/opinions",
            json={
                "position": "Expert",
                "lower_bound": 80.0,
                "peak": 50.0,
                "upper_bound": 90.0,
            },
            headers=auth_headers(token),
        )

        # THEN
        assert response.status_code == 422

    def test_peak_greater_than_upper_bound_rejected(self, http_client):
        """Opinion with peak > upper_bound returns 422."""
        # GIVEN
        email = unique_email("fuzzy2")
        token = register_user(http_client, email)
        project = create_project(http_client, token)

        # WHEN — peak exceeds upper bound
        response = http_client.post(
            f"/projects/{project['id']}/opinions",
            json={
                "position": "Expert",
                "lower_bound": 10.0,
                "peak": 90.0,
                "upper_bound": 50.0,
            },
            headers=auth_headers(token),
        )

        # THEN
        assert response.status_code == 422


@pytest.mark.e2e
class TestAuthenticationErrors:
    """Invalid or missing tokens must result in 401."""

    def test_invalid_token_returns_401(self, http_client):
        """Request with a malformed JWT returns 401."""
        # GIVEN — invalid auth token
        # WHEN
        response = http_client.get(
            "/projects",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        # THEN
        assert response.status_code == 401

    def test_missing_auth_header_returns_401(self, http_client):
        """Request without Authorization header returns 401."""
        # GIVEN — no Authorization header
        # WHEN
        response = http_client.get("/projects")

        # THEN
        assert response.status_code == 401


@pytest.mark.e2e
class TestWeakPassword:
    """Registration with a weak password must be rejected."""

    def test_short_password_rejected(self, http_client):
        """Password shorter than 12 characters returns 422."""
        # GIVEN — weak password input
        # WHEN
        response = http_client.post(
            "/auth/register",
            json={
                "email": unique_email("weak"),
                "password": "Short1!",
                "first_name": "Weak",
                "last_name": "Pass",
            },
        )

        # THEN
        assert response.status_code == 422

    def test_password_without_special_char_rejected(self, http_client):
        """Password missing special characters returns 422."""
        # GIVEN — password missing special character
        # WHEN
        response = http_client.post(
            "/auth/register",
            json={
                "email": unique_email("nospec"),
                "password": "LongPassword123",
                "first_name": "No",
                "last_name": "Special",
            },
        )

        # THEN
        assert response.status_code == 422
