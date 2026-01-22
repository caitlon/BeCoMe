"""Tests for invitation management endpoints (email-based)."""

from tests.api.conftest import auth_header, create_project, register_and_login


class TestInviteByEmail:
    """Tests for POST /api/v1/projects/{id}/invite."""

    def test_invite_by_email_success(self, client):
        """Admin can invite a registered user by email."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        register_and_login(client, "invitee@example.com")  # Register invitee
        project = create_project(client, admin_token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "invitee@example.com"},
            headers=auth_header(admin_token),
        )

        # THEN
        assert response.status_code == 201
        data = response.json()
        assert data["invitee_email"] == "invitee@example.com"
        assert data["project_id"] == project["id"]
        assert "id" in data

    def test_invite_user_not_found(self, client):
        """404 returned when invitee email doesn't exist."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        project = create_project(client, admin_token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "nonexistent@example.com"},
            headers=auth_header(admin_token),
        )

        # THEN
        assert response.status_code == 404
        assert "No user found" in response.json()["detail"]

    def test_invite_user_already_member(self, client):
        """409 returned when user is already a member."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        project = create_project(client, admin_token)

        # WHEN - try to invite admin (already a member)
        response = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "admin@example.com"},
            headers=auth_header(admin_token),
        )

        # THEN
        assert response.status_code == 409
        assert "already a member" in response.json()["detail"]

    def test_invite_user_already_invited(self, client):
        """409 returned when user already has pending invitation."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        register_and_login(client, "invitee@example.com")
        project = create_project(client, admin_token)

        # First invitation
        client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "invitee@example.com"},
            headers=auth_header(admin_token),
        )

        # WHEN - try to invite again
        response = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "invitee@example.com"},
            headers=auth_header(admin_token),
        )

        # THEN
        assert response.status_code == 409
        assert "pending invitation" in response.json()["detail"]

    def test_invite_project_not_found(self, client):
        """404 returned for non-existent project."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        fake_id = "00000000-0000-0000-0000-000000000000"

        # WHEN
        response = client.post(
            f"/api/v1/projects/{fake_id}/invite",
            json={"email": "invitee@example.com"},
            headers=auth_header(admin_token),
        )

        # THEN
        assert response.status_code == 404

    def test_invite_not_admin(self, client):
        """403 returned when non-admin tries to invite."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        other_token = register_and_login(client, "other@example.com")
        register_and_login(client, "invitee@example.com")
        project = create_project(client, admin_token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "invitee@example.com"},
            headers=auth_header(other_token),
        )

        # THEN
        assert response.status_code == 403

    def test_invite_without_auth(self, client):
        """401 returned when not authenticated."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        project = create_project(client, admin_token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "invitee@example.com"},
        )

        # THEN
        assert response.status_code == 401


class TestGetUserInvitations:
    """Tests for GET /api/v1/invitations."""

    def test_get_invitations_empty(self, client):
        """Returns empty list when user has no invitations."""
        # GIVEN
        token = register_and_login(client)

        # WHEN
        response = client.get("/api/v1/invitations", headers=auth_header(token))

        # THEN
        assert response.status_code == 200
        assert response.json() == []

    def test_get_invitations_with_pending(self, client):
        """Returns list of pending invitations."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        invitee_token = register_and_login(client, "invitee@example.com")
        project = create_project(client, admin_token, "Test Project")

        # Create invitation
        client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "invitee@example.com"},
            headers=auth_header(admin_token),
        )

        # WHEN
        response = client.get("/api/v1/invitations", headers=auth_header(invitee_token))

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["project_name"] == "Test Project"
        assert data[0]["inviter_first_name"] == "Test"
        assert "id" in data[0]

    def test_get_invitations_without_auth(self, client):
        """401 returned when not authenticated."""
        # WHEN
        response = client.get("/api/v1/invitations")

        # THEN
        assert response.status_code == 401


