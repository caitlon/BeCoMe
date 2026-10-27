"""Tests for project management endpoints."""

from unittest.mock import patch
from uuid import UUID

import pytest

from api.data.example_project import EXAMPLE_EXPERTS
from api.db.models import MemberRole, Project, ProjectMember
from api.services.calculation_service import CalculationService
from api.services.project_membership_service import ProjectMembershipService
from tests.integration.api.conftest import (
    app_session,
    auth_header,
    create_project,
    register_and_login,
    submit_opinion,
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


class TestCreateProject:
    """Tests for POST /api/v1/projects."""

    def test_create_project_success(self, client):
        """Project is created successfully."""
        # GIVEN
        token = register_and_login(client)

        # WHEN
        response = client.post(
            "/api/v1/projects",
            json={"name": "My Project", "description": "Test description"},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Project"
        assert data["description"] == "Test description"
        assert data["scale_min"] == 0.0
        assert data["scale_max"] == 100.0
        assert data["member_count"] == 1

    def test_create_project_with_custom_scale(self, client):
        """Project is created with custom scale values."""
        # GIVEN
        token = register_and_login(client)

        # WHEN
        response = client.post(
            "/api/v1/projects",
            json={
                "name": "Custom Scale Project",
                "scale_min": 1,
                "scale_max": 10,
                "scale_unit": "points",
            },
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 201
        data = response.json()
        assert data["scale_min"] == 1.0
        assert data["scale_max"] == 10.0
        assert data["scale_unit"] == "points"

    def test_create_project_invalid_scale(self, client):
        """Project creation fails with invalid scale range."""
        # GIVEN
        token = register_and_login(client)

        # WHEN
        response = client.post(
            "/api/v1/projects",
            json={"name": "Bad Scale", "scale_min": 100, "scale_max": 50},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 422

    def test_create_project_equal_scale_fails(self, client):
        """Project creation fails when scale_min equals scale_max."""
        # GIVEN
        token = register_and_login(client)

        # WHEN
        response = client.post(
            "/api/v1/projects",
            json={"name": "Equal Scale", "scale_min": 50, "scale_max": 50},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 422

    @pytest.mark.parametrize("field", ["scale_min", "scale_max"])
    @pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
    def test_create_project_non_finite_scale_fails(self, client, field, literal):
        """Project creation fails when a scale bound is NaN or infinite on the wire."""
        # GIVEN
        token = register_and_login(client)
        bounds = {"scale_min": "0", "scale_max": "100", field: literal}
        body = (
            f'{{"name": "Non-finite", "scale_min": {bounds["scale_min"]}, '
            f'"scale_max": {bounds["scale_max"]}}}'
        )

        # WHEN
        response = client.post(
            "/api/v1/projects",
            content=body,
            headers={**auth_header(token), "Content-Type": "application/json"},
        )

        # THEN
        assert response.status_code == 422
        assert any(
            error["type"] == "finite_number" and error["loc"][-1] == field
            for error in response.json()["detail"]
        )

    def test_create_project_without_auth(self, client):
        """Project creation fails without authentication."""
        # WHEN
        response = client.post(
            "/api/v1/projects",
            json={"name": "Unauthorized Project"},
        )

        # THEN
        assert response.status_code == 401


class TestListProjects:
    """Tests for GET /api/v1/projects."""

    def test_list_projects_empty(self, client):
        """Empty list returned when user has no projects."""
        # GIVEN
        token = register_and_login(client)

        # WHEN
        response = client.get("/api/v1/projects", headers=auth_header(token))

        # THEN
        assert response.status_code == 200
        assert response.json() == []

    def test_list_projects_with_projects(self, client):
        """User's projects are returned."""
        # GIVEN
        token = register_and_login(client)
        client.post(
            "/api/v1/projects",
            json={"name": "Project 1"},
            headers=auth_header(token),
        )
        client.post(
            "/api/v1/projects",
            json={"name": "Project 2"},
            headers=auth_header(token),
        )

        # WHEN
        response = client.get("/api/v1/projects", headers=auth_header(token))

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = [p["name"] for p in data]
        assert "Project 1" in names
        assert "Project 2" in names

    def test_list_projects_only_own(self, client):
        """User only sees projects they are member of."""
        # GIVEN
        token1 = register_and_login(client, "user1@example.com")
        token2 = register_and_login(client, "user2@example.com")

        client.post(
            "/api/v1/projects",
            json={"name": "User1 Project"},
            headers=auth_header(token1),
        )
        client.post(
            "/api/v1/projects",
            json={"name": "User2 Project"},
            headers=auth_header(token2),
        )

        # WHEN
        response = client.get("/api/v1/projects", headers=auth_header(token1))

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "User1 Project"


class TestGetProject:
    """Tests for GET /api/v1/projects/{id}."""

    def test_get_project_success(self, client):
        """Project details are returned for member."""
        # GIVEN
        token = register_and_login(client)
        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test Project"},
            headers=auth_header(token),
        )
        project_id = create_resp.json()["id"]

        # WHEN
        response = client.get(f"/api/v1/projects/{project_id}", headers=auth_header(token))

        # THEN
        assert response.status_code == 200
        assert response.json()["name"] == "Test Project"

    def test_get_project_not_found(self, client):
        """404 returned for non-existent project."""
        # GIVEN
        token = register_and_login(client)
        fake_id = "00000000-0000-0000-0000-000000000000"

        # WHEN
        response = client.get(f"/api/v1/projects/{fake_id}", headers=auth_header(token))

        # THEN
        assert response.status_code == 404

    def test_get_project_not_member(self, client):
        """404 returned when the caller is not a member (existence hidden)."""
        # GIVEN
        token1 = register_and_login(client, "owner@example.com")
        token2 = register_and_login(client, "other@example.com")

        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Private Project"},
            headers=auth_header(token1),
        )
        project_id = create_resp.json()["id"]

        # WHEN
        response = client.get(f"/api/v1/projects/{project_id}", headers=auth_header(token2))

        # THEN
        assert response.status_code == 404

    def test_get_project_role_not_found(self, client):
        """404 returned when role lookup fails (race condition edge case)."""
        # GIVEN
        token = register_and_login(client)
        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test Project"},
            headers=auth_header(token),
        )
        project_id = create_resp.json()["id"]

        # WHEN: mock get_user_role_in_project to return None (simulates race condition)
        with patch.object(ProjectMembershipService, "get_user_role_in_project", return_value=None):
            response = client.get(f"/api/v1/projects/{project_id}", headers=auth_header(token))

        # THEN
        assert response.status_code == 404
        assert response.json()["detail"] == "Membership not found for this project."


class TestUpdateProject:
    """Tests for PATCH /api/v1/projects/{id}."""

    def test_update_project_success(self, client):
        """Admin can update project."""
        # GIVEN
        token = register_and_login(client)
        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Original Name"},
            headers=auth_header(token),
        )
        project_id = create_resp.json()["id"]

        # WHEN
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Updated Name", "description": "New description"},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "New description"

    def test_update_project_partial(self, client):
        """Partial update only changes specified fields."""
        # GIVEN
        token = register_and_login(client)
        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test", "description": "Original"},
            headers=auth_header(token),
        )
        project_id = create_resp.json()["id"]

        # WHEN
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"description": "Updated"},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test"
        assert data["description"] == "Updated"

    def test_update_project_not_member(self, client):
        """A non-member cannot update a project and gets a 404 (existence hidden)."""
        # GIVEN
        token1 = register_and_login(client, "owner@example.com")
        token2 = register_and_login(client, "other@example.com")

        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test"},
            headers=auth_header(token1),
        )
        project_id = create_resp.json()["id"]

        # WHEN
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Hacked"},
            headers=auth_header(token2),
        )

        # THEN
        assert response.status_code == 404

    def test_update_project_invalid_scale(self, client):
        """Update fails if scale range becomes invalid."""
        # GIVEN
        token = register_and_login(client)
        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test", "scale_min": 0, "scale_max": 100},
            headers=auth_header(token),
        )
        project_id = create_resp.json()["id"]

        # WHEN
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"scale_min": 200},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 422

    @pytest.mark.parametrize("field", ["scale_min", "scale_max"])
    @pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
    def test_update_project_non_finite_scale_fails(self, client, field, literal):
        """Update fails when a scale bound is NaN or infinite on the wire."""
        # GIVEN
        token = register_and_login(client)
        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test", "scale_min": 0, "scale_max": 100},
            headers=auth_header(token),
        )
        project_id = create_resp.json()["id"]

        # WHEN
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            content=f'{{"{field}": {literal}}}',
            headers={**auth_header(token), "Content-Type": "application/json"},
        )

        # THEN
        assert response.status_code == 422
        assert any(
            error["type"] == "finite_number" and error["loc"][-1] == field
            for error in response.json()["detail"]
        )

    @pytest.mark.parametrize("field", ["name", "scale_min", "scale_max", "scale_unit"])
    def test_update_project_rejects_explicit_null(self, client, field):
        """An explicit null for a non-nullable column is refused, not crashed on.

        `description` is the only project field the column allows to be null, so every
        other one sent as null is a client error. Before this was handled the request
        reached the database and came back as an unhandled 500.
        """
        # GIVEN
        token = register_and_login(client)
        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test", "scale_min": 0, "scale_max": 100},
            headers=auth_header(token),
        )
        project_id = create_resp.json()["id"]

        # WHEN
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={field: None},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 422

    def test_update_project_accepts_null_description(self, client):
        """`description` is nullable, so clearing it is a normal update."""
        # GIVEN
        token = register_and_login(client)
        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test", "description": "written", "scale_min": 0, "scale_max": 100},
            headers=auth_header(token),
        )
        project_id = create_resp.json()["id"]

        # WHEN
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"description": None},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 200
        assert response.json()["description"] is None

    def test_update_project_equal_scale_fails(self, client):
        """Update fails when scale_min equals scale_max."""
        # GIVEN
        token = register_and_login(client)
        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test", "scale_min": 0, "scale_max": 100},
            headers=auth_header(token),
        )
        project_id = create_resp.json()["id"]

        # WHEN: update scale_max to equal scale_min
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"scale_max": 0},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 422


