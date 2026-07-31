"""Fixtures shared by the auth integration tests.

The transactional mails carry the only copy of a raw token, so every flow that mails a
link is tested through a recording sender rather than a real provider.
"""

import pytest

from api.dependencies import get_email_service
from api.services.email.base import EmailSender


class FakeEmailSender(EmailSender):
    """Record every send so a test can read back the raw token or notice links.

    Subclasses the real ``EmailSender`` ABC so a method the interface gains later
    fails loudly at instantiation (``TypeError: Can't instantiate abstract class``)
    instead of silently working until some test happens to hit the missing method.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
        self.verification_calls: list[dict[str, str]] = []
        self.notice_calls: list[dict[str, str]] = []

    async def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
        """Capture the call instead of sending an email."""
        self.calls.append({"to_email": to_email, "reset_url": reset_url})

    async def send_email_verification(self, *, to_email: str, verify_url: str) -> None:
        """Capture the call instead of sending an email."""
        self.verification_calls.append({"to_email": to_email, "verify_url": verify_url})

    async def send_registration_attempt_notice(
        self, *, to_email: str, login_url: str, reset_url: str
    ) -> None:
        """Capture the call instead of sending an email."""
        self.notice_calls.append(
            {"to_email": to_email, "login_url": login_url, "reset_url": reset_url}
        )


@pytest.fixture
def fake_email(client):
    """Install a fake email sender on the app and return it."""
    sender = FakeEmailSender()
    client.app.dependency_overrides[get_email_service] = lambda: sender
    return sender
