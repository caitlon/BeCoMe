"""E2E tests for invitation lifecycle."""

import pytest

from tests.e2e.conftest import (
    auth_headers,
    create_project,
    register_user,
    unique_email,
)


@pytest.mark.e2e
class TestInvitationAccept:
    """Full invitation flow: invite, accept, and join a project."""

    def test_owner_invites_expert_who_accepts_and_joins(self, http_client):
        """Invited expert accepts and becomes a project member."""
        # GIVEN — owner creates project, expert is registered
        owner_email = unique_email("owner")
        expert_email = unique_email("expert")
        owner_token = register_user(http_client, owner_email)
        expert_token = register_user(http_client, expert_email)
        project = create_project(http_client, owner_token)

        # WHEN — owner sends invitation
        invite_resp = http_client.post(
            f"/projects/{project['id']}/invite",
            json={"email": expert_email},
            headers=auth_headers(owner_token),
        )
        assert invite_resp.status_code == 201

        # Expert accepts the invitation
        invitations = http_client.get("/invitations", headers=auth_headers(expert_token)).json()
        assert len(invitations) == 1
        invitation_id = invitations[0]["id"]

        accept_resp = http_client.post(
            f"/invitations/{invitation_id}/accept",
            headers=auth_headers(expert_token),
        )
        assert accept_resp.status_code == 201

        # THEN — expert can access the project
        project_resp = http_client.get(
            f"/projects/{project['id']}",
            headers=auth_headers(expert_token),
        )
        assert project_resp.status_code == 200


@pytest.mark.e2e
class TestInvitationErrors:
    """Edge cases and error scenarios for invitations."""

    def test_invitation_to_nonexistent_user_returns_404(self, http_client):
        """Inviting an email not in the system returns 404."""
        # GIVEN — owner with a project
        owner_email = unique_email("owner")
        owner_token = register_user(http_client, owner_email)
        project = create_project(http_client, owner_token)

        # WHEN — invite a nonexistent email
        response = http_client.post(
            f"/projects/{project['id']}/invite",
            json={"email": unique_email("ghost")},
            headers=auth_headers(owner_token),
        )

        # THEN
        assert response.status_code == 404

    def test_invitation_to_existing_member_returns_409(self, http_client):
        """Inviting someone who is already a member returns 409."""
        # GIVEN — expert is already a project member
        owner_email = unique_email("owner")
        expert_email = unique_email("expert")
        owner_token = register_user(http_client, owner_email)
        expert_token = register_user(http_client, expert_email)
        project = create_project(http_client, owner_token)

        # Invite and accept
        http_client.post(
            f"/projects/{project['id']}/invite",
            json={"email": expert_email},
            headers=auth_headers(owner_token),
        )
        invitations = http_client.get("/invitations", headers=auth_headers(expert_token)).json()
        http_client.post(
            f"/invitations/{invitations[0]['id']}/accept",
            headers=auth_headers(expert_token),
        )

        # WHEN — owner tries to invite the same expert again
        response = http_client.post(
            f"/projects/{project['id']}/invite",
            json={"email": expert_email},
            headers=auth_headers(owner_token),
        )

        # THEN
        assert response.status_code == 409


@pytest.mark.e2e
class TestInvitationDecline:
    """Expert can decline an invitation."""

    def test_expert_can_decline_invitation(self, http_client):
        """Declining removes the invitation; expert stays outside the project."""
        # GIVEN — pending invitation
        owner_email = unique_email("owner")
        expert_email = unique_email("expert")
        owner_token = register_user(http_client, owner_email)
        expert_token = register_user(http_client, expert_email)
        project = create_project(http_client, owner_token)

        http_client.post(
            f"/projects/{project['id']}/invite",
            json={"email": expert_email},
            headers=auth_headers(owner_token),
        )
        invitations = http_client.get("/invitations", headers=auth_headers(expert_token)).json()
        invitation_id = invitations[0]["id"]

        # WHEN — expert declines
        decline_resp = http_client.post(
            f"/invitations/{invitation_id}/decline",
            headers=auth_headers(expert_token),
        )
        assert decline_resp.status_code == 204

        # THEN — no pending invitations left
        remaining = http_client.get("/invitations", headers=auth_headers(expert_token)).json()
        assert len(remaining) == 0

        # AND — expert cannot access the project
        project_resp = http_client.get(
            f"/projects/{project['id']}",
            headers=auth_headers(expert_token),
        )
        assert project_resp.status_code == 403