class TestDeleteProject:
    """Tests for DELETE /api/v1/projects/{id}."""

    def test_delete_project_success(self, client):
        """Admin can delete project."""
        # GIVEN
        token = register_and_login(client)
        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "To Delete"},
            headers=auth_header(token),
        )
        project_id = create_resp.json()["id"]

        # WHEN
        response = client.delete(f"/api/v1/projects/{project_id}", headers=auth_header(token))

        # THEN
        assert response.status_code == 204

        # Verify deleted
        get_resp = client.get(f"/api/v1/projects/{project_id}", headers=auth_header(token))
        assert get_resp.status_code == 404

    def test_delete_project_not_member(self, client):
        """A non-member cannot delete a project and gets a 404 (existence hidden)."""
        # GIVEN
        token1 = register_and_login(client, "owner@example.com")
        token2 = register_and_login(client, "other@example.com")

        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test"},
            headers=auth_header(token1),
        )
        project_id = create_resp.json()["id"]

        # WHEN
        response = client.delete(f"/api/v1/projects/{project_id}", headers=auth_header(token2))

        # THEN
        assert response.status_code == 404


class TestListMembers:
    """Tests for GET /api/v1/projects/{id}/members."""

    def test_list_members_success(self, client):
        """Members list includes creator as admin."""
        # GIVEN
        token = register_and_login(client)
        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test"},
            headers=auth_header(token),
        )
        project_id = create_resp.json()["id"]

        # WHEN
        response = client.get(f"/api/v1/projects/{project_id}/members", headers=auth_header(token))

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["email"] == "test@example.com"
        assert data[0]["role"] == "admin"

    def test_list_members_not_member(self, client):
        """Non-member cannot see members list (404, existence hidden)."""
        # GIVEN
        token1 = register_and_login(client, "owner@example.com")
        token2 = register_and_login(client, "other@example.com")

        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test"},
            headers=auth_header(token1),
        )
        project_id = create_resp.json()["id"]

        # WHEN
        response = client.get(
            f"/api/v1/projects/{project_id}/members",
            headers=auth_header(token2),
        )

        # THEN
        assert response.status_code == 404

    def test_list_members_respects_pagination(self, client):
        """limit/offset bound the members page; the default returns every member."""
        # GIVEN a project with two members (admin + expert)
        owner = register_and_login(client, "owner@example.com")
        project = create_project(client, owner)
        _add_expert(client, owner, project["id"], "expert@example.com")

        # THEN the default returns both, while limit/offset page through them
        everyone = client.get(
            f"/api/v1/projects/{project['id']}/members", headers=auth_header(owner)
        )
        assert len(everyone.json()) == 2

        first = client.get(
            f"/api/v1/projects/{project['id']}/members?limit=1", headers=auth_header(owner)
        )
        assert len(first.json()) == 1

        second = client.get(
            f"/api/v1/projects/{project['id']}/members?limit=1&offset=1",
            headers=auth_header(owner),
        )
        assert len(second.json()) == 1
        assert first.json()[0]["user_id"] != second.json()[0]["user_id"]

    @staticmethod
    def _emails_by_user(client, token, project_id):
        response = client.get(f"/api/v1/projects/{project_id}/members", headers=auth_header(token))
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 2
        assert all("email" in row for row in rows)
        return {row["user_id"]: row["email"] for row in rows}

    def test_list_members_admin_sees_every_email(self, client):
        """The project admin gets the address of every member."""
        # GIVEN
        owner = register_and_login(client, "owner@example.com")
        project = create_project(client, owner)
        _expert, expert_id = _add_expert(client, owner, project["id"], "expert@example.com")

        # WHEN
        emails = self._emails_by_user(client, owner, project["id"])

        # THEN
        assert sorted(emails.values()) == ["expert@example.com", "owner@example.com"]
        assert expert_id in emails

    def test_list_members_expert_sees_only_their_own_email(self, client):
        """An expert gets null for the other members and their own address on their row."""
        # GIVEN
        owner = register_and_login(client, "owner@example.com")
        project = create_project(client, owner)
        expert, expert_id = _add_expert(client, owner, project["id"], "expert@example.com")

        # WHEN
        emails = self._emails_by_user(client, expert, project["id"])

        # THEN
        assert emails.pop(expert_id) == "expert@example.com"
        assert list(emails.values()) == [None]


