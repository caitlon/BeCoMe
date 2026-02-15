"""E2E tests for user profile management: update name, change password."""

import pytest

from tests.e2e.conftest import (
    DEFAULT_PASSWORD,
    auth_headers,
    register_user,
    unique_email,
)

NEW_PASSWORD = "NewSecurePass99!"


@pytest.mark.e2e
class TestUpdateProfile:
    """PUT /users/me must update first_name and last_name."""

    def test_update_profile_name(self, http_client):
        """Change first_name and last_name, then verify via GET."""
        # GIVEN — a registered user
        email = unique_email("profile")
        token = register_user(http_client, email)

        # WHEN — update profile
        update_resp = http_client.put(
            "/users/me",
            json={"first_name": "Updated", "last_name": "Name"},
            headers=auth_headers(token),
        )

        # THEN — response contains updated data
        assert update_resp.status_code == 200
        body = update_resp.json()
        assert body["first_name"] == "Updated"
        assert body["last_name"] == "Name"

        # Verify via GET
        me_resp = http_client.get("/users/me", headers=auth_headers(token))
        me_resp.raise_for_status()
        assert me_resp.json()["first_name"] == "Updated"
        assert me_resp.json()["last_name"] == "Name"


@pytest.mark.e2e
class TestChangePassword:
    """PUT /users/me/password must change the password."""

    def test_change_password_success(self, http_client):
        """Change password, then login with new password succeeds."""
        # GIVEN — a registered user
        email = unique_email("chpwd")
        token = register_user(http_client, email)

        # WHEN — change password
        change_resp = http_client.put(
            "/users/me/password",
            json={
                "current_password": DEFAULT_PASSWORD,
                "new_password": NEW_PASSWORD,
            },
            headers=auth_headers(token),
        )

        # THEN — password changed
        assert change_resp.status_code == 204

        # Login with new password works
        login_resp = http_client.post(
            "/auth/login",
            data={"username": email, "password": NEW_PASSWORD},
        )
        assert login_resp.status_code == 200
        assert login_resp.json()["access_token"]

    def test_change_password_wrong_current(self, http_client):
        """Wrong current_password must be rejected."""
        # GIVEN — a registered user
        email = unique_email("wrongcur")
        token = register_user(http_client, email)

        # WHEN — send wrong current password
        response = http_client.put(
            "/users/me/password",
            json={
                "current_password": "TotallyWrongPass1!",
                "new_password": NEW_PASSWORD,
            },
            headers=auth_headers(token),
        )

        # THEN — rejected
        assert response.status_code in (400, 401)
