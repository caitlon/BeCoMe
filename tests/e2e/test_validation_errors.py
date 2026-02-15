"""E2E tests for validation and error handling edge cases."""

import pytest

from tests.e2e.conftest import (
    auth_headers,
    create_project,
    register_user,
    register_user_with_name,
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


@pytest.mark.e2e
class TestSpecialCharsInProjectName:
    """Project names with special characters are sanitized."""

    def test_html_stripped_special_chars_preserved(self, http_client):
        """HTML tags stripped, special characters preserved."""
        # GIVEN — authenticated user
        email = unique_email("spchars")
        token = register_user(http_client, email)

        # WHEN — create project with HTML and special chars
        response = http_client.post(
            "/projects",
            json={"name": "Test ()&@# <b>bold</b> Project"},
            headers=auth_headers(token),
        )

        # THEN — created, HTML stripped, special chars preserved or encoded
        assert response.status_code == 201
        name = response.json()["name"]
        assert "<b>" not in name
        assert "bold" in name
        assert "@#" in name
        assert "()" in name


@pytest.mark.e2e
class TestUnicodeUserNames:
    """User names with Unicode characters must be accepted."""

    def test_diacritics_accepted(self, http_client):
        """European diacritics in names stored correctly."""
        # GIVEN / WHEN — register with diacritics
        email = unique_email("diacritics")
        token = register_user_with_name(http_client, email, "François", "O'Connor")

        # THEN — names preserved
        me_resp = http_client.get("/users/me", headers=auth_headers(token))
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["first_name"] == "François"
        assert data["last_name"] == "O'Connor"

    def test_cjk_names_accepted(self, http_client):
        """CJK characters in names stored correctly."""
        # GIVEN / WHEN — register with CJK characters
        email = unique_email("cjk")
        token = register_user_with_name(http_client, email, "李", "小明")

        # THEN — names preserved
        me_resp = http_client.get("/users/me", headers=auth_headers(token))
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["first_name"] == "李"
        assert data["last_name"] == "小明"
