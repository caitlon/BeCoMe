"""E2E tests for GDPR data erasure compliance.

Verifies that account deletion removes all personal data traces:
opinions, memberships, invitations, and login credentials.
Complements test_account_lifecycle.py which covers basic deletion flow.
"""

import pytest

from tests.e2e.conftest import (
    DEFAULT_PASSWORD,
    auth_headers,
    create_project,
    invite_and_accept,
    register_user,
    register_user_with_name,
    submit_opinion,
    unique_email,
)


@pytest.mark.e2e
class TestRightOfAccess:
    """GDPR Article 15 — right of access to personal data."""

    def test_user_can_access_all_profile_data(self, http_client):
        """GET /users/me returns all stored personal data."""
        # GIVEN — user registered with known details
        email = unique_email("gdpr-access")
        token = register_user_with_name(
            http_client,
            email,
            "Priscilla",
            "Testova",
        )

        # WHEN — user requests their data
        response = http_client.get("/users/me", headers=auth_headers(token))

        # THEN — all profile fields are present and correct
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert data["first_name"] == "Priscilla"
        assert data["last_name"] == "Testova"
        assert "id" in data

        # Cleanup
        http_client.delete("/users/me", headers=auth_headers(token))

    def test_data_export_endpoint_not_implemented(self, http_client):
        """No data export endpoint exists yet (GDPR Article 20 gap)."""
        # GIVEN — registered user
        email = unique_email("gdpr-export")
        token = register_user(http_client, email)

        # WHEN — user attempts to export their data
        response = http_client.get(
            "/users/me/export",
            headers=auth_headers(token),
        )

        # THEN — endpoint does not exist
        assert response.status_code in (404, 405)

        # Cleanup
        http_client.delete("/users/me", headers=auth_headers(token))


@pytest.mark.e2e
class TestDataErasure:
    """GDPR Article 17 — right to erasure across related entities."""

    def test_deleted_expert_opinion_removed(self, http_client):
        """When expert deletes account, their opinion disappears from project."""
        # GIVEN — owner and expert in the same project, both with opinions
        owner_email = unique_email("gdpr-owner")
        expert_email = unique_email("gdpr-expert")
        owner_token = register_user(http_client, owner_email)
        expert_token = register_user(http_client, expert_email)

        project = create_project(http_client, owner_token, "GDPR Opinion Test")
        project_id = project["id"]
        invite_and_accept(
            http_client,
            owner_token,
            expert_token,
            expert_email,
            project_id,
        )

        submit_opinion(http_client, owner_token, project_id, 20.0, 50.0, 80.0)
        submit_opinion(http_client, expert_token, project_id, 30.0, 60.0, 90.0)

        opinions_before = http_client.get(
            f"/projects/{project_id}/opinions",
            headers=auth_headers(owner_token),
        )
        assert len(opinions_before.json()) == 2

        # WHEN — expert deletes their account
        delete_resp = http_client.delete(
            "/users/me",
            headers=auth_headers(expert_token),
        )
        assert delete_resp.status_code == 204

        # THEN — only owner's opinion remains
        opinions_after = http_client.get(
            f"/projects/{project_id}/opinions",
            headers=auth_headers(owner_token),
        )
        assert len(opinions_after.json()) == 1

        # Cleanup
        http_client.delete(
            f"/projects/{project_id}",
            headers=auth_headers(owner_token),
        )
        http_client.delete("/users/me", headers=auth_headers(owner_token))

    def test_deleted_expert_removed_from_members(self, http_client):
        """When expert deletes account, they disappear from project members."""
        # GIVEN — owner and expert are both members
        owner_email = unique_email("gdpr-memb-own")
        expert_email = unique_email("gdpr-memb-exp")
        owner_token = register_user(http_client, owner_email)
        expert_token = register_user(http_client, expert_email)

        project = create_project(http_client, owner_token, "GDPR Member Test")
        project_id = project["id"]
        invite_and_accept(
            http_client,
            owner_token,
            expert_token,
            expert_email,
            project_id,
        )

        members_before = http_client.get(
            f"/projects/{project_id}/members",
            headers=auth_headers(owner_token),
        )
        assert len(members_before.json()) == 2

        # WHEN — expert deletes their account
        delete_resp = http_client.delete(
            "/users/me",
            headers=auth_headers(expert_token),
        )
        assert delete_resp.status_code == 204

        # THEN — only owner remains in members
        members_after = http_client.get(
            f"/projects/{project_id}/members",
            headers=auth_headers(owner_token),
        )
        assert len(members_after.json()) == 1

        # Cleanup
        http_client.delete(
            f"/projects/{project_id}",
            headers=auth_headers(owner_token),
        )
        http_client.delete("/users/me", headers=auth_headers(owner_token))

    def test_deleted_invitee_pending_invitation_removed(self, http_client):
        """When invitee deletes account, their pending invitation disappears."""
        # GIVEN — owner sent invitation, invitee has NOT accepted
        owner_email = unique_email("gdpr-inv-own")
        invitee_email = unique_email("gdpr-inv-tgt")
        owner_token = register_user(http_client, owner_email)
        invitee_token = register_user(http_client, invitee_email)

        project = create_project(http_client, owner_token, "GDPR Invite Test")
        project_id = project["id"]

        invite_resp = http_client.post(
            f"/projects/{project_id}/invite",
            json={"email": invitee_email},
            headers=auth_headers(owner_token),
        )
        invite_resp.raise_for_status()

        invitations_before = http_client.get(
            f"/projects/{project_id}/invitations",
            headers=auth_headers(owner_token),
        )
        assert len(invitations_before.json()) == 1

        # WHEN — invitee deletes their account
        delete_resp = http_client.delete(
            "/users/me",
            headers=auth_headers(invitee_token),
        )
        assert delete_resp.status_code == 204

        # THEN — no pending invitations remain
        invitations_after = http_client.get(
            f"/projects/{project_id}/invitations",
            headers=auth_headers(owner_token),
        )
        assert len(invitations_after.json()) == 0

        # Cleanup
        http_client.delete(
            f"/projects/{project_id}",
            headers=auth_headers(owner_token),
        )
        http_client.delete("/users/me", headers=auth_headers(owner_token))

    def test_deleted_user_cannot_login(self, http_client):
        """Deleted user's credentials no longer work for login."""
        # GIVEN — user registered with known credentials
        email = unique_email("gdpr-login")
        token = register_user(http_client, email)

        # WHEN — user deletes account and attempts to login again
        delete_resp = http_client.delete(
            "/users/me",
            headers=auth_headers(token),
        )
        assert delete_resp.status_code == 204

        login_resp = http_client.post(
            "/auth/login",
            data={"username": email, "password": DEFAULT_PASSWORD},
        )

        # THEN — login is rejected
        assert login_resp.status_code == 401


@pytest.mark.e2e
class TestDeletionAudit:
    """Deletion edge cases and graceful handling."""

    def test_deletion_succeeds_without_storage(self, http_client):
        """Account deletion works even when Supabase storage is unavailable.

        In E2E environment, Supabase storage may not be configured.
        The deletion endpoint suppresses StorageDeleteError to ensure
        account removal is not blocked by storage failures.
        """
        # GIVEN — user without a profile photo
        email = unique_email("gdpr-nostorage")
        token = register_user(http_client, email)

        # WHEN — user deletes their account
        delete_resp = http_client.delete(
            "/users/me",
            headers=auth_headers(token),
        )

        # THEN — deletion succeeds
        assert delete_resp.status_code == 204
