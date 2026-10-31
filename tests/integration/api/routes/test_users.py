"""Tests for DELETE /api/v1/users/me endpoint."""

import csv
import io
from unittest.mock import patch
from uuid import UUID

from fastapi import status

from api.auth.revocation_store import RevocationStoreError
from api.data.example_project import EXAMPLE_EXPERTS
from api.db.models import MemberRole, Project, ProjectMember, User
from api.middleware.rate_limit import LIMIT_PWD_RESET, limiter
from tests.integration.api.conftest import (
    DEFAULT_TEST_PASSWORD,
    app_session,
    auth_header,
    create_project,
    delete_account,
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


class TestAssistantObjection:
    """The profile switch that keeps a user's opinions from other members' assistant."""

    def test_flag_defaults_to_false_on_both_profile_endpoints(self, client):
        """A fresh account has not objected."""
        # GIVEN
        token = register_and_login(client, "fresh-objection@example.com")

        # WHEN
        users_me = client.get("/api/v1/users/me", headers=auth_header(token))
        auth_me = client.get("/api/v1/auth/me", headers=auth_header(token))

        # THEN
        assert users_me.json()["assistant_objection"] is False
        assert auth_me.json()["assistant_objection"] is False

    def test_put_sets_and_clears_the_flag(self, client):
        """PUT /users/me writes the flag, and the next reads show it, cached or not."""
        # GIVEN: a warm profile cache
        token = register_and_login(client, "toggle-objection@example.com")
        client.get("/api/v1/users/me", headers=auth_header(token))

        # WHEN: set
        put = client.put(
            "/api/v1/users/me", json={"assistant_objection": True}, headers=auth_header(token)
        )

        # THEN
        assert put.status_code == status.HTTP_200_OK
        assert put.json()["assistant_objection"] is True
        assert client.get("/api/v1/users/me", headers=auth_header(token)).json()[
            "assistant_objection"
        ]
        assert client.get("/api/v1/auth/me", headers=auth_header(token)).json()[
            "assistant_objection"
        ]

        # WHEN: cleared
        cleared = client.put(
            "/api/v1/users/me", json={"assistant_objection": False}, headers=auth_header(token)
        )

        # THEN
        assert cleared.json()["assistant_objection"] is False
        assert (
            client.get("/api/v1/users/me", headers=auth_header(token)).json()["assistant_objection"]
            is False
        )

    def test_put_without_the_field_keeps_it(self, client):
        """A name edit does not reset the objection."""
        # GIVEN
        token = register_and_login(client, "keep-objection@example.com")
        client.put(
            "/api/v1/users/me", json={"assistant_objection": True}, headers=auth_header(token)
        )

        # WHEN
        response = client.put(
            "/api/v1/users/me", json={"first_name": "Renamed"}, headers=auth_header(token)
        )

        # THEN
        assert response.json()["assistant_objection"] is True

    def test_put_with_a_null_flag_keeps_it(self, client):
        """An explicit null is not a clear: the objection stays set."""
        # GIVEN
        token = register_and_login(client, "null-objection@example.com")
        client.put(
            "/api/v1/users/me", json={"assistant_objection": True}, headers=auth_header(token)
        )

        # WHEN
        response = client.put(
            "/api/v1/users/me", json={"assistant_objection": None}, headers=auth_header(token)
        )

        # THEN
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["assistant_objection"] is True

    def test_unknown_fields_are_still_rejected(self, client):
        """The request keeps extra=forbid next to the new field."""
        # GIVEN
        token = register_and_login(client, "extra-objection@example.com")

        # WHEN
        response = client.put(
            "/api/v1/users/me",
            json={"assistant_objection": True, "is_demo": True},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestDeleteAccount:
    """Tests for DELETE /api/v1/users/me endpoint."""

    def test_delete_account_returns_204(self, client):
        """Successful account deletion returns 204 No Content."""
        # GIVEN
        token = register_and_login(client, "delete@example.com")

        # WHEN
        response = delete_account(client, token)

        # THEN
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_account_removes_user(self, client):
        """Deleted user cannot access protected endpoints."""
        # GIVEN
        token = register_and_login(client, "removed@example.com")
        delete_account(client, token)

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
        delete_account(client, token)

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
        response = delete_account(client, token)

        # THEN
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_account_survives_blocked_deletion(self, client):
        """A blocked deletion leaves the account usable."""
        # GIVEN
        token = register_and_login(client, "survivor@example.com")
        client.post("/api/v1/projects", json={"name": "Owned"}, headers=auth_header(token))
        delete_account(client, token)

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
        response = delete_account(client, token)

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
        response = delete_account(
            client,
            owner,
            [{"project_id": project_id, "action": "transfer", "new_admin_id": expert_id}],
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
        response = delete_account(
            client, owner, [{"project_id": project["id"], "action": "delete"}]
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
        response = delete_account(client, owner, [{"project_id": project_id, "action": "delete"}])

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
        response = delete_account(client, owner, [{"project_id": second["id"], "action": "delete"}])

        # THEN the deletion is rejected
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["code"] == "account_has_owned_projects"

    def test_transfer_to_non_member_rejected(self, client):
        """A transfer to someone who is not a project member is rejected."""
        # GIVEN an owner of a project with no other members
        owner = register_and_login(client, "solo-owner@example.com")
        project = create_project(client, owner, "Solo")
        stranger = "00000000-0000-0000-0000-000000000000"

        # WHEN the owner tries to transfer to a non-member
        response = delete_account(
            client,
            owner,
            [{"project_id": project["id"], "action": "transfer", "new_admin_id": stranger}],
        )

        # THEN the disposition is rejected as invalid
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["code"] == "invalid_project_disposition"

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
        response = delete_account(
            client,
            owner,
            [
                {
                    "project_id": project["id"],
                    "action": "transfer",
                    "new_admin_id": str(demo_id),
                }
            ],
        )

        # THEN the disposition is rejected as invalid
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["code"] == "invalid_project_disposition"


class TestDeleteAccountRequiresPassword:
    """Erasure needs the current password, checked like a password change."""

    WRONG_PASSWORD = "NotThePassword1!"  # pragma: allowlist secret

    @staticmethod
    def _user_id(client, token):
        """Return the id of the account the token belongs to."""
        return UUID(client.get("/api/v1/auth/me", headers=auth_header(token)).json()["id"])

    def test_wrong_password_is_refused_and_nothing_changes(self, client):
        """A wrong password answers 400 and leaves the account and its projects alone."""
        # GIVEN an owner with a project and a member who could take it over
        owner = register_and_login(client, "pw-owner@example.com")
        project_id = create_project(client, owner, "Kept")["id"]
        _member, member_id = _add_expert(client, owner, project_id, "pw-heir@example.com")
        owner_id = self._user_id(client, owner)

        # WHEN the deletion names a valid transfer but the wrong password
        response = delete_account(
            client,
            owner,
            [{"project_id": project_id, "action": "transfer", "new_admin_id": member_id}],
            password=self.WRONG_PASSWORD,
        )

        # THEN it is refused with the same code the password change uses
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["code"] == "current_password_incorrect"
        # AND the user, their project and the transfer target are unchanged
        with app_session(client) as session:
            assert session.get(User, owner_id) is not None
            assert session.get(User, UUID(member_id)) is not None
            project = session.get(Project, UUID(project_id))
            assert project is not None
            assert project.admin_id == owner_id
        assert client.get("/api/v1/auth/me", headers=auth_header(owner)).status_code == 200

    def test_wrong_password_is_reported_before_a_bad_disposition(self, client):
        """The password is checked first, so a bad disposition cannot be probed without it."""
        # GIVEN an owner of a project with no other members
        owner = register_and_login(client, "pw-first@example.com")
        project = create_project(client, owner, "Solo")
        stranger = "00000000-0000-0000-0000-000000000000"

        # WHEN an invalid transfer is sent together with a wrong password
        response = delete_account(
            client,
            owner,
            [{"project_id": project["id"], "action": "transfer", "new_admin_id": stranger}],
            password=self.WRONG_PASSWORD,
        )

        # THEN the password error wins over the disposition error
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["code"] == "current_password_incorrect"

    def test_wrong_password_is_reported_before_missing_dispositions(self, client):
        """An owned project without a disposition does not show up before the password."""
        # GIVEN an owner of a project
        owner = register_and_login(client, "pw-409@example.com")
        create_project(client, owner, "Owned")

        # WHEN no disposition is sent and the password is wrong
        response = delete_account(client, owner, password=self.WRONG_PASSWORD)

        # THEN the password error is reported
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["code"] == "current_password_incorrect"

    def test_missing_body_returns_422_and_keeps_the_account(self, client):
        """A request with no body is a validation error, not a deletion."""
        # GIVEN
        token = register_and_login(client, "pw-nobody@example.com")

        # WHEN
        response = client.delete("/api/v1/users/me", headers=auth_header(token))

        # THEN
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert client.get("/api/v1/auth/me", headers=auth_header(token)).status_code == 200

    def test_missing_password_field_returns_422_and_keeps_the_account(self, client):
        """A body without current_password is a validation error, not a deletion."""
        # GIVEN
        token = register_and_login(client, "pw-nofield@example.com")

        # WHEN
        response = client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"project_dispositions": []},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert client.get("/api/v1/auth/me", headers=auth_header(token)).status_code == 200

    def test_empty_password_returns_422(self, client):
        """An empty password is rejected by validation, as on the password change."""
        # GIVEN
        token = register_and_login(client, "pw-empty@example.com")

        # WHEN
        response = delete_account(client, token, password="")

        # THEN
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_correct_password_deletes_the_account(self, client):
        """The right password erases the account."""
        # GIVEN
        token = register_and_login(client, "pw-right@example.com")
        user_id = self._user_id(client, token)

        # WHEN
        response = delete_account(client, token)

        # THEN
        assert response.status_code == status.HTTP_204_NO_CONTENT
        with app_session(client) as session:
            assert session.get(User, user_id) is None

    def test_correct_password_with_dispositions_deletes_the_account(self, client):
        """The right password with a transfer erases the account and moves the project."""
        # GIVEN
        owner = register_and_login(client, "pw-right-owner@example.com")
        project_id = create_project(client, owner, "Handed")["id"]
        _member, member_id = _add_expert(client, owner, project_id, "pw-right-heir@example.com")

        # WHEN
        response = delete_account(
            client,
            owner,
            [{"project_id": project_id, "action": "transfer", "new_admin_id": member_id}],
        )

        # THEN
        assert response.status_code == status.HTTP_204_NO_CONTENT
        with app_session(client) as session:
            project = session.get(Project, UUID(project_id))
            assert project is not None
            assert str(project.admin_id) == member_id

    def test_route_is_limited_like_a_password_change(self, client):
        """With the limiter on, the fourth attempt in a minute is refused with 429."""
        # GIVEN the limiter switched on and the password-change limit
        assert LIMIT_PWD_RESET == "3/minute"
        allowed = int(LIMIT_PWD_RESET.split("/")[0])
        token = register_and_login(client, "pw-limited@example.com")

        # WHEN one address guesses wrong as often as the limit allows, and once more
        with patch.object(limiter, "enabled", True):
            limiter.reset()
            try:
                statuses = [
                    delete_account(client, token, password=self.WRONG_PASSWORD).status_code
                    for _ in range(allowed + 1)
                ]
            finally:
                limiter.reset()

        # THEN the first attempts were answered and the last was limited
        assert statuses == [status.HTTP_400_BAD_REQUEST] * allowed + [
            status.HTTP_429_TOO_MANY_REQUESTS
        ]


class TestDeleteAccountRecalculatesResults:
    """Erasure drops the user's opinions elsewhere, so those results are recalculated."""

    @staticmethod
    def _submit(client, token, project_id, lower, peak, upper):
        """Save an opinion in the project for the token's user."""
        response = client.post(
            f"/api/v1/projects/{project_id}/opinions",
            json={"position": "Expert", "lower_bound": lower, "peak": peak, "upper_bound": upper},
            headers=auth_header(token),
        )
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

    def test_result_no_longer_counts_the_deleted_member(self, client):
        """A project that keeps other opinions ends with a result computed without the user."""
        # GIVEN a project where the owner and a member both gave an opinion
        owner = register_and_login(client, "recalc-owner@example.com")
        project_id = create_project(client, owner, "Recalc")["id"]
        member, _ = _add_expert(client, owner, project_id, "recalc-member@example.com")
        self._submit(client, owner, project_id, 10.0, 20.0, 30.0)
        self._submit(client, member, project_id, 70.0, 80.0, 90.0)
        before = client.get(f"/api/v1/projects/{project_id}/result", headers=auth_header(owner))
        assert before.json()["num_experts"] == 2

        # WHEN the member deletes their account
        response = delete_account(client, member)

        # THEN the result counts only the owner's opinion
        assert response.status_code == status.HTTP_204_NO_CONTENT
        after = client.get(
            f"/api/v1/projects/{project_id}/result", headers=auth_header(owner)
        ).json()
        assert after["num_experts"] == 1
        assert after["arithmetic_mean"]["peak"] == 20.0
        assert after["best_compromise"]["peak"] == 20.0

    def test_csv_export_uses_the_recalculated_result(self, client):
        """The export reads the stored result, so it shows the values without the user."""
        # GIVEN a project where the owner and a member both gave an opinion
        owner = register_and_login(client, "csv-owner@example.com")
        project_id = create_project(client, owner, "Csv Recalc")["id"]
        member, _ = _add_expert(client, owner, project_id, "csv-member@example.com")
        self._submit(client, owner, project_id, 10.0, 20.0, 30.0)
        self._submit(client, member, project_id, 70.0, 80.0, 90.0)

        # WHEN the member deletes their account and the owner exports the result
        delete_account(client, member)
        response = client.get(
            f"/api/v1/projects/{project_id}/result/export?format=csv",
            headers=auth_header(owner),
        )

        # THEN the exported summary counts only the owner's opinion
        assert response.status_code == status.HTTP_200_OK
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        summary = {row[0]: row for row in rows if row}
        assert summary["Experts"][1] == "1"
        assert float(summary["Best Compromise (\u0393\u03a9Mean)"][2]) == 20.0

    def test_result_is_removed_when_the_only_opinion_goes(self, client):
        """A project whose only opinion belonged to the user ends with no result."""
        # GIVEN a project where only the member gave an opinion
        owner = register_and_login(client, "solo-owner@example.com")
        project_id = create_project(client, owner, "Solo")["id"]
        member, _ = _add_expert(client, owner, project_id, "solo-member@example.com")
        self._submit(client, member, project_id, 40.0, 50.0, 60.0)

        # WHEN the member deletes their account
        response = delete_account(client, member)

        # THEN the project has no result left
        assert response.status_code == status.HTTP_204_NO_CONTENT
        after = client.get(f"/api/v1/projects/{project_id}/result", headers=auth_header(owner))
        assert after.status_code == status.HTTP_200_OK
        assert after.json() is None


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


class TestChangePasswordWithWrongCurrentPassword:
    """A mistyped current password is a 400 the session survives, never a 401."""

    def test_wrong_current_password_is_a_400_with_a_code(self, client):
        """The refusal is a 400 with its own code and no bearer challenge."""
        # GIVEN a logged-in user
        token = register_and_login(client, "wrongcurrent@example.com")

        # WHEN the current password is mistyped
        resp = client.put(
            "/api/v1/users/me/password",
            headers=auth_header(token),
            json={
                "current_password": "NotThePassword1!",  # pragma: allowlist secret
                "new_password": "NewSecurePass456!",
            },
        )

        # THEN it is a 400 the SPA can tell apart, with no WWW-Authenticate challenge
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json() == {
            "detail": "Current password is incorrect",
            "code": "current_password_incorrect",
        }
        assert "www-authenticate" not in resp.headers

    def test_session_and_password_survive_a_wrong_current_password(self, client):
        """The refusal revokes nothing and changes nothing."""
        # GIVEN a logged-in user who mistypes the current password
        token = register_and_login(client, "keepsession@example.com")
        client.put(
            "/api/v1/users/me/password",
            headers=auth_header(token),
            json={
                "current_password": "NotThePassword1!",  # pragma: allowlist secret
                "new_password": "NewSecurePass456!",
            },
        )

        # WHEN the same token is used again
        me = client.get("/api/v1/users/me", headers=auth_header(token))

        # THEN the session still works and the old password still signs in
        assert me.status_code == status.HTTP_200_OK
        login = client.post(
            "/api/v1/auth/login",
            data={"username": "keepsession@example.com", "password": DEFAULT_TEST_PASSWORD},
        )
        assert login.status_code == status.HTTP_200_OK
