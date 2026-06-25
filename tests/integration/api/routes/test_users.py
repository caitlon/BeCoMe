"""Tests for DELETE /api/v1/users/me endpoint."""

from fastapi import status

from tests.integration.api.conftest import DEFAULT_TEST_PASSWORD, auth_header, register_and_login


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
        token = register_and_login(client, email)

        # Delete account
        client.delete("/api/v1/users/me", headers=auth_header(token))

        # WHEN - try to login with same credentials
        response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": DEFAULT_TEST_PASSWORD},
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


class TestDeleteAccountWithOwnedProjects:
    """Account deletion is blocked while the user owns (is admin of) projects.

    Right to erasure must not silently destroy other experts' contributions, so a
    user who admins a project must transfer ownership or delete the project first.
    """

    def test_delete_account_with_owned_project_returns_409(self, client):
        """Deletion is rejected with 409 while the user admins a project."""
        # GIVEN
        token = register_and_login(client, "owner@example.com")
        client.post("/api/v1/projects", json={"name": "Owned"}, headers=auth_header(token))

        # WHEN
        response = client.delete("/api/v1/users/me", headers=auth_header(token))

        # THEN
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_account_survives_blocked_deletion(self, client):
        """A blocked deletion leaves the account usable."""
        # GIVEN
        token = register_and_login(client, "survivor@example.com")
        client.post("/api/v1/projects", json={"name": "Owned"}, headers=auth_header(token))
        client.delete("/api/v1/users/me", headers=auth_header(token))

        # WHEN
        response = client.get("/api/v1/auth/me", headers=auth_header(token))

        # THEN
        assert response.status_code == status.HTTP_200_OK

    def test_delete_account_succeeds_after_project_deleted(self, client):
        """Deletion succeeds once the owned project is gone."""
        # GIVEN
        token = register_and_login(client, "freed@example.com")
        create = client.post("/api/v1/projects", json={"name": "Owned"}, headers=auth_header(token))
        project_id = create.json()["id"]
        client.delete(f"/api/v1/projects/{project_id}", headers=auth_header(token))

        # WHEN
        response = client.delete("/api/v1/users/me", headers=auth_header(token))

        # THEN
        assert response.status_code == status.HTTP_204_NO_CONTENT
