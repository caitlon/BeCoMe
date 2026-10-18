"""Integration tests for opinion management endpoints."""

import pytest

from tests.integration.api.conftest import (
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
        """Returns 404 for non-members (project existence stays hidden)."""
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
        assert response.status_code == 404

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


def _join_project(client, owner_token, project_id, email):
    """Register an expert, invite them, accept, and return their token."""
    token = register_and_login(client, email)
    client.post(
        f"/api/v1/projects/{project_id}/invite",
        json={"email": email},
        headers=auth_header(owner_token),
    )
    invitation = client.get("/api/v1/invitations", headers=auth_header(token)).json()[0]
    client.post(f"/api/v1/invitations/{invitation['id']}/accept", headers=auth_header(token))
    return token


class TestListOpinionsForAssistant:
    """The for_assistant view leaves out opinions of users who objected."""

    @staticmethod
    def _project_with_an_objector(client):
        """Owner and expert B did not object, expert A did; all three hold an opinion."""
        owner = register_and_login(client, "owner@example.com")
        project = create_project(client, owner)
        project_id = project["id"]
        objector = _join_project(client, owner, project_id, "a@example.com")
        other = _join_project(client, owner, project_id, "b@example.com")
        for token, peak in ((owner, 50.0), (objector, 60.0), (other, 70.0)):
            submit_opinion(client, token, project_id, peak - 10.0, peak, peak + 10.0)
        client.put(
            "/api/v1/users/me", json={"assistant_objection": True}, headers=auth_header(objector)
        )
        return project_id, owner, objector, other

    @staticmethod
    def _emails(client, token, project_id, query=""):
        response = client.get(
            f"/api/v1/projects/{project_id}/opinions{query}", headers=auth_header(token)
        )
        assert response.status_code == 200
        return [row["user_email"] for row in response.json()]

    def test_other_members_do_not_get_the_objectors_row(self, client):
        """A member asking for the assistant view gets no row for the objector."""
        # GIVEN
        project_id, owner, _objector, other = self._project_with_an_objector(client)

        # WHEN / THEN
        for token in (owner, other):
            emails = self._emails(client, token, project_id, "?for_assistant=true")
            assert "a@example.com" not in emails
            assert len(emails) == 2

    def test_the_objector_still_gets_their_own_row(self, client):
        """The objector's own assistant view is complete."""
        # GIVEN
        project_id, _owner, objector, _other = self._project_with_an_objector(client)

        # WHEN
        emails = self._emails(client, objector, project_id, "?for_assistant=true")

        # THEN
        assert sorted(emails) == ["a@example.com", "b@example.com", "owner@example.com"]

    def test_two_objectors_see_only_their_own_rows(self, client):
        """Each objector gets their own row and not the other's; a bystander gets neither."""
        # GIVEN
        owner = register_and_login(client, "owner@example.com")
        project_id = create_project(client, owner)["id"]
        first = _join_project(client, owner, project_id, "a@example.com")
        second = _join_project(client, owner, project_id, "c@example.com")
        for token, peak in ((owner, 50.0), (first, 60.0), (second, 70.0)):
            submit_opinion(client, token, project_id, peak - 10.0, peak, peak + 10.0)
        for token in (first, second):
            client.put(
                "/api/v1/users/me", json={"assistant_objection": True}, headers=auth_header(token)
            )

        # WHEN
        query = "?for_assistant=true"
        first_view = self._emails(client, first, project_id, query)
        second_view = self._emails(client, second, project_id, query)
        owner_view = self._emails(client, owner, project_id, query)

        # THEN
        assert sorted(first_view) == ["a@example.com", "owner@example.com"]
        assert sorted(second_view) == ["c@example.com", "owner@example.com"]
        assert owner_view == ["owner@example.com"]

    @pytest.mark.parametrize("query", ["", "?for_assistant=false"])
    def test_the_plain_listing_is_unchanged(self, client, query):
        """Without the parameter every opinion is listed and no flag is exposed."""
        # GIVEN
        project_id, owner, _objector, _other = self._project_with_an_objector(client)

        # WHEN
        response = client.get(
            f"/api/v1/projects/{project_id}/opinions{query}", headers=auth_header(owner)
        )

        # THEN
        rows = response.json()
        assert len(rows) == 3
        assert all("assistant_objection" not in row for row in rows)

    def test_pages_of_the_filtered_view_stay_full_and_consistent(self, client):
        """The filter is applied before limit and offset, so no page comes back short."""
        # GIVEN: the objector's row sits in the middle of the creation order
        project_id, owner, _objector, _other = self._project_with_an_objector(client)

        # WHEN
        first = self._emails(client, owner, project_id, "?for_assistant=true&limit=1&offset=0")
        second = self._emails(client, owner, project_id, "?for_assistant=true&limit=1&offset=1")
        third = self._emails(client, owner, project_id, "?for_assistant=true&limit=1&offset=2")

        # THEN
        assert first + second == self._emails(client, owner, project_id, "?for_assistant=true")
        assert len(first) == len(second) == 1
        assert third == []


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

    def test_position_is_required(self, client):
        """Returns 422 when position is missing from request."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={"lower_bound": 40.0, "peak": 60.0, "upper_bound": 80.0},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 422

    def test_empty_position_rejected(self, client):
        """Returns 422 when position is an empty string."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={
                "position": "",
                "lower_bound": 40.0,
                "peak": 60.0,
                "upper_bound": 80.0,
            },
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 422

    def test_html_only_position_rejected(self, client):
        """Returns 422 when position contains only HTML tags (empty after sanitization)."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={
                "position": "<br><hr>",
                "lower_bound": 40.0,
                "peak": 60.0,
                "upper_bound": 80.0,
            },
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 422

    def test_validates_fuzzy_constraints(self, client):
        """Returns 422 when fuzzy constraints violated."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)

        # WHEN: lower > peak
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={
                "position": "Analyst",
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

        # WHEN: upper_bound > scale_max (100)
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={
                "position": "Analyst",
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

        # WHEN: lower_bound (10) is below scale_min (20)
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={
                "position": "Analyst",
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
        """Returns 404 for non-members (project existence stays hidden)."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        other_token = register_and_login(client, "other@example.com")
        project = create_project(client, admin_token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={
                "position": "Analyst",
                "lower_bound": 40.0,
                "peak": 60.0,
                "upper_bound": 80.0,
            },
            headers=auth_header(other_token),
        )

        # THEN
        assert response.status_code == 404

    def test_triggers_calculation(self, client):
        """Triggers recalculation after submitting opinion."""
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)

        # WHEN
        submit_opinion(client, token, project["id"], 30.0, 50.0, 70.0)

        # THEN: result should exist
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
        """Returns 404 for non-members (project existence stays hidden)."""
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
        assert response.status_code == 404

    def test_triggers_recalculation(self, client):
        """Triggers recalculation after deleting opinion."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        expert_token = register_and_login(client, "expert@example.com")
        project = create_project(client, admin_token)

        # Invite expert by email
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "expert@example.com"},
            headers=auth_header(admin_token),
        )
        invitation_id = invite_resp.json()["id"]
        client.post(
            f"/api/v1/invitations/{invitation_id}/accept",
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

        # WHEN: expert deletes opinion
        client.delete(
            f"/api/v1/projects/{project['id']}/opinions",
            headers=auth_header(expert_token),
        )

        # THEN: result should update
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

    def test_includes_the_agreement_level(self, client):
        """The result carries its agreement reading, so every reader shows the same one.

        A single opinion puts the mean and the median in the same place, so Δmax is
        zero and the panel reads as high agreement.
        """
        # GIVEN a project with one opinion
        token = register_and_login(client)
        project = create_project(client, token)
        submit_opinion(client, token, project["id"], 70.0, 80.0, 90.0)

        # WHEN the result is read
        response = client.get(
            f"/api/v1/projects/{project['id']}/result",
            headers=auth_header(token),
        )

        # THEN the level comes from the server, not from whoever renders it
        assert response.json()["agreement_level"] == "high"

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
        """Returns 404 for non-members (project existence stays hidden)."""
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
        assert response.status_code == 404


class TestOpinionFlow:
    """Integration tests for complete opinion workflow."""

    def test_full_opinion_flow(self, client):
        """Complete flow: submit opinions -> get result -> update -> delete."""
        # GIVEN
        admin_token = register_and_login(client, "admin@example.com")
        expert_token = register_and_login(client, "expert@example.com")
        project = create_project(client, admin_token, "Decision Project")

        # Invite expert by email
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"email": "expert@example.com"},
            headers=auth_header(admin_token),
        )
        invitation_id = invite_resp.json()["id"]
        client.post(
            f"/api/v1/invitations/{invitation_id}/accept",
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

        # Invite experts by email
        experts = [
            ("expert1@example.com", expert1_token),
            ("expert2@example.com", expert2_token),
        ]
        for email, expert_token in experts:
            invite_resp = client.post(
                f"/api/v1/projects/{project['id']}/invite",
                json={"email": email},
                headers=auth_header(admin_token),
            )
            invitation_id = invite_resp.json()["id"]
            client.post(
                f"/api/v1/invitations/{invitation_id}/accept",
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
