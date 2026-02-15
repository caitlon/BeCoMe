"""E2E tests for access control and role-based permissions."""

import pytest

from tests.e2e.conftest import (
    auth_headers,
    create_project,
    invite_and_accept,
    register_user,
    unique_email,
)


@pytest.mark.e2e
class TestNonMemberAccess:
    """Users who are not project members must be denied access."""

    def test_non_member_cannot_access_project(self, http_client):
        """GET project by a non-member returns 403."""
        # GIVEN — two users, one owns a project
        owner_email = unique_email("owner")
        outsider_email = unique_email("outsider")
        owner_token = register_user(http_client, owner_email)
        outsider_token = register_user(http_client, outsider_email)
        project = create_project(http_client, owner_token)

        # WHEN — outsider tries to access the project
        response = http_client.get(
            f"/projects/{project['id']}",
            headers=auth_headers(outsider_token),
        )

        # THEN
        assert response.status_code == 403

    def test_non_member_cannot_submit_opinion(self, http_client):
        """POST opinion by a non-member returns 403."""
        # GIVEN
        owner_email = unique_email("owner")
        outsider_email = unique_email("outsider")
        owner_token = register_user(http_client, owner_email)
        outsider_token = register_user(http_client, outsider_email)
        project = create_project(http_client, owner_token)

        # WHEN — outsider submits an opinion
        response = http_client.post(
            f"/projects/{project['id']}/opinions",
            json={
                "position": "Intruder",
                "lower_bound": 10.0,
                "peak": 50.0,
                "upper_bound": 90.0,
            },
            headers=auth_headers(outsider_token),
        )

        # THEN
        assert response.status_code == 403


@pytest.mark.e2e
class TestExpertPermissions:
    """Expert members have limited permissions compared to admins."""

    def test_expert_cannot_delete_project(self, http_client):
        """Expert member DELETE project returns 403."""
        # GIVEN — owner and expert in the same project
        owner_email = unique_email("owner")
        expert_email = unique_email("expert")
        owner_token = register_user(http_client, owner_email)
        expert_token = register_user(http_client, expert_email)
        project = create_project(http_client, owner_token)
        invite_and_accept(http_client, owner_token, expert_token, expert_email, project["id"])

        # WHEN — expert tries to delete the project
        response = http_client.delete(
            f"/projects/{project['id']}",
            headers=auth_headers(expert_token),
        )

        # THEN
        assert response.status_code == 403

    def test_expert_cannot_remove_members(self, http_client):
        """Expert cannot remove other members from a project."""
        # GIVEN — owner and two experts
        owner_email = unique_email("owner")
        expert1_email = unique_email("expert1")
        expert2_email = unique_email("expert2")
        owner_token = register_user(http_client, owner_email)
        expert1_token = register_user(http_client, expert1_email)
        expert2_token = register_user(http_client, expert2_email)
        project = create_project(http_client, owner_token)
        invite_and_accept(http_client, owner_token, expert1_token, expert1_email, project["id"])
        invite_and_accept(http_client, owner_token, expert2_token, expert2_email, project["id"])

        # Get expert2's user ID from members list
        members = http_client.get(
            f"/projects/{project['id']}/members",
            headers=auth_headers(owner_token),
        ).json()
        expert2_id = next(
            (m["user_id"] for m in members if m["email"] == expert2_email),
            None,
        )
        assert expert2_id is not None, f"Expert ({expert2_email}) not found in members"

        # WHEN — expert1 tries to remove expert2
        response = http_client.delete(
            f"/projects/{project['id']}/members/{expert2_id}",
            headers=auth_headers(expert1_token),
        )

        # THEN
        assert response.status_code == 403


@pytest.mark.e2e
class TestAdminPermissions:
    """Admin (project owner) has full control over their project."""

    def test_admin_can_delete_own_project(self, http_client):
        """Owner DELETE project returns 204 and project becomes inaccessible."""
        # GIVEN — owner with a project
        owner_email = unique_email("owner")
        owner_token = register_user(http_client, owner_email)
        project = create_project(http_client, owner_token)

        # WHEN — owner deletes the project
        response = http_client.delete(
            f"/projects/{project['id']}",
            headers=auth_headers(owner_token),
        )

        # THEN — deletion succeeds
        assert response.status_code == 204

        # AND — project is no longer accessible
        get_response = http_client.get(
            f"/projects/{project['id']}",
            headers=auth_headers(owner_token),
        )
        assert get_response.status_code == 404
