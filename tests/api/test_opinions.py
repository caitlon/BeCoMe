"""Integration tests for opinion management endpoints."""

from tests.api.conftest import (
    auth_header,
    create_project,
    register_and_login,
    submit_opinion,
)


class TestListOpinions:
    """Tests for GET /api/v1/projects/{id}/opinions."""

    def test_returns_empty_list_for_new_project(self, client):
        """Returns empty list when project has no opinions."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)

        # WHEN
        response = client.get(
            f"/api/v1/projects/{project['id']}/opinions",
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_opinions_with_user_details(self, client):
        """Returns opinions with user information."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)
        submit_opinion(client, token, project["id"], 30.0, 50.0, 70.0)

        # WHEN
        response = client.get(
            f"/api/v1/projects/{project['id']}/opinions",
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_email"] == "test@example.com"
        assert data[0]["lower_bound"] == 30.0
        assert data[0]["peak"] == 50.0
        assert data[0]["upper_bound"] == 70.0
        assert "centroid" in data[0]

    def test_requires_authentication(self, client):
        """Returns 401 without authentication."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)

        # WHEN
        response = client.get(f"/api/v1/projects/{project['id']}/opinions")

        # THEN
        assert response.status_code == 401

    def test_requires_membership(self, client):
        """Returns 403 for non-members."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        other_token = register_and_login(client, "other@example.com")
        project = create_project(client, admin_token)

        # WHEN
        response = client.get(
            f"/api/v1/projects/{project['id']}/opinions",
            headers=auth_header(other_token),
        )

        # THEN
        assert response.status_code == 403

    def test_returns_404_for_nonexistent_project(self, client):
        """Returns 404 for non-existent project."""
        # GIVEN
        token = register_and_login(client)
        fake_id = "00000000-0000-0000-0000-000000000000"

        # WHEN
        response = client.get(
            f"/api/v1/projects/{fake_id}/opinions",
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 404


class TestSubmitOpinion:
    """Tests for POST /api/v1/projects/{id}/opinions."""

    def test_creates_opinion_successfully(self, client):
        """Creates new opinion with 201."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={
                "position": "Chairman",
                "lower_bound": 40.0,
                "peak": 60.0,
                "upper_bound": 80.0,
            },
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 201
        data = response.json()
        assert data["position"] == "Chairman"
        assert data["lower_bound"] == 40.0
        assert data["peak"] == 60.0
        assert data["upper_bound"] == 80.0
        assert data["centroid"] == 60.0

    def test_updates_existing_opinion(self, client):
        """Updates opinion when user already has one."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)
        submit_opinion(client, token, project["id"], 30.0, 50.0, 70.0)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={
                "position": "Updated",
                "lower_bound": 40.0,
                "peak": 60.0,
                "upper_bound": 80.0,
            },
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 201
        data = response.json()
        assert data["position"] == "Updated"
        assert data["lower_bound"] == 40.0

        # Verify only one opinion exists
        list_resp = client.get(
            f"/api/v1/projects/{project['id']}/opinions",
            headers=auth_header(token),
        )
        assert len(list_resp.json()) == 1

    def test_validates_fuzzy_constraints(self, client):
        """Returns 422 when fuzzy constraints violated."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)

        # WHEN - lower > peak
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={
                "lower_bound": 70.0,
                "peak": 50.0,
                "upper_bound": 80.0,
            },
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 422

    def test_validates_scale_bounds(self, client):
        """Returns 422 when values outside project scale."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)

        # WHEN - upper_bound > scale_max (100)
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={
                "lower_bound": 80.0,
                "peak": 90.0,
                "upper_bound": 110.0,
            },
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 422

    def test_validates_all_values_within_scale(self, client):
        """Returns 422 when lower_bound is below scale_min."""
        # GIVEN
        token = register_and_login(client)
        project_resp = client.post(
            "/api/v1/projects",
            json={"name": "Test", "scale_min": 20, "scale_max": 80},
            headers=auth_header(token),
        )
        project = project_resp.json()

        # WHEN - lower_bound (10) is below scale_min (20)
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={
                "lower_bound": 10.0,  # Below scale_min!
                "peak": 50.0,
                "upper_bound": 70.0,
            },
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 422
        assert "within project scale" in response.json()["detail"]

    def test_requires_membership(self, client):
        """Returns 403 for non-members."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        other_token = register_and_login(client, "other@example.com")
        project = create_project(client, admin_token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={
                "lower_bound": 40.0,
                "peak": 60.0,
                "upper_bound": 80.0,
            },
            headers=auth_header(other_token),
        )

        # THEN
        assert response.status_code == 403

    def test_triggers_calculation(self, client):
        """Triggers recalculation after submitting opinion."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)

        # WHEN
        submit_opinion(client, token, project["id"], 30.0, 50.0, 70.0)

        # THEN - result should exist
        result_resp = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(token),
        )
        assert result_resp.status_code == 200
        data = result_resp.json()
        assert data is not None
        assert data["num_experts"] == 1


class TestDeleteOpinion:
    """Tests for DELETE /api/v1/projects/{id}/opinions."""

    def test_deletes_own_opinion(self, client):
        """Deletes user's opinion with 204."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)
        submit_opinion(client, token, project["id"])

        # WHEN
        response = client.delete(
            f"/api/v1/projects/{project['id']}/opinions",
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 204

        # Verify opinion is deleted
        list_resp = client.get(
            f"/api/v1/projects/{project['id']}/opinions",
            headers=auth_header(token),
        )
        assert list_resp.json() == []

    def test_returns_404_when_no_opinion(self, client):
        """Returns 404 when user has no opinion."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)

        # WHEN
        response = client.delete(
            f"/api/v1/projects/{project['id']}/opinions",
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 404

    def test_requires_membership(self, client):
        """Returns 403 for non-members."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        other_token = register_and_login(client, "other@example.com")
        project = create_project(client, admin_token)

        # WHEN
        response = client.delete(
            f"/api/v1/projects/{project['id']}/opinions",
            headers=auth_header(other_token),
        )

        # THEN
        assert response.status_code == 403

    def test_triggers_recalculation(self, client):
        """Triggers recalculation after deleting opinion."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        expert_token = register_and_login(client, "expert@example.com")
        project = create_project(client, admin_token)

        # Invite expert
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=auth_header(admin_token),
        )
        invite_token = invite_resp.json()["token"]
        client.post(
            f"/api/v1/invitations/{invite_token}/accept",
            headers=auth_header(expert_token),
        )

        # Submit opinions from both users
        submit_opinion(client, admin_token, project["id"], 20.0, 40.0, 60.0)
        submit_opinion(client, expert_token, project["id"], 40.0, 60.0, 80.0)

        # Verify 2 experts
        result_before = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(admin_token),
        ).json()
        assert result_before["num_experts"] == 2

        # WHEN - expert deletes opinion
        client.delete(
            f"/api/v1/projects/{project['id']}/opinions",
            headers=auth_header(expert_token),
        )

        # THEN - result should update
        result_after = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(admin_token),
        ).json()
        assert result_after["num_experts"] == 1

    def test_deletes_result_when_last_opinion_removed(self, client):
        """Deletes result when all opinions are removed."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)
        submit_opinion(client, token, project["id"])

        # Verify result exists
        result_before = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(token),
        ).json()
        assert result_before is not None

        # WHEN
        client.delete(
            f"/api/v1/projects/{project['id']}/opinions",
            headers=auth_header(token),
        )

        # THEN
        result_after = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(token),
        ).json()
        assert result_after is None


class TestGetResult:
    """Tests for GET /api/v1/projects/{id}/result."""

    def test_returns_none_for_empty_project(self, client):
        """Returns None when project has no opinions."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)

        # WHEN
        response = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 200
        assert response.json() is None

    def test_returns_result_with_all_fields(self, client):
        """Returns calculation result with all fields."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)
        submit_opinion(client, token, project["id"], 30.0, 50.0, 70.0)

        # WHEN
        response = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert "best_compromise" in data
        assert "arithmetic_mean" in data
        assert "median" in data
        assert "max_error" in data
        assert data["num_experts"] == 1
        assert "calculated_at" in data

    def test_includes_likert_for_standard_scale(self, client):
        """Includes Likert interpretation for 0-100 scale."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)
        submit_opinion(client, token, project["id"], 70.0, 80.0, 90.0)

        # WHEN
        response = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(token),
        )

        # THEN
        data = response.json()
        assert data["likert_value"] is not None
        assert data["likert_decision"] is not None

    def test_skips_likert_for_custom_scale(self, client):
        """Skips Likert for non 0-100 scale."""
        # GIVEN
        token = register_and_login(client)
        project_resp = client.post(
            "/api/v1/projects",
            json={"name": "Custom Scale", "scale_min": 1, "scale_max": 5},
            headers=auth_header(token),
        )
        project = project_resp.json()
        submit_opinion(client, token, project["id"], 2.0, 3.0, 4.0)

        # WHEN
        response = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(token),
        )

        # THEN
        data = response.json()
        assert data["likert_value"] is None
        assert data["likert_decision"] is None

    def test_requires_membership(self, client):
        """Returns 403 for non-members."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        other_token = register_and_login(client, "other@example.com")
        project = create_project(client, admin_token)

        # WHEN
        response = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(other_token),
        )

        # THEN
        assert response.status_code == 403


class TestOpinionFlow:
    """Integration tests for complete opinion workflow."""

    def test_full_opinion_flow(self, client):
        """Complete flow: submit opinions -> get result -> update -> delete."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        expert_token = register_and_login(client, "expert@example.com")
        project = create_project(client, admin_token, "Decision Project")

        # Invite expert
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=auth_header(admin_token),
        )
        invite_token = invite_resp.json()["token"]
        client.post(
            f"/api/v1/invitations/{invite_token}/accept",
            headers=auth_header(expert_token),
        )

        # Step 1: Admin submits opinion
        submit_opinion(client, admin_token, project["id"], 20.0, 40.0, 60.0, "Chairman")

        result1 = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(admin_token),
        ).json()
        assert result1["num_experts"] == 1

        # Step 2: Expert submits opinion
        submit_opinion(client, expert_token, project["id"], 40.0, 60.0, 80.0, "Expert")

        result2 = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(admin_token),
        ).json()
        assert result2["num_experts"] == 2

        # Step 3: Expert updates opinion
        submit_opinion(client, expert_token, project["id"], 50.0, 70.0, 90.0)

        result3 = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(admin_token),
        ).json()
        assert result3["num_experts"] == 2
        assert result3["best_compromise"] != result2["best_compromise"]

        # Step 4: Expert deletes opinion
        client.delete(
            f"/api/v1/projects/{project['id']}/opinions",
            headers=auth_header(expert_token),
        )

        result4 = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(admin_token),
        ).json()
        assert result4["num_experts"] == 1

        # Verify opinions list
        opinions = client.get(
            f"/api/v1/projects/{project['id']}/opinions",
            headers=auth_header(admin_token),
        ).json()
        assert len(opinions) == 1
        assert opinions[0]["position"] == "Chairman"

    def test_calculation_with_odd_number_of_experts(self, client):
        """Verifies calculation with 3 experts (odd median strategy)."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        expert1_token = register_and_login(client, "expert1@example.com")
        expert2_token = register_and_login(client, "expert2@example.com")
        project = create_project(client, admin_token)

        # Invite experts
        for expert_token in [expert1_token, expert2_token]:
            invite_resp = client.post(
                f"/api/v1/projects/{project['id']}/invite",
                json={},
                headers=auth_header(admin_token),
            )
            invite_token = invite_resp.json()["token"]
            client.post(
                f"/api/v1/invitations/{invite_token}/accept",
                headers=auth_header(expert_token),
            )

        # Submit opinions
        submit_opinion(client, admin_token, project["id"], 20.0, 40.0, 60.0)
        submit_opinion(client, expert1_token, project["id"], 30.0, 50.0, 70.0)
        submit_opinion(client, expert2_token, project["id"], 40.0, 60.0, 80.0)

        # WHEN
        result = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(admin_token),
        ).json()

        # THEN
        assert result["num_experts"] == 3
        assert result["best_compromise"] is not None
        assert result["max_error"] >= 0