class TestRemoveMember:
    """Tests for DELETE /api/v1/projects/{id}/members/{user_id}."""

    def test_removal_discards_the_opinion_and_recalculates(self, client):
        """Removing a member drops their opinion and the result stops counting them.

        The opinion carries the ex-member's email, name, and position, it is served
        to every remaining member and embedded in exports, and after removal the
        person concerned can no longer delete it themselves (the project 404s for them).
        """
        # GIVEN a project where both the admin and an expert submitted an opinion
        owner = register_and_login(client, "owner@example.com")
        project = create_project(client, owner)
        submit_opinion(client, owner, project["id"], 30.0, 50.0, 70.0)
        expert, expert_id = _add_expert(client, owner, project["id"], "expert@example.com")
        submit_opinion(client, expert, project["id"], 10.0, 20.0, 30.0)

        before = client.get(
            f"/api/v1/projects/{project['id']}/result", headers=auth_header(owner)
        ).json()
        assert before["num_experts"] == 2

        # WHEN the admin removes the expert
        response = client.delete(
            f"/api/v1/projects/{project['id']}/members/{expert_id}",
            headers=auth_header(owner),
        )

        # THEN the opinion is gone from the listing and from the recalculated result
        assert response.status_code == 204

        opinions = client.get(
            f"/api/v1/projects/{project['id']}/opinions", headers=auth_header(owner)
        ).json()
        assert [item["user_email"] for item in opinions] == ["owner@example.com"]

        after = client.get(
            f"/api/v1/projects/{project['id']}/result", headers=auth_header(owner)
        ).json()
        assert after["num_experts"] == 1

    def test_failed_recalculation_keeps_the_member_and_the_opinion(self, client):
        """A removal whose recalculation fails leaves the membership, opinion and result."""
        # GIVEN a project where both the admin and an expert submitted an opinion
        owner = register_and_login(client, "owner@example.com")
        project = create_project(client, owner)
        submit_opinion(client, owner, project["id"], 30.0, 50.0, 70.0)
        expert, expert_id = _add_expert(client, owner, project["id"], "expert@example.com")
        submit_opinion(client, expert, project["id"], 10.0, 20.0, 30.0)
        result_before = client.get(
            f"/api/v1/projects/{project['id']}/result", headers=auth_header(owner)
        ).json()
        assert result_before["num_experts"] == 2

        # WHEN the recalculation fails while the admin removes the expert
        with (
            patch.object(
                CalculationService, "stage_recalculation", side_effect=RuntimeError("boom")
            ),
            pytest.raises(RuntimeError),
        ):
            client.delete(
                f"/api/v1/projects/{project['id']}/members/{expert_id}",
                headers=auth_header(owner),
            )

        # THEN the expert is still a member, their opinion remains and the result is unchanged
        members = client.get(
            f"/api/v1/projects/{project['id']}/members", headers=auth_header(owner)
        ).json()
        assert expert_id in [member["user_id"] for member in members]
        opinions = client.get(
            f"/api/v1/projects/{project['id']}/opinions", headers=auth_header(owner)
        ).json()
        assert len(opinions) == 2
        after = client.get(
            f"/api/v1/projects/{project['id']}/result", headers=auth_header(owner)
        ).json()
        assert after == result_before

    def test_remove_member_self_fails(self, client):
        """Admin cannot remove themselves."""
        # GIVEN
        token = register_and_login(client)
        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test"},
            headers=auth_header(token),
        )
        project_id = create_resp.json()["id"]
        admin_id = create_resp.json()["admin_id"]

        # WHEN
        response = client.delete(
            f"/api/v1/projects/{project_id}/members/{admin_id}",
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 400
        assert "cannot remove themselves" in response.json()["detail"]

    def test_remove_nonexistent_member(self, client):
        """Removing non-member returns 404."""
        # GIVEN
        token = register_and_login(client)
        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test"},
            headers=auth_header(token),
        )
        project_id = create_resp.json()["id"]
        fake_user_id = "00000000-0000-0000-0000-000000000000"

        # WHEN
        response = client.delete(
            f"/api/v1/projects/{project_id}/members/{fake_user_id}",
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 404

    def test_remove_member_not_member(self, client):
        """A non-member cannot remove members and gets a 404 (existence hidden)."""
        # GIVEN
        token1 = register_and_login(client, "owner@example.com")
        token2 = register_and_login(client, "other@example.com")

        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test"},
            headers=auth_header(token1),
        )
        project_id = create_resp.json()["id"]
        admin_id = create_resp.json()["admin_id"]

        # WHEN
        response = client.delete(
            f"/api/v1/projects/{project_id}/members/{admin_id}",
            headers=auth_header(token2),
        )

        # THEN
        assert response.status_code == 404


