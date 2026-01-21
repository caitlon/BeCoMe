"""Tests for project management endpoints."""

from tests.api.conftest import auth_header, register_and_login


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
        """403 returned when user is not a member."""
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
        assert response.status_code == 403


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

    def test_update_project_not_admin(self, client):
        """Non-admin cannot update project."""
        # GIVEN - would need invitation flow to test properly
        # For now, test that non-member gets 403
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
        assert response.status_code == 403

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

        # WHEN - update scale_max to equal scale_min
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

    def test_delete_project_not_admin(self, client):
        """Non-admin cannot delete project."""
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
        assert response.status_code == 403


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
        """Non-member cannot see members list."""
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
        assert response.status_code == 403


class TestRemoveMember:
    """Tests for DELETE /api/v1/projects/{id}/members/{user_id}."""

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

    def test_remove_member_not_admin(self, client):
        """Non-admin cannot remove members."""
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
        assert response.status_code == 403
