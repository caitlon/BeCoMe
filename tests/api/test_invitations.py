"""Tests for invitation management endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from api.config import get_settings
from api.db.models import (  # noqa: F401 - import all models to register in metadata
    CalculationResult,
    ExpertOpinion,
    Invitation,
    PasswordResetToken,
    Project,
    ProjectMember,
    User,
)
from api.dependencies import get_session
from api.routes import auth, calculate, health, invitations, projects


def _create_test_app() -> FastAPI:
    """Create FastAPI app without lifespan for testing."""
    settings = get_settings()
    app = FastAPI(
        title="BeCoMe API Test",
        version=settings.api_version,
    )
    app.include_router(health.router)
    app.include_router(calculate.router)
    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(invitations.router)
    return app


@pytest.fixture
def client():
    """Create test client with in-memory database."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)

    test_app = _create_test_app()

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    test_app.dependency_overrides[get_session] = override_get_session

    with TestClient(test_app) as test_client:
        yield test_client


def _register_and_login(client: TestClient, email: str = "test@example.com") -> str:
    """Helper to register a user and return their token."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "first_name": "Test",
            "last_name": "User",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "password123"},
    )
    return response.json()["access_token"]


def _auth_header(token: str) -> dict[str, str]:
    """Create authorization header."""
    return {"Authorization": f"Bearer {token}"}


def _create_project(client: TestClient, token: str, name: str = "Test Project") -> dict:
    """Helper to create a project and return its data."""
    response = client.post(
        "/api/v1/projects",
        json={"name": name},
        headers=_auth_header(token),
    )
    return response.json()


class TestCreateInvitation:
    """Tests for POST /api/v1/projects/{id}/invite."""

    def test_create_invitation_success(self, client):
        """Admin can create invitation."""
        # GIVEN
        token = _register_and_login(client)
        project = _create_project(client, token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"expires_in_days": 7},
            headers=_auth_header(token),
        )

        # THEN
        assert response.status_code == 201
        data = response.json()
        assert "token" in data
        assert data["project_id"] == project["id"]
        assert data["project_name"] == "Test Project"
        assert "expires_at" in data

    def test_create_invitation_with_custom_expiration(self, client):
        """Invitation is created with custom expiration."""
        # GIVEN
        token = _register_and_login(client)
        project = _create_project(client, token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"expires_in_days": 30},
            headers=_auth_header(token),
        )

        # THEN
        assert response.status_code == 201

    def test_create_invitation_default_expiration(self, client):
        """Invitation uses default expiration when not specified."""
        # GIVEN
        token = _register_and_login(client)
        project = _create_project(client, token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=_auth_header(token),
        )

        # THEN
        assert response.status_code == 201

    def test_create_invitation_project_not_found(self, client):
        """404 returned for non-existent project."""
        # GIVEN
        token = _register_and_login(client)
        fake_id = "00000000-0000-0000-0000-000000000000"

        # WHEN
        response = client.post(
            f"/api/v1/projects/{fake_id}/invite",
            json={},
            headers=_auth_header(token),
        )

        # THEN
        assert response.status_code == 404

    def test_create_invitation_not_admin(self, client):
        """Non-admin cannot create invitation."""
        # GIVEN
        admin_token = _register_and_login(client, "admin@example.com")
        other_token = _register_and_login(client, "other@example.com")
        project = _create_project(client, admin_token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=_auth_header(other_token),
        )

        # THEN
        assert response.status_code == 403

    def test_create_invitation_without_auth(self, client):
        """Invitation creation fails without authentication."""
        # GIVEN
        token = _register_and_login(client)
        project = _create_project(client, token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
        )

        # THEN
        assert response.status_code == 401

    def test_create_invitation_invalid_expiration(self, client):
        """Invitation creation fails with invalid expiration days."""
        # GIVEN
        token = _register_and_login(client)
        project = _create_project(client, token)

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"expires_in_days": 0},  # Below minimum
            headers=_auth_header(token),
        )

        # THEN
        assert response.status_code == 422


class TestGetInvitationInfo:
    """Tests for GET /api/v1/invitations/{token}."""

    def test_get_invitation_info_success(self, client):
        """Invitation info is returned for valid token."""
        # GIVEN
        token = _register_and_login(client, "admin@example.com")
        project = _create_project(client, token, "My Project")
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=_auth_header(token),
        )
        invite_token = invite_resp.json()["token"]

        # WHEN - no auth required
        response = client.get(f"/api/v1/invitations/{invite_token}")

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert data["project_name"] == "My Project"
        assert data["admin_name"] == "Test User"
        assert data["is_valid"] is True
        assert "expires_at" in data

    def test_get_invitation_info_not_found(self, client):
        """404 returned for non-existent invitation."""
        # GIVEN
        fake_token = "00000000-0000-0000-0000-000000000000"

        # WHEN
        response = client.get(f"/api/v1/invitations/{fake_token}")

        # THEN
        assert response.status_code == 404

    def test_get_invitation_info_shows_invalid_when_used(self, client):
        """Invitation info shows is_valid=False when already used."""
        # GIVEN
        admin_token = _register_and_login(client, "admin@example.com")
        expert_token = _register_and_login(client, "expert@example.com")
        project = _create_project(client, admin_token)
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=_auth_header(admin_token),
        )
        invite_token = invite_resp.json()["token"]

        # Accept the invitation
        client.post(
            f"/api/v1/invitations/{invite_token}/accept",
            headers=_auth_header(expert_token),
        )

        # WHEN
        response = client.get(f"/api/v1/invitations/{invite_token}")

        # THEN
        assert response.status_code == 200
        assert response.json()["is_valid"] is False


class TestAcceptInvitation:
    """Tests for POST /api/v1/invitations/{token}/accept."""

    def test_accept_invitation_success(self, client):
        """User joins project as expert when accepting invitation."""
        # GIVEN
        admin_token = _register_and_login(client, "admin@example.com")
        expert_token = _register_and_login(client, "expert@example.com")
        project = _create_project(client, admin_token)
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=_auth_header(admin_token),
        )
        invite_token = invite_resp.json()["token"]

        # WHEN
        response = client.post(
            f"/api/v1/invitations/{invite_token}/accept",
            headers=_auth_header(expert_token),
        )

        # THEN
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "expert@example.com"
        assert data["role"] == "expert"

    def test_accept_invitation_user_can_see_project(self, client):
        """User can access project after accepting invitation."""
        # GIVEN
        admin_token = _register_and_login(client, "admin@example.com")
        expert_token = _register_and_login(client, "expert@example.com")
        project = _create_project(client, admin_token)
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=_auth_header(admin_token),
        )
        invite_token = invite_resp.json()["token"]

        # WHEN
        client.post(
            f"/api/v1/invitations/{invite_token}/accept",
            headers=_auth_header(expert_token),
        )

        # THEN - expert can now access project
        get_resp = client.get(
            f"/api/v1/projects/{project['id']}",
            headers=_auth_header(expert_token),
        )
        assert get_resp.status_code == 200

    def test_accept_invitation_increases_member_count(self, client):
        """Member count increases after accepting invitation."""
        # GIVEN
        admin_token = _register_and_login(client, "admin@example.com")
        expert_token = _register_and_login(client, "expert@example.com")
        project = _create_project(client, admin_token)
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=_auth_header(admin_token),
        )
        invite_token = invite_resp.json()["token"]

        # WHEN
        client.post(
            f"/api/v1/invitations/{invite_token}/accept",
            headers=_auth_header(expert_token),
        )

        # THEN
        get_resp = client.get(
            f"/api/v1/projects/{project['id']}",
            headers=_auth_header(admin_token),
        )
        assert get_resp.json()["member_count"] == 2

    def test_accept_invitation_not_found(self, client):
        """404 returned for non-existent invitation."""
        # GIVEN
        token = _register_and_login(client)
        fake_invite = "00000000-0000-0000-0000-000000000000"

        # WHEN
        response = client.post(
            f"/api/v1/invitations/{fake_invite}/accept",
            headers=_auth_header(token),
        )

        # THEN
        assert response.status_code == 404

    def test_accept_invitation_already_used(self, client):
        """400 returned when invitation was already used."""
        # GIVEN
        admin_token = _register_and_login(client, "admin@example.com")
        expert1_token = _register_and_login(client, "expert1@example.com")
        expert2_token = _register_and_login(client, "expert2@example.com")
        project = _create_project(client, admin_token)
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=_auth_header(admin_token),
        )
        invite_token = invite_resp.json()["token"]

        # First expert accepts
        client.post(
            f"/api/v1/invitations/{invite_token}/accept",
            headers=_auth_header(expert1_token),
        )

        # WHEN - second expert tries to accept same invitation
        response = client.post(
            f"/api/v1/invitations/{invite_token}/accept",
            headers=_auth_header(expert2_token),
        )

        # THEN
        assert response.status_code == 400
        assert "already been used" in response.json()["detail"]

    def test_accept_invitation_already_member(self, client):
        """409 returned when user is already a member."""
        # GIVEN
        admin_token = _register_and_login(client, "admin@example.com")
        project = _create_project(client, admin_token)
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=_auth_header(admin_token),
        )
        invite_token = invite_resp.json()["token"]

        # WHEN - admin tries to accept (already a member)
        response = client.post(
            f"/api/v1/invitations/{invite_token}/accept",
            headers=_auth_header(admin_token),
        )

        # THEN
        assert response.status_code == 409
        assert "already a member" in response.json()["detail"]

    def test_accept_invitation_without_auth(self, client):
        """401 returned when not authenticated."""
        # GIVEN
        token = _register_and_login(client)
        project = _create_project(client, token)
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=_auth_header(token),
        )
        invite_token = invite_resp.json()["token"]

        # WHEN
        response = client.post(f"/api/v1/invitations/{invite_token}/accept")

        # THEN
        assert response.status_code == 401


class TestInvitationFlow:
    """Integration tests for complete invitation flow."""

    def test_full_invitation_flow(self, client):
        """Complete flow: create invitation -> get info -> accept."""
        # GIVEN
        admin_token = _register_and_login(client, "admin@example.com")
        expert_token = _register_and_login(client, "expert@example.com")
        project = _create_project(client, admin_token, "Decision Project")

        # Step 1: Admin creates invitation
        invite_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={"expires_in_days": 14},
            headers=_auth_header(admin_token),
        )
        assert invite_resp.status_code == 201
        invite_token = invite_resp.json()["token"]

        # Step 2: Expert views invitation info (no auth)
        info_resp = client.get(f"/api/v1/invitations/{invite_token}")
        assert info_resp.status_code == 200
        info = info_resp.json()
        assert info["project_name"] == "Decision Project"
        assert info["is_valid"] is True

        # Step 3: Expert accepts invitation
        accept_resp = client.post(
            f"/api/v1/invitations/{invite_token}/accept",
            headers=_auth_header(expert_token),
        )
        assert accept_resp.status_code == 201
        assert accept_resp.json()["role"] == "expert"

        # Step 4: Verify expert is now a member
        members_resp = client.get(
            f"/api/v1/projects/{project['id']}/members",
            headers=_auth_header(admin_token),
        )
        assert members_resp.status_code == 200
        members = members_resp.json()
        assert len(members) == 2
        emails = [m["email"] for m in members]
        assert "admin@example.com" in emails
        assert "expert@example.com" in emails

        # Step 5: Invitation is now invalid
        info_resp2 = client.get(f"/api/v1/invitations/{invite_token}")
        assert info_resp2.json()["is_valid"] is False

    def test_multiple_invitations_same_project(self, client):
        """Multiple invitations can be created for same project."""
        # GIVEN
        admin_token = _register_and_login(client, "admin@example.com")
        expert1_token = _register_and_login(client, "expert1@example.com")
        expert2_token = _register_and_login(client, "expert2@example.com")
        project = _create_project(client, admin_token)

        # Create two invitations
        invite1_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=_auth_header(admin_token),
        )
        invite2_resp = client.post(
            f"/api/v1/projects/{project['id']}/invite",
            json={},
            headers=_auth_header(admin_token),
        )
        token1 = invite1_resp.json()["token"]
        token2 = invite2_resp.json()["token"]
        assert token1 != token2

        # Both experts can accept their respective invitations
        accept1 = client.post(
            f"/api/v1/invitations/{token1}/accept",
            headers=_auth_header(expert1_token),
        )
        accept2 = client.post(
            f"/api/v1/invitations/{token2}/accept",
            headers=_auth_header(expert2_token),
        )
        assert accept1.status_code == 201
        assert accept2.status_code == 201

        # Project now has 3 members
        get_resp = client.get(
            f"/api/v1/projects/{project['id']}",
            headers=_auth_header(admin_token),
        )
        assert get_resp.json()["member_count"] == 3