class TestTransferOwnership:
    """Tests for POST /api/v1/projects/{id}/transfer-ownership."""

    def test_transfer_ownership_success(self, client):
        """Admin transfers ownership; admin_id moves and roles are swapped."""
        # GIVEN
        owner = register_and_login(client, "owner@example.com")
        project = create_project(client, owner, "Shared")
        project_id = project["id"]
        owner_id = project["admin_id"]
        _expert_token, expert_id = _add_expert(client, owner, project_id, "expert@example.com")

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project_id}/transfer-ownership",
            json={"new_admin_id": expert_id},
            headers=auth_header(owner),
        )

        # THEN
        assert response.status_code == 200
        assert response.json()["admin_id"] == expert_id
        members = client.get(
            f"/api/v1/projects/{project_id}/members", headers=auth_header(owner)
        ).json()
        roles = {m["user_id"]: m["role"] for m in members}
        assert roles[expert_id] == "admin"
        assert roles[owner_id] == "expert"

    def test_transfer_to_non_member_returns_404(self, client):
        """Transferring to a user who is not a member returns 404."""
        # GIVEN
        owner = register_and_login(client, "owner@example.com")
        project = create_project(client, owner, "Solo")
        fake_id = "00000000-0000-0000-0000-000000000000"

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/transfer-ownership",
            json={"new_admin_id": fake_id},
            headers=auth_header(owner),
        )

        # THEN
        assert response.status_code == 404

    def test_transfer_to_demo_account_returns_404(self, client):
        """Transferring to a demo account is refused exactly like a non-member.

        A demo account seeded into an example project is an ordinary ProjectMember
        row, so this is the case membership alone cannot catch: the target really is
        a member, and would pass the check that rejects a stranger. It still has to
        be refused, because it can never log in to use the ownership it was handed.
        """
        # GIVEN a project with a demo account as an ordinary member
        owner = register_and_login(client, "owner@example.com")
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

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/transfer-ownership",
            json={"new_admin_id": str(demo_id)},
            headers=auth_header(owner),
        )

        # THEN
        assert response.status_code == 404

    def test_transfer_to_self_returns_400(self, client):
        """Transferring ownership to yourself returns 400."""
        # GIVEN
        owner = register_and_login(client, "owner@example.com")
        project = create_project(client, owner, "Solo")
        owner_id = project["admin_id"]

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/transfer-ownership",
            json={"new_admin_id": owner_id},
            headers=auth_header(owner),
        )

        # THEN
        assert response.status_code == 400

    def test_transfer_member_not_admin_returns_403(self, client):
        """A member who is not the admin cannot transfer ownership (403, not 404)."""
        # GIVEN
        owner = register_and_login(client, "owner@example.com")
        project = create_project(client, owner, "Shared")
        project_id = project["id"]
        expert_token, expert_id = _add_expert(client, owner, project_id, "expert@example.com")

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project_id}/transfer-ownership",
            json={"new_admin_id": expert_id},
            headers=auth_header(expert_token),
        )

        # THEN
        assert response.status_code == 403

    def test_transfer_unblocks_account_deletion(self, client):
        """The former owner can delete their account once ownership is transferred."""
        # GIVEN
        owner = register_and_login(client, "owner@example.com")
        project = create_project(client, owner, "Shared")
        project_id = project["id"]
        _expert_token, expert_id = _add_expert(client, owner, project_id, "expert@example.com")
        client.post(
            f"/api/v1/projects/{project_id}/transfer-ownership",
            json={"new_admin_id": expert_id},
            headers=auth_header(owner),
        )

        # WHEN
        response = client.delete("/api/v1/users/me", headers=auth_header(owner))

        # THEN
        assert response.status_code == 204


