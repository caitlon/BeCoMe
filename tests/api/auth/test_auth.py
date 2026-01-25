"""Tests for authentication endpoints.

Uses shared fixtures from conftest.py (client, test_engine).
"""

from sqlmodel import select

from api.db.models import User


class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    def test_register_creates_user(self, client):
        """Registration with valid data creates user and returns profile."""
        # GIVEN
        payload = {
            "email": "test@example.com",
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert "id" in data
        assert "password" not in data
        assert "hashed_password" not in data

    def test_register_without_last_name_fails(self, client):
        """Registration without last_name returns 422."""
        # GIVEN
        payload = {
            "email": "jane@example.com",
            "password": "SecurePass123!",
            "first_name": "Jane",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422

    def test_register_duplicate_email_fails(self, client):
        """Registration with existing email returns 409."""
        # GIVEN - first registration
        payload = {
            "email": "duplicate@example.com",
            "password": "SecurePass123!",
            "first_name": "First",
            "last_name": "User",
        }
        client.post("/api/v1/auth/register", json=payload)

        # WHEN - second registration with same email
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    def test_register_duplicate_email_different_case_fails(self, client):
        """Registration with same email in different case returns 409."""
        # GIVEN - first registration with mixed case email
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "Test@Example.COM",
                "password": "SecurePass123!",
                "first_name": "First",
                "last_name": "User",
            },
        )

        # WHEN - second registration with lowercase email
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "SecurePass123!",
                "first_name": "Second",
                "last_name": "User",
            },
        )

        # THEN
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    def test_register_short_password_fails(self, client):
        """Registration with password < 12 chars returns 422."""
        # GIVEN
        payload = {
            "email": "short@example.com",
            "password": "short",
            "first_name": "Short",
            "last_name": "Pass",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422

    def test_register_password_without_uppercase_fails(self, client):
        """Registration with password missing uppercase letter returns 422."""
        # GIVEN
        payload = {
            "email": "nouppercase@example.com",
            "password": "password1234!",
            "first_name": "Test",
            "last_name": "User",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422
        assert "uppercase" in response.json()["detail"][0]["msg"].lower()

    def test_register_password_without_lowercase_fails(self, client):
        """Registration with password missing lowercase letter returns 422."""
        # GIVEN
        payload = {
            "email": "nolowercase@example.com",
            "password": "PASSWORD1234!",
            "first_name": "Test",
            "last_name": "User",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422
        assert "lowercase" in response.json()["detail"][0]["msg"].lower()

    def test_register_password_without_digit_fails(self, client):
        """Registration with password missing digit returns 422."""
        # GIVEN
        payload = {
            "email": "nodigit@example.com",
            "password": "PasswordABCD!",
            "first_name": "Test",
            "last_name": "User",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422
        assert "digit" in response.json()["detail"][0]["msg"].lower()

    def test_register_password_without_special_char_fails(self, client):
        """Registration with password missing special character returns 422."""
        # GIVEN
        payload = {
            "email": "nospecial@example.com",
            "password": "PasswordABCD1",
            "first_name": "Test",
            "last_name": "User",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422
        assert "special" in response.json()["detail"][0]["msg"].lower()

    def test_register_invalid_email_fails(self, client):
        """Registration with invalid email returns 422."""
        # GIVEN
        payload = {
            "email": "not-an-email",
            "password": "SecurePass123!",
            "first_name": "Bad",
            "last_name": "Email",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    def test_login_returns_token(self, client):
        """Login with valid credentials returns JWT token."""
        # GIVEN - register user first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "password": "SecurePass123!",
                "first_name": "Login",
                "last_name": "User",
            },
        )

        # WHEN - login with OAuth2 form data
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "login@example.com", "password": "SecurePass123!"},
        )

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password_fails(self, client):
        """Login with incorrect password returns 401."""
        # GIVEN
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpass@example.com",
                "password": "CorrectPass1!",
                "first_name": "Wrong",
                "last_name": "Pass",
            },
        )

        # WHEN
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "wrongpass@example.com", "password": "WrongPass999"},
        )

        # THEN
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_nonexistent_user_fails(self, client):
        """Login with non-existent email returns 401."""
        # WHEN
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "nobody@example.com", "password": "anypassword"},
        )

        # THEN
        assert response.status_code == 401

    def test_login_with_different_case_email_works(self, client):
        """Login works with email in different case than registered."""
        # GIVEN - register with mixed case
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "CaseTest@Example.COM",
                "password": "SecurePass123!",
                "first_name": "Case",
                "last_name": "Test",
            },
        )

        # WHEN - login with lowercase
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "casetest@example.com", "password": "SecurePass123!"},
        )

        # THEN
        assert response.status_code == 200
        assert "access_token" in response.json()


