"""Tests for DELETE /api/v1/users/me endpoint."""

from unittest.mock import patch
from uuid import UUID

from fastapi import status

from api.auth.revocation_store import RevocationStoreError
from api.data.example_project import EXAMPLE_EXPERTS
from api.db.models import MemberRole, ProjectMember
from tests.integration.api.conftest import (
    DEFAULT_TEST_PASSWORD,
    app_session,
    auth_header,
    create_project,
    register_and_login,
)
from tests.shared.helpers import insert_demo_experts


def _add_expert(client, owner_token, project_id, email):
    """Invite an expert into the project, accept, and return (token, user_id)."""
    expert_token = register_and_login(client, email)
    client.post(
        f"/api/v1/projects/{project_id}/invite",
        json={"email": email},
        headers=auth_header(owner_token),
    )
    invitations = client.get("/api/v1/invitations", headers=auth_header(expert_token)).json()
    accept = client.post(
        f"/api/v1/invitations/{invitations[0]['id']}/accept",
        headers=auth_header(expert_token),
    )
    return expert_token, accept.json()["user_id"]


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

        # WHEN: try to login with same credentials
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


class TestDeleteAccountDispositions:
    """Guided erasure: each owned project is transferred or deleted (GDPR Art. 17)."""

    def test_transfer_owned_project_then_delete_account(self, client):
        """Owner transfers a project to a member, then the account is erased."""
        # GIVEN an owner, a member, and an owned project
        owner = register_and_login(client, "leaving-owner@example.com")
        project = create_project(client, owner, "Handover")
        project_id = project["id"]
        expert_token, expert_id = _add_expert(client, owner, project_id, "heir@example.com")

        # WHEN the owner deletes their account, transferring the project to the member
        response = client.request(
            "DELETE",
            "/api/v1/users/me",
            json={
                "project_dispositions": [
                    {"project_id": project_id, "action": "transfer", "new_admin_id": expert_id}
                ]
            },
            headers=auth_header(owner),
        )

        # THEN the account is gone but the project survives under the new admin
        assert response.status_code == status.HTTP_204_NO_CONTENT
        fetched = client.get(f"/api/v1/projects/{project_id}", headers=auth_header(expert_token))
        assert fetched.status_code == status.HTTP_200_OK
        assert fetched.json()["admin_id"] == expert_id

    def test_delete_owned_project_then_delete_account(self, client):
        """Owner deletes their project as part of erasing the account."""
        # GIVEN an owner with an owned project
        owner = register_and_login(client, "purging-owner@example.com")
        project = create_project(client, owner, "Doomed")

        # WHEN the owner deletes their account, deleting the project too
        response = client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"project_dispositions": [{"project_id": project["id"], "action": "delete"}]},
            headers=auth_header(owner),
        )

        # THEN the account is erased
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_deleting_project_cascades_opinions(self, client_with_session):
        """Deleting an owned project during erasure removes its opinions (no orphans)."""
        from sqlmodel import select

        from api.db.models import ExpertOpinion

        client, session = client_with_session
        # GIVEN an owned project carrying an opinion
        owner = register_and_login(client, "cascade-owner@example.com")
        project = create_project(client, owner, "WithOpinion")
        project_id = project["id"]
        client.post(
            f"/api/v1/projects/{project_id}/opinions",
            json={"position": "Expert", "lower_bound": 40.0, "peak": 60.0, "upper_bound": 80.0},
            headers=auth_header(owner),
        )

        # WHEN the account is erased, deleting the project
        response = client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"project_dispositions": [{"project_id": project_id, "action": "delete"}]},
            headers=auth_header(owner),
        )

        # THEN no opinions are left orphaned
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert session.exec(select(ExpertOpinion)).all() == []

    def test_partial_dispositions_returns_409(self, client):
        """An owned project left without a disposition blocks the deletion."""
        # GIVEN an owner of two projects
        owner = register_and_login(client, "two-projects@example.com")
        create_project(client, owner, "First")
        second = create_project(client, owner, "Second")

        # WHEN only one project is given a disposition
        response = client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"project_dispositions": [{"project_id": second["id"], "action": "delete"}]},
            headers=auth_header(owner),
        )

        # THEN the deletion is rejected
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_transfer_to_non_member_rejected(self, client):
        """A transfer to someone who is not a project member is rejected."""
        # GIVEN an owner of a project with no other members
        owner = register_and_login(client, "solo-owner@example.com")
        project = create_project(client, owner, "Solo")
        stranger = "00000000-0000-0000-0000-000000000000"

        # WHEN the owner tries to transfer to a non-member
        response = client.request(
            "DELETE",
            "/api/v1/users/me",
            json={
                "project_dispositions": [
                    {"project_id": project["id"], "action": "transfer", "new_admin_id": stranger}
                ]
            },
            headers=auth_header(owner),
        )

        # THEN the disposition is rejected as invalid
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_transfer_to_demo_account_rejected(self, client):
        """A transfer naming a demo account as the erasure disposition is rejected.

        Membership alone would accept it, since a demo account seeded into an example
        project is an ordinary ProjectMember row, so this covers the case
        test_transfer_to_non_member_rejected above does not: the target really is a
        member, and is refused anyway because it can never log in to hold the project.
        """
        # GIVEN an owner whose project has a demo account as an ordinary member
        owner = register_and_login(client, "demo-transfer-owner@example.com")
        project = create_project(client, owner, "Solo")
        demo_id = EXAMPLE_EXPERTS[0].user_id
        with app_session(client) as session:
            insert_demo_experts(session)
            session.add(
                ProjectMember(
                    project_id=UUID(project["id"]),
                    user_id=demo_id,
                    role=MemberRole.EXPERT,
                )
            )
            session.commit()

        # WHEN the owner tries to transfer their project to the demo account
        response = client.request(
            "DELETE",
            "/api/v1/users/me",
            json={
                "project_dispositions": [
                    {
                        "project_id": project["id"],
                        "action": "transfer",
                        "new_admin_id": str(demo_id),
                    }
                ]
            },
            headers=auth_header(owner),
        )

        # THEN the disposition is rejected as invalid
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestChangePasswordRevokesSessions:
    """Changing the password invalidates tokens issued earlier (M1)."""

    def test_change_password_revokes_existing_tokens(self, client):
        """After a password change, a previously issued access token is rejected."""
        # GIVEN a logged-in user whose token works
        token = register_and_login(client, "changepw@example.com")
        assert client.get("/api/v1/auth/me", headers=auth_header(token)).status_code == 200

        # WHEN the password is changed
        resp = client.put(
            "/api/v1/users/me/password",
            headers=auth_header(token),
            json={"current_password": DEFAULT_TEST_PASSWORD, "new_password": "NewSecurePass456!"},
        )
        assert resp.status_code == 204

        # THEN the old token no longer works
        assert client.get("/api/v1/auth/me", headers=auth_header(token)).status_code == 401

    def test_store_fault_leaves_the_old_password_in_place(self, client):
        """When the session cutoff cannot be written, the password is not changed either.

        Otherwise the caller sees a failure while the new password is already live and
        every session issued before it stays valid.
        """
        # GIVEN a logged-in user and a revocation store that cannot record the cutoff
        token = register_and_login(client, "storefault@example.com")

        # WHEN the password change runs into the store fault
        with patch(
            "api.auth.revocation_store.InMemoryRevocationStore.set_user_valid_after",
            side_effect=RevocationStoreError("store is down"),
        ):
            resp = client.put(
                "/api/v1/users/me/password",
                headers=auth_header(token),
                json={
                    "current_password": DEFAULT_TEST_PASSWORD,
                    "new_password": "NewSecurePass456!",
                },
            )

        # THEN the request fails and the original password still authenticates
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        login = client.post(
            "/api/v1/auth/login",
            data={"username": "storefault@example.com", "password": DEFAULT_TEST_PASSWORD},
        )
        assert login.status_code == status.HTTP_200_OK
