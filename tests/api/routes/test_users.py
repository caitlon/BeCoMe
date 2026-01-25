"""Tests for DELETE /api/v1/users/me endpoint."""

from fastapi import status

from tests.api.conftest import auth_header, register_and_login


class TestDeleteAccount:
    """Tests for DELETE /api/v1/users/me endpoint."""

    def test_delete_account_returns_204(self, client):
        """Successful account deletion returns 204 No Content."""
        # GIVEN
        token = register_and_login(client, "delete@example.com")

        # WHEN
        response = client.delete(
            "/api/v1/users/me",
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_account_removes_user(self, client):
        """Deleted user cannot access protected endpoints."""
        # GIVEN
        token = register_and_login(client, "removed@example.com")
        client.delete("/api/v1/users/me", headers=auth_header(token))

        # WHEN
        response = client.get("/api/v1/auth/me", headers=auth_header(token))

        # THEN
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_account_prevents_login(self, client):
        """Deleted user cannot log in again."""
        # GIVEN
        email = "nologin@example.com"
        password = "SecurePass123!"
        client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": "Test",
                "last_name": "User",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        token = login_response.json()["access_token"]

        # Delete account
        client.delete("/api/v1/users/me", headers=auth_header(token))

        # WHEN
        response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )

        # THEN
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_account_without_auth_returns_401(self, client):
        """Unauthenticated request returns 401."""
        # WHEN
        response = client.delete("/api/v1/users/me")

        # THEN
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_account_with_invalid_token_returns_401(self, client):
        """Invalid token returns 401."""
        # WHEN
        response = client.delete(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid_token"},
        )

        # THEN
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# NOTE: Tests for account deletion with projects are not included because
# the current data model has NOT NULL constraints on admin_id and user_id.
# This requires either:
# 1. CASCADE DELETE on projects when admin is deleted
# 2. Business logic to transfer ownership before deletion
# 3. Preventing deletion when user owns projects
# This is a separate feature that needs design decision.
