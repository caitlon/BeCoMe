"""E2E tests for validation and error handling edge cases."""

import pytest

from tests.e2e.conftest import (
    auth_headers,
    create_project,
    register_user,
    unique_email,
)


@pytest.mark.e2e
class TestLoginErrorMessage:
    """Wrong password login must return 401 with descriptive message."""

    def test_wrong_password_error_contains_credentials(self, http_client):
        """Error response mentions invalid credentials."""
        # GIVEN — a registered user
        email = unique_email("errmsg")
        register_user(http_client, email)

        # WHEN — login with wrong password
        response = http_client.post(
            "/auth/login",
            data={"username": email, "password": "CompletelyWrong1!"},
        )

        # THEN — 401 with descriptive detail
        assert response.status_code == 401
        detail = response.json().get("detail", "").lower()
        assert "credential" in detail or "password" in detail or "invalid" in detail


@pytest.mark.e2e
class TestPasswordChangeErrors:
    """Password change with wrong current password must fail."""

    def test_wrong_current_password_rejected(self, http_client):
        """Submitting wrong current password returns error."""
        # GIVEN — a registered user
        email = unique_email("pwderr")
        token = register_user(http_client, email)

        # WHEN — attempt password change with wrong current
        response = http_client.put(
            "/users/me/password",
            json={
                "current_password": "WrongOldPassword1!",
                "new_password": "BrandNewSecure99!",
            },
            headers=auth_headers(token),
        )

        # THEN — rejected with 400 or 401
        assert response.status_code in (400, 401)


@pytest.mark.e2e
class TestOpinionScaleValidation:
    """Opinion values outside project scale must be rejected."""

    def test_opinion_below_scale_min_rejected(self, http_client):
        """lower_bound below scale_min returns 422."""
        # GIVEN — a project with default scale 0-100
        email = unique_email("scalemin")
        token = register_user(http_client, email)
        project = create_project(http_client, token)

        # WHEN — submit opinion with lower_bound below 0
        response = http_client.post(
            f"/projects/{project['id']}/opinions",
            json={
                "position": "Expert",
                "lower_bound": -5.0,
                "peak": 50.0,
                "upper_bound": 80.0,
            },
            headers=auth_headers(token),
        )

        # THEN — rejected
        assert response.status_code == 422

    def test_opinion_above_scale_max_rejected(self, http_client):
        """upper_bound above scale_max returns 422."""
        # GIVEN — a project with default scale 0-100
        email = unique_email("scalemax")
        token = register_user(http_client, email)
        project = create_project(http_client, token)

        # WHEN — submit opinion with upper_bound above 100
        response = http_client.post(
            f"/projects/{project['id']}/opinions",
            json={
                "position": "Expert",
                "lower_bound": 20.0,
                "peak": 50.0,
                "upper_bound": 150.0,
            },
            headers=auth_headers(token),
        )

        # THEN — rejected
        assert response.status_code == 422
