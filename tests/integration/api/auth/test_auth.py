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
        assert data["refresh_token"]  # rotation returns a fresh refresh token
        assert data["expires_in"] > 0

    def test_refresh_rotates_and_reuse_revokes_the_family(self, client):
        """Refresh rotates the pair; reusing the old token revokes the whole family."""
        # GIVEN - register and login
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "rotate@example.com",
                "password": "SecurePass123!",
                "first_name": "Rot",
                "last_name": "Ate",
            },
        )
        login = client.post(
            "/api/v1/auth/login",
            data={"username": "rotate@example.com", "password": "SecurePass123!"},
        )
        old_refresh = login.json()["refresh_token"]

        # WHEN - first refresh returns a fresh pair
        first = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert first.status_code == 200
        new_refresh = first.json()["refresh_token"]
        assert new_refresh and new_refresh != old_refresh

        # THEN - reusing the old refresh token is rejected and revokes the whole family
        reused = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert reused.status_code == 401

        # AND - reuse detection revoked the session, so the rotated token also stops working
        again = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
        assert again.status_code == 401

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


class TestLoginLockout:
    """Repeated failed logins lock the account for a cooldown."""

    def test_locks_account_after_repeated_failures(self, client):
        """After too many wrong-password attempts, further logins return 429."""
        from api.auth.login_throttle import InMemoryLoginThrottle, get_login_throttle

        throttle = InMemoryLoginThrottle(max_failures=3, window_seconds=3600)
        client.app.dependency_overrides[get_login_throttle] = lambda: throttle
        try:
            client.post(
                "/api/v1/auth/register",
                json={
                    "email": "lockout@example.com",
                    "password": "SecurePass123!",
                    "first_name": "Lock",
                    "last_name": "Out",
                },
            )
            # GIVEN three failed attempts, each rejected with 401
            for _ in range(3):
                failed = client.post(
                    "/api/v1/auth/login",
                    data={"username": "lockout@example.com", "password": "WrongPass999!"},
                )
                assert failed.status_code == 401

            # WHEN a fourth attempt is made, even with the correct password
            locked = client.post(
                "/api/v1/auth/login",
                data={"username": "lockout@example.com", "password": "SecurePass123!"},
            )

            # THEN the account is locked out
            assert locked.status_code == 429
        finally:
            client.app.dependency_overrides.pop(get_login_throttle, None)


class TestLoginStoreUnavailable:
    """Login fails cleanly with 503 when the session store is down, never a raw 500."""

    def test_login_returns_503_when_session_store_is_down(self, client):
        """A RevocationStoreError while starting the session becomes a clean 503."""
        from unittest.mock import MagicMock

        from api.auth.revocation_store import RevocationStoreError, get_revocation_store

        client.post(
            "/api/v1/auth/register",
            json={
                "email": "storedown@example.com",
                "password": "SecurePass123!",
                "first_name": "Store",
                "last_name": "Down",
            },
        )
        broken = MagicMock()
        broken.start_session.side_effect = RevocationStoreError("redis down")
        client.app.dependency_overrides[get_revocation_store] = lambda: broken
        try:
            response = client.post(
                "/api/v1/auth/login",
                data={"username": "storedown@example.com", "password": "SecurePass123!"},
            )
            assert response.status_code == 503
        finally:
            client.app.dependency_overrides.pop(get_revocation_store, None)


class TestLogout:
    """Tests for POST /api/v1/auth/logout."""

    def test_logout_revokes_token(self, client):
        """Logout revokes the current token."""
        # GIVEN - register and login
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


class TestCookieAuth:
    """Login issues session cookies; the cookie authenticates and CSRF guards mutations."""

    PASSWORD = "SecurePass123!"

    def _register_and_login(self, cookie_client, email="cookie@example.com"):
        """Register a user and log in, leaving the session cookies in the client jar."""
        cookie_client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": self.PASSWORD,
                "first_name": "Cookie",
                "last_name": "User",
            },
        )
        return cookie_client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": self.PASSWORD},
        )

    def _csrf_header(self, cookie_client):
        """Echo the readable csrf_token cookie back as the X-CSRF-Token header."""
        return {"X-CSRF-Token": cookie_client.cookies.get("csrf_token")}

    def test_login_sets_httponly_session_cookies(self, cookie_client):
        """Login sets access/refresh/csrf cookies; token cookies are HttpOnly + SameSite=Strict."""
        resp = self._register_and_login(cookie_client)

        assert resp.status_code == 200
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies
        assert "csrf_token" in resp.cookies
        raw = " ".join(resp.headers.get_list("set-cookie")).lower()
        assert "httponly" in raw
        assert "samesite=strict" in raw

    def test_access_cookie_authenticates_without_bearer(self, cookie_client):
        """A request carrying only the session cookie (no Authorization header) authenticates."""
        self._register_and_login(cookie_client)  # the jar now holds the session cookies

        resp = cookie_client.get("/api/v1/auth/me")

        assert resp.status_code == 200
        assert resp.json()["email"] == "cookie@example.com"

    def test_logout_with_csrf_clears_cookies(self, cookie_client):
        """A logout carrying the CSRF header succeeds and clears the session cookies."""
        self._register_and_login(cookie_client)

        resp = cookie_client.post("/api/v1/auth/logout", headers=self._csrf_header(cookie_client))

        assert resp.status_code == 204
        raw = " ".join(resp.headers.get_list("set-cookie")).lower()
        assert "access_token=" in raw

    def test_cookie_mutation_without_csrf_header_is_rejected(self, cookie_client):
        """A cookie-authenticated mutation without the CSRF header is rejected with 403."""
        self._register_and_login(cookie_client)

        resp = cookie_client.post("/api/v1/auth/logout")

        assert resp.status_code == 403

    def test_cookie_mutation_with_wrong_csrf_header_is_rejected(self, cookie_client):
        """A cookie-authenticated mutation with a mismatched CSRF token is rejected with 403."""
        self._register_and_login(cookie_client)

        resp = cookie_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "wrong"})

        assert resp.status_code == 403

    def test_refresh_via_cookie_without_body(self, cookie_client):
        """The SPA refreshes using only the refresh cookie (no body) plus the CSRF header."""
        self._register_and_login(cookie_client)

        resp = cookie_client.post("/api/v1/auth/refresh", headers=self._csrf_header(cookie_client))

        assert resp.status_code == 200
        assert resp.json()["access_token"]

    def test_refresh_without_cookie_or_body_is_unauthorized(self, client):
        """A refresh with neither the refresh cookie nor a body token is rejected with 401."""
        resp = client.post("/api/v1/auth/refresh")

        assert resp.status_code == 401
