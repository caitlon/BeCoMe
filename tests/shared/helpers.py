"""Shared constants and helpers used across unit and integration tests."""

import secrets
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlmodel import Session

from api.auth.password import hash_password
from api.data.example_project import EXAMPLE_EXPERTS
from api.db.models import User
from api.db.utils import utc_now

# Shared test password constant to avoid coupling between helpers and tests
DEFAULT_TEST_PASSWORD = "SecurePass123!"


def auth_header(token: str) -> dict[str, str]:
    """Create authorization header from token.

    :param token: JWT access token
    :return: Headers dict with Bearer authorization
    """
    return {"Authorization": f"Bearer {token}"}


@contextmanager
def mock_datetime_offset(module_path: str, offset: timedelta):
    """Mock datetime.now() to return a time shifted by offset.

    Uses wraps=datetime to preserve classmethods like fromtimestamp() while
    overriding now(). Used to test token expiration by creating tokens "in the past".

    :param module_path: Full module path to mock (e.g., "api.auth.jwt.datetime")
    :param offset: Timedelta to subtract from current time (positive = past)

    Example:
        with mock_datetime_offset("api.auth.jwt.datetime", timedelta(hours=48)):
            token = create_access_token(user_id)  # Created 48 hours ago
    """
    with patch(module_path, wraps=datetime) as mock_dt:
        mock_dt.now.return_value = datetime.now(UTC) - offset
        yield mock_dt


def insert_demo_experts(session: Session) -> None:
    """Create the pool of demo accounts the example project's opinions belong to.

    Production gets the pool from the migration that added it. Tests build their
    schema with ``SQLModel.metadata.create_all``, which carries no data, so they call
    this instead. The rows match the migration: already verified, and holding a
    password hash whose plaintext is never kept.

    :param session: Session to insert into; this function commits.
    """
    unusable_password = hash_password(secrets.token_urlsafe(64))
    for expert in EXAMPLE_EXPERTS:
        session.add(
            User(
                id=expert.user_id,
                email=expert.email,
                hashed_password=unusable_password,
                first_name=expert.first_name,
                last_name=expert.last_name,
                email_verified_at=utc_now(),
                is_demo=True,
            )
        )
    session.commit()
