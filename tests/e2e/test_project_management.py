"""E2E tests for project management: update, standalone calculate, invitations."""

import pytest

from tests.e2e.conftest import (
    auth_headers,
    create_project,
    register_user,
    unique_email,
)


@pytest.mark.e2e
class TestUpdateProject:
    """PATCH /projects/{id} must update project fields."""

    def test_update_project_name_and_description(self, http_client):
        """Admin renames project and adds description."""
        # GIVEN — a project
        email = unique_email("projup")
        token = register_user(http_client, email)
        project = create_project(http_client, token, "Original Name")

        # WHEN — update name and description
        update_resp = http_client.patch(
            f"/projects/{project['id']}",
            json={"name": "Renamed Project", "description": "New description"},
            headers=auth_headers(token),
        )

        # THEN — response reflects changes
        assert update_resp.status_code == 200
        body = update_resp.json()
        assert body["name"] == "Renamed Project"
        assert body["description"] == "New description"

        # Verify via GET
        get_resp = http_client.get(
            f"/projects/{project['id']}",
            headers=auth_headers(token),
        )
        get_resp.raise_for_status()
        assert get_resp.json()["name"] == "Renamed Project"


@pytest.mark.e2e
class TestStandaloneCalculation:
    """POST /calculate must return correct BeCoMe results."""

    def test_standalone_calculate_three_experts(self, http_client):
        """Three experts produce correct arithmetic mean, median, and best compromise."""
        # GIVEN — three expert opinions
        payload = {
            "experts": [
                {"name": "Expert A", "lower": 10.0, "peak": 20.0, "upper": 30.0},
                {"name": "Expert B", "lower": 20.0, "peak": 30.0, "upper": 40.0},
                {"name": "Expert C", "lower": 30.0, "peak": 40.0, "upper": 50.0},
            ]
        }

        # WHEN — call standalone calculate
        response = http_client.post("/calculate", json=payload)

        # THEN — correct results
        assert response.status_code == 200
        result = response.json()
        assert result["num_experts"] == 3

        # Arithmetic mean: (10+20+30)/3=20, (20+30+40)/3=30, (30+40+50)/3=40
        assert result["arithmetic_mean"]["lower"] == pytest.approx(20.0)
        assert result["arithmetic_mean"]["peak"] == pytest.approx(30.0)
        assert result["arithmetic_mean"]["upper"] == pytest.approx(40.0)

        # Median (odd, 3 experts sorted by centroid): middle expert is B=(20,30,40)
        assert result["median"]["lower"] == pytest.approx(20.0)
        assert result["median"]["peak"] == pytest.approx(30.0)
        assert result["median"]["upper"] == pytest.approx(40.0)

        # Best compromise = average of mean and median
        assert result["best_compromise"]["lower"] == pytest.approx(20.0)
        assert result["best_compromise"]["peak"] == pytest.approx(30.0)
        assert result["best_compromise"]["upper"] == pytest.approx(40.0)


@pytest.mark.e2e
class TestListPendingInvitations:
    """GET /projects/{id}/invitations must return pending invitations."""

    def test_list_pending_invitations(self, http_client):
        """Invite an expert, verify the invitation appears in the list."""
        # GIVEN — a project owner and a registered expert
        owner_email = unique_email("invowner")
        expert_email = unique_email("invexpert")
        owner_token = register_user(http_client, owner_email)
        register_user(http_client, expert_email)
        project = create_project(http_client, owner_token, "Invitation List Test")

        # WHEN — owner invites expert
        invite_resp = http_client.post(
            f"/projects/{project['id']}/invite",
            json={"email": expert_email},
            headers=auth_headers(owner_token),
        )
        invite_resp.raise_for_status()

        # THEN — invitations list shows the pending invitation
        list_resp = http_client.get(
            f"/projects/{project['id']}/invitations",
            headers=auth_headers(owner_token),
        )
        assert list_resp.status_code == 200
        invitations = list_resp.json()
        assert len(invitations) >= 1
        emails = [inv["invitee_email"] for inv in invitations]
        assert expert_email in emails
