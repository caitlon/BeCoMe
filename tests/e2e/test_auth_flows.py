"""E2E tests for authentication flows: refresh, logout, wrong credentials."""

import pytest

from tests.e2e.conftest import (
    DEFAULT_PASSWORD,
    auth_headers,
    register_user,
    unique_email,
)


@pytest.mark.e2e
class TestTokenRefresh:
    """Refresh token must return a new valid access token."""

    def test_refresh_token_returns_new_access_token(self, http_client):
        """Login → use refresh_token → get new access_token → access protected resource."""
        # GIVEN — a registered user with login tokens
        email = unique_email("refresh")
        http_client.post(
            "/auth/register",
            json={
                "email": email,
                "password": DEFAULT_PASSWORD,
                "first_name": "Refresh",
                "last_name": "Tester",
            },
        ).raise_for_status()

        login_resp = http_client.post(
            "/auth/login",
            data={"username": email, "password": DEFAULT_PASSWORD},
        )
        login_resp.raise_for_status()
        tokens = login_resp.json()
        refresh_token = tokens["refresh_token"]
        assert refresh_token, "Login must return a refresh_token"

        # WHEN — request a new access token via refresh endpoint
        refresh_resp = http_client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        # THEN — new access token works
        assert refresh_resp.status_code == 200
        new_access_token = refresh_resp.json()["access_token"]
        assert new_access_token

        me_resp = http_client.get("/users/me", headers=auth_headers(new_access_token))
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == email


@pytest.mark.e2e
class TestLogout:
    """Logout must revoke the access token."""

    def test_logout_revokes_token(self, http_client):
        """Login → logout → old token returns 401."""
        # GIVEN — a logged-in user
        email = unique_email("logout")
        token = register_user(http_client, email)

        # Verify token works before logout
        me_resp = http_client.get("/users/me", headers=auth_headers(token))
        assert me_resp.status_code == 200

        # WHEN — user logs out
        logout_resp = http_client.post("/auth/logout", headers=auth_headers(token))

        # THEN — token is revoked
        assert logout_resp.status_code == 204

        me_after = http_client.get("/users/me", headers=auth_headers(token))
        assert me_after.status_code == 401


@pytest.mark.e2e
class TestWrongCredentials:
    """Login with wrong password must return 401."""

    def test_wrong_password_returns_401(self, http_client):
        """Registered user tries to login with wrong password."""
        # GIVEN — a registered user
        email = unique_email("wrongpw")
        register_user(http_client, email)

        # WHEN — login with wrong password
        response = http_client.post(
            "/auth/login",
            data={"username": email, "password": "CompletelyWrong1!"},
        )

        # THEN
        assert response.status_code == 401


@pytest.mark.e2e
class TestTamperedToken:
    """Tampered access token must be rejected; refresh must still work."""

    def test_tampered_token_returns_401_then_refresh_works(self, http_client):
        """Corrupted access token → 401, then refresh → new valid token."""
        # GIVEN — a registered user with tokens
        email = unique_email("tamper")
        http_client.post(
            "/auth/register",
            json={
                "email": email,
                "password": DEFAULT_PASSWORD,
                "first_name": "Tamper",
                "last_name": "Tester",
            },
        ).raise_for_status()

        login_resp = http_client.post(
            "/auth/login",
            data={"username": email, "password": DEFAULT_PASSWORD},
        )
        login_resp.raise_for_status()
        tokens = login_resp.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # WHEN — use a tampered access token
        tampered = access_token + "TAMPERED"
        me_resp = http_client.get("/users/me", headers=auth_headers(tampered))

        # THEN — rejected with 401
        assert me_resp.status_code == 401

        # AND — refresh still works
        refresh_resp = http_client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_resp.status_code == 200
        new_token = refresh_resp.json()["access_token"]

        me_after = http_client.get("/users/me", headers=auth_headers(new_token))
        assert me_after.status_code == 200
        assert me_after.json()["email"] == email
