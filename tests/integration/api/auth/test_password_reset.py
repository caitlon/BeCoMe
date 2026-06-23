"""Integration tests for the password reset endpoints.

Uses shared fixtures from conftest.py (client, client_with_session). A fake email
sender captures the raw reset token, which the API never returns in a response.
"""

import hashlib
from datetime import timedelta

import pytest
from sqlmodel import select

from api.db.models import PasswordResetToken, User
from api.db.utils import utc_now
from api.dependencies import get_email_service
from tests.shared.helpers import DEFAULT_TEST_PASSWORD

NEW_PASSWORD = "BrandNewPass456!"


class FakeEmailSender:
    """Record password-reset sends so a test can read back the raw token."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
        """Capture the call instead of sending an email."""
        self.calls.append({"to_email": to_email, "reset_url": reset_url})


@pytest.fixture
def fake_email(client):
    """Install a fake email sender on the app and return it."""
    sender = FakeEmailSender()
    client.app.dependency_overrides[get_email_service] = lambda: sender
    return sender


def _register(client, email: str = "user@example.com") -> None:
    """Register a user with the default test password."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": DEFAULT_TEST_PASSWORD,
            "first_name": "Test",
            "last_name": "User",
        },
    )


def _captured_token(sender: FakeEmailSender) -> str:
    """Extract the raw reset token from the last captured reset URL."""
    reset_url = sender.calls[-1]["reset_url"]
    return reset_url.split("token=")[1]


class TestForgotPassword:
    """Tests for POST /api/v1/auth/forgot-password."""

    def test_returns_202_and_sends_for_existing_user(self, client, fake_email):
        """A known email gets a 202 and triggers exactly one send."""
        # GIVEN
        _register(client, "user@example.com")

        # WHEN
        response = client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})

        # THEN
        assert response.status_code == 202
        assert len(fake_email.calls) == 1
        assert fake_email.calls[0]["to_email"] == "user@example.com"

    def test_returns_202_without_sending_for_unknown_email(self, client, fake_email):
        """An unknown email gets a 202 but triggers no send (anti-enumeration)."""
        # WHEN
        response = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})

        # THEN
        assert response.status_code == 202
        assert fake_email.calls == []

    def test_response_identical_for_known_and_unknown(self, client, fake_email):
        """Status and body are identical whether or not the email exists."""
        # GIVEN
        _register(client, "known@example.com")

        # WHEN
        known = client.post("/api/v1/auth/forgot-password", json={"email": "known@example.com"})
        unknown = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@example.com"})

        # THEN
        assert known.status_code == unknown.status_code == 202
        assert known.json() == unknown.json()


class TestResetPassword:
    """Tests for POST /api/v1/auth/reset-password."""

    def test_full_round_trip(self, client, fake_email):
        """Reset swaps the password: the old one fails and the new one logs in."""
        # GIVEN
        _register(client, "user@example.com")
        client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
        token = _captured_token(fake_email)

        # WHEN
        reset = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": NEW_PASSWORD},
        )

        # THEN
        assert reset.status_code == 204
        old_login = client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": DEFAULT_TEST_PASSWORD},
        )
        assert old_login.status_code == 401
        new_login = client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": NEW_PASSWORD},
        )
        assert new_login.status_code == 200

    def test_rejects_unknown_token(self, client):
        """An unknown token is rejected with 400."""
        # WHEN
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "garbage-token", "new_password": NEW_PASSWORD},
        )

        # THEN
        assert response.status_code == 400

    def test_rejects_reused_token(self, client, fake_email):
        """A token cannot be redeemed twice."""
        # GIVEN
        _register(client, "user@example.com")
        client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
        token = _captured_token(fake_email)
        first = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": NEW_PASSWORD},
        )
        assert first.status_code == 204

        # WHEN
        second = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "EvenNewerPass789!"},
        )

        # THEN
        assert second.status_code == 400

    def test_rejects_weak_password(self, client, fake_email):
        """A weak new password is rejected by schema validation with 422."""
        # GIVEN
        _register(client, "user@example.com")
        client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
        token = _captured_token(fake_email)

        # WHEN
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "weak"},
        )

        # THEN
        assert response.status_code == 422

    def test_rejects_expired_token(self, client_with_session):
        """An expired token is rejected with 400."""
        # GIVEN
        client, session = client_with_session
        _register(client, "user@example.com")
        user = session.exec(select(User).where(User.email == "user@example.com")).first()
        raw = "expired-integration-token"
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                expires_at=utc_now() - timedelta(minutes=1),
            )
        )
        session.commit()

        # WHEN
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw, "new_password": NEW_PASSWORD},
        )

        # THEN
        assert response.status_code == 400