class TestMe:
    """Tests for GET /api/v1/auth/me."""

    def test_me_returns_profile(self, client):
        """Authenticated request returns user profile."""
        # GIVEN - register and login
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "me@example.com",
                "password": "SecurePass123!",
                "first_name": "Me",
                "last_name": "User",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": "me@example.com", "password": "SecurePass123!"},
        )
        token = login_response.json()["access_token"]

        # WHEN
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@example.com"
        assert data["first_name"] == "Me"
        assert data["last_name"] == "User"

    def test_me_without_token_fails(self, client):
        """Request without token returns 401."""
        # WHEN
        response = client.get("/api/v1/auth/me")

        # THEN
        assert response.status_code == 401

    def test_me_with_invalid_token_fails(self, client):
        """Request with invalid token returns 401."""
        # WHEN
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        # THEN
        assert response.status_code == 401

    def test_me_with_deleted_user_fails(self, client):
        """Request with valid token but deleted user returns 401."""
        # GIVEN - register, login, then delete user
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "deleted@example.com",
                "password": "SecurePass123!",
                "first_name": "Deleted",
                "last_name": "User",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": "deleted@example.com", "password": "SecurePass123!"},
        )
        token = login_response.json()["access_token"]

        # Delete user directly from database
        from api.db.session import get_session

        session = next(client.app.dependency_overrides[get_session]())
        user = session.exec(select(User).where(User.email == "deleted@example.com")).first()
        session.delete(user)
        session.commit()

        # WHEN - try to use token for deleted user
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        # THEN
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]