class TestAcceptInvitation:
    """Tests for POST /api/v1/invitations/{id}/accept."""

    def test_accept_invitation_success(self, client):
        """User joins project as expert when accepting invitation."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        invitee_token = register_and_login(client, "invitee@example.com")
        project = create_project(client, admin_token)

        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "invitee@example.com"},
            headers=auth_header(admin_token),
        )
        invitation_id = invite_resp.json()["id"]

        # WHEN
        response = client.post(
            f"/api/v1/invitations/{invitation_id}/accept",
            headers=auth_header(invitee_token),
        )

        # THEN
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "invitee@example.com"
        assert data["role"] == "expert"

    def test_accept_invitation_user_can_see_project(self, client):
        """User can access project after accepting invitation."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        invitee_token = register_and_login(client, "invitee@example.com")
        project = create_project(client, admin_token)

        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "invitee@example.com"},
            headers=auth_header(admin_token),
        )
        invitation_id = invite_resp.json()["id"]

        # WHEN
        client.post(
            f"/api/v1/invitations/{invitation_id}/accept",
            headers=auth_header(invitee_token),
        )

        # THEN - invitee can now access project
        get_resp = client.get(
            f"/api/v1/projects/{project['id']}",
            headers=auth_header(invitee_token),
        )
        assert get_resp.status_code == 200

    def test_accept_invitation_removes_from_list(self, client):
        """Invitation disappears from list after acceptance."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        invitee_token = register_and_login(client, "invitee@example.com")
        project = create_project(client, admin_token)

        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "invitee@example.com"},
            headers=auth_header(admin_token),
        )
        invitation_id = invite_resp.json()["id"]

        # WHEN
        client.post(
            f"/api/v1/invitations/{invitation_id}/accept",
            headers=auth_header(invitee_token),
        )

        # THEN
        list_resp = client.get("/api/v1/invitations", headers=auth_header(invitee_token))
        assert list_resp.json() == []

    def test_accept_invitation_not_found(self, client):
        """404 returned for non-existent invitation."""
        # GIVEN
        token = register_and_login(client)
        fake_id = "00000000-0000-0000-0000-000000000000"

        # WHEN
        response = client.post(
            f"/api/v1/invitations/{fake_id}/accept",
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 404

    def test_accept_invitation_not_for_user(self, client):
        """404 returned when invitation is for different user."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        register_and_login(client, "invitee@example.com")  # Register invitee
        other_token = register_and_login(client, "other@example.com")
        project = create_project(client, admin_token)

        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "invitee@example.com"},
            headers=auth_header(admin_token),
        )
        invitation_id = invite_resp.json()["id"]

        # WHEN - other user tries to accept
        response = client.post(
            f"/api/v1/invitations/{invitation_id}/accept",
            headers=auth_header(other_token),
        )

        # THEN
        assert response.status_code == 404

    def test_accept_invitation_without_auth(self, client):
        """401 returned when not authenticated."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        register_and_login(client, "invitee@example.com")
        project = create_project(client, admin_token)

        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "invitee@example.com"},
            headers=auth_header(admin_token),
        )
        invitation_id = invite_resp.json()["id"]

        # WHEN
        response = client.post(f"/api/v1/invitations/{invitation_id}/accept")

        # THEN
        assert response.status_code == 401


class TestDeclineInvitation:
    """Tests for POST /api/v1/invitations/{id}/decline."""

    def test_decline_invitation_success(self, client):
        """Invitation is removed when declined."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        invitee_token = register_and_login(client, "invitee@example.com")
        project = create_project(client, admin_token)

        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "invitee@example.com"},
            headers=auth_header(admin_token),
        )
        invitation_id = invite_resp.json()["id"]

        # WHEN
        response = client.post(
            f"/api/v1/invitations/{invitation_id}/decline",
            headers=auth_header(invitee_token),
        )

        # THEN
        assert response.status_code == 204

        # Invitation removed from list
        list_resp = client.get("/api/v1/invitations", headers=auth_header(invitee_token))
        assert list_resp.json() == []

    def test_decline_invitation_not_found(self, client):
        """404 returned for non-existent invitation."""
        # GIVEN
        token = register_and_login(client)
        fake_id = "00000000-0000-0000-0000-000000000000"

        # WHEN
        response = client.post(
            f"/api/v1/invitations/{fake_id}/decline",
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 404

    def test_decline_invitation_not_for_user(self, client):
        """404 returned when invitation is for different user."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        register_and_login(client, "invitee@example.com")  # Register invitee
        other_token = register_and_login(client, "other@example.com")
        project = create_project(client, admin_token)

        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "invitee@example.com"},
            headers=auth_header(admin_token),
        )
        invitation_id = invite_resp.json()["id"]

        # WHEN - other user tries to decline
        response = client.post(
            f"/api/v1/invitations/{invitation_id}/decline",
            headers=auth_header(other_token),
        )

        # THEN
        assert response.status_code == 404


class TestInvitationFlow:
    """Integration tests for complete invitation flow."""

    def test_full_invitation_flow(self, client):
        """Complete flow: invite -> list -> accept -> verify membership."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        expert_token = register_and_login(client, "expert@example.com")
        project = create_project(client, admin_token, "Decision Project")

        # Step 1: Admin invites expert by email
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "expert@example.com"},
            headers=auth_header(admin_token),
        )
        assert invite_resp.status_code == 201
        invitation_id = invite_resp.json()["id"]

        # Step 2: Expert sees invitation in their list
        list_resp = client.get("/api/v1/invitations", headers=auth_header(expert_token))
        assert list_resp.status_code == 200
        invitations = list_resp.json()
        assert len(invitations) == 1
        assert invitations[0]["project_name"] == "Decision Project"

        # Step 3: Expert accepts invitation
        accept_resp = client.post(
            f"/api/v1/invitations/{invitation_id}/accept",
            headers=auth_header(expert_token),
        )
        assert accept_resp.status_code == 201
        assert accept_resp.json()["role"] == "expert"

        # Step 4: Verify expert is now a member
        members_resp = client.get(
            f"/api/v1/projects/{project['id']}/members",
            headers=auth_header(admin_token),
        )
        assert members_resp.status_code == 200
        members = members_resp.json()
        assert len(members) == 2
        emails = [m["email"] for m in members]
        assert "admin@example.com" in emails
        assert "expert@example.com" in emails

        # Step 5: Invitation no longer in list
        list_resp2 = client.get("/api/v1/invitations", headers=auth_header(expert_token))
        assert list_resp2.json() == []

    def test_invite_multiple_experts(self, client):
        """Admin can invite multiple experts to same project."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        expert1_token = register_and_login(client, "expert1@example.com")
        expert2_token = register_and_login(client, "expert2@example.com")
        project = create_project(client, admin_token)

        # Invite both experts
        invite1 = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "expert1@example.com"},
            headers=auth_header(admin_token),
        )
        invite2 = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "expert2@example.com"},
            headers=auth_header(admin_token),
        )
        assert invite1.status_code == 201
        assert invite2.status_code == 201

        # Both accept
        client.post(
            f"/api/v1/invitations/{invite1.json()['id']}/accept",
            headers=auth_header(expert1_token),
        )
        client.post(
            f"/api/v1/invitations/{invite2.json()['id']}/accept",
            headers=auth_header(expert2_token),
        )

        # Project has 3 members
        get_resp = client.get(
            f"/api/v1/projects/{project['id']}",
            headers=auth_header(admin_token),
        )
        assert get_resp.json()["member_count"] == 3
