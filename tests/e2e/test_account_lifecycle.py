"""E2E tests for user account lifecycle."""

import pytest

from tests.e2e.conftest import (
    auth_headers,
    create_project,
    register_user,
    submit_opinion,
    unique_email,
)


@pytest.mark.e2e
class TestAccountLifecycle:
    """Full account lifecycle from registration to deletion."""

    def test_full_lifecycle_register_to_delete(self, http_client):
        """User registers, creates project, submits opinion, cleans up, deletes account."""
        # GIVEN — a new user with a project and opinion
        email = unique_email("lifecycle")
        token = register_user(http_client, email)

        project = create_project(http_client, token, "Lifecycle Test")
        submit_opinion(http_client, token, project["id"])

        # Verify project and opinion exist
        result = http_client.get(
            f"/projects/{project['id']}/result",
            headers=auth_headers(token),
        ).json()
        assert result is not None
        assert result["num_experts"] == 1

        # Delete project first (admin_id NOT NULL prevents user cascade)
        del_project = http_client.delete(
            f"/projects/{project['id']}",
            headers=auth_headers(token),
        )
        assert del_project.status_code == 204

        # WHEN — user deletes their account
        delete_resp = http_client.delete(
            "/users/me",
            headers=auth_headers(token),
        )

        # THEN — deletion succeeds
        assert delete_resp.status_code == 204

    def test_deleted_account_token_invalidated(self, http_client):
        """After account deletion, the old token no longer works."""
        # GIVEN — user registers and then deletes their account
        email = unique_email("deleted")
        token = register_user(http_client, email)

        http_client.delete("/users/me", headers=auth_headers(token))

        # WHEN — try to use the old token
        response = http_client.get(
            "/projects",
            headers=auth_headers(token),
        )

        # THEN — token is invalid
        assert response.status_code == 401
