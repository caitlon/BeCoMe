"""Tests for GET /api/v1/users/me/export endpoint (GDPR Article 20)."""

from fastapi import status

from tests.integration.api.conftest import (
    auth_header,
    create_project,
    register_and_login,
    submit_opinion,
)

_EXPORT_URL = "/api/v1/users/me/export"


class TestDataExport:
    """Tests for the GDPR data export endpoint."""

    def test_export_returns_profile(self, client):
        """The export carries the authenticated user's profile and metadata."""
        # GIVEN
        token = register_and_login(client, "export@example.com")

        # WHEN
        response = client.get(_EXPORT_URL, headers=auth_header(token))

        # THEN
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["profile"]["email"] == "export@example.com"
        assert "created_at" in data["profile"]
        assert data["export_metadata"]["format_version"]

    def test_export_includes_owned_project_and_opinion(self, client):
        """Owned projects and submitted opinions appear in the export."""
        # GIVEN - a user who owns a project and submitted an opinion
        token = register_and_login(client, "owner@example.com")
        project = create_project(client, token, "My Project")
        project_id = project["id"]
        submit_opinion(client, token, project_id, 20.0, 50.0, 80.0, "Lead")

        # WHEN
        response = client.get(_EXPORT_URL, headers=auth_header(token))

        # THEN
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert any(p["name"] == "My Project" for p in data["owned_projects"])
        opinions = data["opinions"]
        assert len(opinions) == 1
        assert opinions[0]["project_id"] == project_id
        assert opinions[0]["position"] == "Lead"
        assert opinions[0]["peak"] == 50.0

    def test_export_includes_membership(self, client):
        """A project the user joined as an expert shows up under memberships."""
        # GIVEN - owner invites an expert who accepts
        owner = register_and_login(client, "m-owner@example.com")
        expert = register_and_login(client, "m-expert@example.com")
        project = create_project(client, owner, "Shared Project")
        project_id = project["id"]
        client.post(
            f"/api/v1/projects/{project_id}/invite",
            json={"email": "m-expert@example.com"},
            headers=auth_header(owner),
        )
        invitations = client.get("/api/v1/invitations", headers=auth_header(expert)).json()
        client.post(
            f"/api/v1/invitations/{invitations[0]['id']}/accept",
            headers=auth_header(expert),
        )

        # WHEN - the expert exports their data
        data = client.get(_EXPORT_URL, headers=auth_header(expert)).json()

        # THEN
        memberships = data["memberships"]
        assert any(m["project_name"] == "Shared Project" for m in memberships)
        assert memberships[0]["role"] == "expert"

    def test_export_excludes_password_hash(self, client):
        """The export never exposes password material."""
        # GIVEN
        token = register_and_login(client, "secure@example.com")

        # WHEN
        response = client.get(_EXPORT_URL, headers=auth_header(token))

        # THEN
        assert "hashed_password" not in response.text
        assert "hashed_password" not in response.json()["profile"]

    def test_export_empty_account_has_empty_collections(self, client):
        """A fresh account exports empty lists, never null."""
        # GIVEN
        token = register_and_login(client, "fresh@example.com")

        # WHEN
        data = client.get(_EXPORT_URL, headers=auth_header(token)).json()

        # THEN
        assert data["owned_projects"] == []
        assert data["memberships"] == []
        assert data["opinions"] == []
        assert data["received_invitations"] == []

    def test_export_requires_authentication(self, client):
        """Unauthenticated requests are rejected."""
        # WHEN
        response = client.get(_EXPORT_URL)

        # THEN
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