class TestEmailValidation:
    """Tests for email ASCII validation."""

    def test_register_email_with_cyrillic_fails(self, client):
        """Registration with Cyrillic email returns 422."""
        # GIVEN
        payload = {
            "email": "тест@example.com",
            "password": "SecurePass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422
        assert "ascii" in response.json()["detail"][0]["msg"].lower()

    def test_register_email_ascii_succeeds(self, client):
        """Registration with ASCII email succeeds."""
        # GIVEN
        payload = {
            "email": "test.user+tag@example.com",
            "password": "SecurePass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 201
        assert response.json()["email"] == "test.user+tag@example.com"


class TestNameValidation:
    """Tests for first_name and last_name validation."""

    def test_register_name_with_digits_fails(self, client):
        """Registration with digits in name returns 422."""
        # GIVEN
        payload = {
            "email": "digits@example.com",
            "password": "SecurePass123!",
            "first_name": "John123",
            "last_name": "Doe",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422
        assert "letters" in response.json()["detail"][0]["msg"].lower()

    def test_register_name_with_special_chars_fails(self, client):
        """Registration with special characters in name returns 422."""
        # GIVEN
        payload = {
            "email": "special@example.com",
            "password": "SecurePass123!",
            "first_name": "John@#$",
            "last_name": "Doe",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422

    def test_register_name_with_hyphen_succeeds(self, client):
        """Registration with hyphenated name succeeds."""
        # GIVEN
        payload = {
            "email": "hyphen@example.com",
            "password": "SecurePass123!",
            "first_name": "Jean-Pierre",
            "last_name": "Dupont",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 201
        assert response.json()["first_name"] == "Jean-Pierre"

    def test_register_name_with_apostrophe_succeeds(self, client):
        """Registration with apostrophe in name succeeds."""
        # GIVEN
        payload = {
            "email": "apostrophe@example.com",
            "password": "SecurePass123!",
            "first_name": "O'Brien",
            "last_name": "Smith",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 201
        assert response.json()["first_name"] == "O'Brien"

    def test_register_cyrillic_name_succeeds(self, client):
        """Registration with Cyrillic name succeeds."""
        # GIVEN
        payload = {
            "email": "cyrillic@example.com",
            "password": "SecurePass123!",
            "first_name": "Олег",
            "last_name": "Петров",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 201
        assert response.json()["first_name"] == "Олег"
        assert response.json()["last_name"] == "Петров"

    def test_register_name_with_space_succeeds(self, client):
        """Registration with space in name succeeds."""
        # GIVEN
        payload = {
            "email": "space@example.com",
            "password": "SecurePass123!",
            "first_name": "Anna Maria",
            "last_name": "Kowalski",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 201
        assert response.json()["first_name"] == "Anna Maria"

    def test_register_last_name_with_digits_fails(self, client):
        """Registration with digits in last name returns 422."""
        # GIVEN
        payload = {
            "email": "lastdigits@example.com",
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe123",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422

    def test_register_empty_last_name_fails(self, client):
        """Registration with empty last name returns 422."""
        # GIVEN
        payload = {
            "email": "emptylast@example.com",
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422


class TestProfileUpdate:
    """Tests for PUT /api/v1/users/me profile update validation."""

    def _get_auth_header(self, client) -> dict:
        """Register and login, return auth header."""
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "profile@example.com",
                "password": "SecurePass123!",
                "first_name": "Profile",
                "last_name": "User",
            },
        )
        login = client.post(
            "/api/v1/auth/login",
            data={"username": "profile@example.com", "password": "SecurePass123!"},
        )
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_update_profile_name_with_digits_fails(self, client):
        """Profile update with digits in name returns 422."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me",
            json={"first_name": "John123"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 422
        assert "letters" in response.json()["detail"][0]["msg"].lower()

    def test_update_profile_valid_name_succeeds(self, client):
        """Profile update with valid name succeeds."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me",
            json={"first_name": "Jean-Pierre", "last_name": "O'Connor"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 200
        assert response.json()["first_name"] == "Jean-Pierre"
        assert response.json()["last_name"] == "O'Connor"

    def test_update_profile_cyrillic_name_succeeds(self, client):
        """Profile update with Cyrillic name succeeds."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me",
            json={"first_name": "Алексей"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 200
        assert response.json()["first_name"] == "Алексей"

    def test_update_profile_empty_last_name_is_ignored(self, client):
        """Profile update with empty last name doesn't change it."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me",
            json={"last_name": ""},
            headers=headers,
        )

        # THEN - empty string converted to None means "no update"
        assert response.status_code == 200
        assert response.json()["last_name"] == "User"  # unchanged

    def test_update_profile_empty_first_name_is_ignored(self, client):
        """Profile update with empty first name doesn't change it."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me",
            json={"first_name": ""},
            headers=headers,
        )

        # THEN - empty string converted to None means "no update"
        assert response.status_code == 200
        assert response.json()["first_name"] == "Profile"  # unchanged


class TestPasswordChange:
    """Tests for PUT /api/v1/users/me/password validation."""

    def _get_auth_header(self, client) -> dict:
        """Register and login, return auth header."""
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "pwchange@example.com",
                "password": "OldSecure123!",
                "first_name": "Password",
                "last_name": "Change",
            },
        )
        login = client.post(
            "/api/v1/auth/login",
            data={"username": "pwchange@example.com", "password": "OldSecure123!"},
        )
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_change_password_without_uppercase_fails(self, client):
        """Password change without uppercase letter returns 422."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me/password",
            json={"current_password": "OldSecure123!", "new_password": "newpassword1!"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 422
        assert "uppercase" in response.json()["detail"][0]["msg"].lower()

    def test_change_password_without_lowercase_fails(self, client):
        """Password change without lowercase letter returns 422."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me/password",
            json={"current_password": "OldSecure123!", "new_password": "NEWPASSWORD1!"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 422
        assert "lowercase" in response.json()["detail"][0]["msg"].lower()

    def test_change_password_without_digit_fails(self, client):
        """Password change without digit returns 422."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me/password",
            json={"current_password": "OldSecure123!", "new_password": "NewPasswordAB!"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 422
        assert "digit" in response.json()["detail"][0]["msg"].lower()

    def test_change_password_without_special_char_fails(self, client):
        """Password change without special character returns 422."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me/password",
            json={"current_password": "OldSecure123!", "new_password": "NewPassword123"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 422
        assert "special" in response.json()["detail"][0]["msg"].lower()

    def test_change_password_valid_succeeds(self, client):
        """Password change with valid password succeeds."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me/password",
            json={"current_password": "OldSecure123!", "new_password": "NewSecure456!"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 204


class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh."""

    def test_refresh_returns_new_access_token(self, client):
        """Refresh with valid refresh token returns new access token."""
        # GIVEN - register and login
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@example.com",
                "password": "SecurePass123!",
                "first_name": "Refresh",
                "last_name": "User",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": "refresh@example.com", "password": "SecurePass123!"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # WHEN
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["expires_in"] > 0

    def test_refresh_with_invalid_token_fails(self, client):
        """Refresh with invalid token returns 401."""
        # WHEN
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.refresh.token"},
        )

        # THEN
        assert response.status_code == 401

    def test_refresh_with_access_token_fails(self, client):
        """Refresh with access token (wrong type) returns 401."""
        # GIVEN - register and login
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongtype@example.com",
                "password": "SecurePass123!",
                "first_name": "Wrong",
                "last_name": "Type",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": "wrongtype@example.com", "password": "SecurePass123!"},
        )
        access_token = login_response.json()["access_token"]

        # WHEN - try to use access token as refresh token
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )

        # THEN
        assert response.status_code == 401


class TestLogout:
    """Tests for POST /api/v1/auth/logout."""

    def test_logout_revokes_token(self, client):
        """Logout revokes the current token."""
        # GIVEN - register and login
        from api.auth.token_blacklist import TokenBlacklist

        TokenBlacklist.reset()

        client.post(
            "/api/v1/auth/register",
            json={
                "email": "logout@example.com",
                "password": "SecurePass123!",
                "first_name": "Logout",
                "last_name": "User",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": "logout@example.com", "password": "SecurePass123!"},
        )
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # WHEN - logout
        response = client.post("/api/v1/auth/logout", headers=headers)

        # THEN
        assert response.status_code == 204

        # AND - token should no longer work
        me_response = client.get("/api/v1/auth/me", headers=headers)
        assert me_response.status_code == 401

    def test_logout_without_token_fails(self, client):
        """Logout without token returns 401."""
        # WHEN
        response = client.post("/api/v1/auth/logout")

        # THEN
        assert response.status_code == 401

    def test_refresh_after_logout_fails(self, client):
        """Refresh token cannot be used after logout."""
        # GIVEN - register and login
        from api.auth.token_blacklist import TokenBlacklist

        TokenBlacklist.reset()

        client.post(
            "/api/v1/auth/register",
            json={
                "email": "logoutrefresh@example.com",
                "password": "SecurePass123!",
                "first_name": "Logout",
                "last_name": "Refresh",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": "logoutrefresh@example.com", "password": "SecurePass123!"},
        )
        tokens = login_response.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # WHEN - logout
        client.post("/api/v1/auth/logout", headers=headers)

        # THEN - refresh token should no longer work
        refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 401