class TestUpdateProjectScaleWithOpinions:
    """A scale change on PATCH /api/v1/projects/{id} must keep every opinion inside it."""

    @pytest.mark.parametrize(
        "change",
        [{"scale_max": 50.0}, {"scale_min": 50.0}, {"scale_min": 41.0, "scale_max": 79.0}],
        ids=["max-below-upper-bound", "min-above-lower-bound", "both-ends-inside-the-opinion"],
    )
    def test_narrowing_past_an_opinion_is_refused(self, client, change):
        """A new scale that would leave an opinion outside it answers 409 and changes nothing."""
        # GIVEN a project on 0..100 with one opinion spanning 40..80
        token = register_and_login(client)
        project_id = create_project(client, token)["id"]
        submit_opinion(client, token, project_id, 40.0, 60.0, 80.0)

        # WHEN the admin narrows the scale past that opinion
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json=change,
            headers=auth_header(token),
        )

        # THEN the change is refused and the stored scale is unchanged
        assert response.status_code == 409
        assert response.json()["code"] == "scale_excludes_opinions"
        project = client.get(f"/api/v1/projects/{project_id}", headers=auth_header(token)).json()
        assert project["scale_min"] == 0.0
        assert project["scale_max"] == 100.0

    def test_a_refused_request_applies_none_of_its_fields(self, client):
        """A refused scale change that also renames the project leaves the name alone."""
        # GIVEN a project with one opinion reaching 80
        token = register_and_login(client)
        project_id = create_project(client, token, name="Original")["id"]
        submit_opinion(client, token, project_id, 40.0, 60.0, 80.0)

        # WHEN the admin renames it and narrows the scale past the opinion in one request
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Renamed", "scale_max": 50.0},
            headers=auth_header(token),
        )

        # THEN the request is refused and the name is unchanged
        assert response.status_code == 409
        project = client.get(f"/api/v1/projects/{project_id}", headers=auth_header(token)).json()
        assert project["name"] == "Original"

    def test_narrowing_onto_the_opinion_bounds_keeps_the_result(self, client):
        """A scale that still contains every opinion, bounds included, is accepted."""
        # GIVEN a project on 0..100 with one opinion 40/60/80 and its calculated result
        token = register_and_login(client)
        project_id = create_project(client, token)["id"]
        submit_opinion(client, token, project_id, 40.0, 60.0, 80.0)
        result_url = f"/api/v1/projects/{project_id}/result"
        before = client.get(result_url, headers=auth_header(token)).json()

        # WHEN the admin narrows the scale to exactly 40..80
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"scale_min": 40.0, "scale_max": 80.0},
            headers=auth_header(token),
        )

        # THEN the scale is updated and the aggregation numbers are the same as before
        assert response.status_code == 200
        assert response.json()["scale_min"] == 40.0
        assert response.json()["scale_max"] == 80.0
        after = client.get(result_url, headers=auth_header(token)).json()
        for field in ("best_compromise", "arithmetic_mean", "median"):
            assert after[field] == before[field]

    def test_widening_with_opinions_is_accepted(self, client):
        """Widening the scale never excludes an opinion."""
        # GIVEN a project on 0..100 with one opinion
        token = register_and_login(client)
        project_id = create_project(client, token)["id"]
        submit_opinion(client, token, project_id, 40.0, 60.0, 80.0)

        # WHEN the admin widens the scale to -50..200
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"scale_min": -50.0, "scale_max": 200.0},
            headers=auth_header(token),
        )

        # THEN the change is applied
        assert response.status_code == 200
        assert response.json()["scale_min"] == -50.0
        assert response.json()["scale_max"] == 200.0

    def test_opinions_of_another_project_do_not_block_the_change(self, client):
        """Only the edited project's own opinions are checked against its new scale."""
        # GIVEN project B holding an opinion 40/60/80 and project A with none
        token = register_and_login(client)
        project_a = create_project(client, token, name="A")["id"]
        project_b = create_project(client, token, name="B")["id"]
        submit_opinion(client, token, project_b, 40.0, 60.0, 80.0)

        # WHEN the admin narrows project A's scale below that opinion's upper bound
        response = client.patch(
            f"/api/v1/projects/{project_a}",
            json={"scale_max": 50.0},
            headers=auth_header(token),
        )

        # THEN the change is applied
        assert response.status_code == 200
        assert response.json()["scale_max"] == 50.0

    def test_echoing_an_unchanged_scale_with_a_rename_is_accepted(self, client):
        """A project already holding out-of-range opinions still accepts an unchanged scale."""
        # GIVEN a project whose stored scale 0..70 sits below an existing 40/60/80 opinion
        token = register_and_login(client)
        project = create_project(client, token, name="Original")
        project_id = project["id"]
        submit_opinion(client, token, project_id, 40.0, 60.0, 80.0)
        with app_session(client) as session:
            row = session.get(Project, UUID(project_id))
            row.scale_max = 70.0
            session.add(row)
            session.commit()

        # WHEN the admin renames it and sends the same scale back
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Renamed", "scale_min": 0.0, "scale_max": 70.0},
            headers=auth_header(token),
        )

        # THEN the request is accepted and the name is updated
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"
