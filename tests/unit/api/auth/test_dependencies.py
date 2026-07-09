"""Unit tests for authentication dependencies."""

import asyncio
from unittest.mock import MagicMock, patch
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException

from api.auth.dependencies import get_current_token_payload, get_current_user
from api.auth.jwt import ALGORITHM, create_access_token, revoke_token
from api.auth.revocation_store import InMemoryRevocationStore
from api.config import get_settings
from api.logging_context import get_user_id
from api.services.user_cache import InMemoryUserCache


@pytest.fixture
def store() -> InMemoryRevocationStore:
    """Provide a fresh in-memory revocation store per test."""
    return InMemoryRevocationStore()


@pytest.fixture
def cache() -> InMemoryUserCache:
    """Provide a fresh, empty in-memory user cache per test."""
    return InMemoryUserCache()


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    def test_returns_user_for_valid_token(self, store, cache):
        """Valid token returns corresponding user."""
        # GIVEN
        user_id = uuid4()
        token = create_access_token(user_id)
        mock_session = MagicMock()
        mock_user = MagicMock()
        mock_user.id = user_id

        # WHEN
        with patch("api.auth.dependencies.UserService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_by_id.return_value = mock_user
            mock_service_class.return_value = mock_service

            result = asyncio.run(get_current_user(token, mock_session, store, cache))

        # THEN
        assert result == mock_user
        mock_service.get_by_id.assert_called_once_with(user_id)

    def test_binds_user_id_to_logging_context(self, store, cache):
        """A successful resolution binds the acting user ID to the context."""
        # GIVEN
        user_id = uuid4()
        token = create_access_token(user_id)
        mock_session = MagicMock()
        mock_user = MagicMock()
        mock_user.id = user_id

        async def resolve_then_read() -> str | None:
            with patch("api.auth.dependencies.UserService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_by_id.return_value = mock_user
                mock_service_class.return_value = mock_service
                await get_current_user(token, mock_session, store, cache)
            return get_user_id()

        # WHEN
        bound = asyncio.run(resolve_then_read())

        # THEN
        assert bound == str(user_id)

    def test_raises_401_for_invalid_token(self, store, cache):
        """Invalid token raises HTTPException 401."""
        # GIVEN
        invalid_token = "invalid.token.here"
        mock_session = MagicMock()

        # WHEN / THEN
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(invalid_token, mock_session, store, cache))

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    def test_raises_401_for_nonexistent_user(self, store, cache):
        """Valid token but non-existent user raises HTTPException 401."""
        # GIVEN
        user_id = uuid4()
        token = create_access_token(user_id)
        mock_session = MagicMock()

        # WHEN
        with patch("api.auth.dependencies.UserService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_by_id.return_value = None  # User not found
            mock_service_class.return_value = mock_service

            # THEN
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(get_current_user(token, mock_session, store, cache))

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    def test_raises_401_for_revoked_token(self, store, cache):
        """Revoked token raises HTTPException 401."""
        # GIVEN
        user_id = uuid4()
        token = create_access_token(user_id)
        mock_session = MagicMock()

        # Extract JTI and revoke
        settings = get_settings()
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        revoke_token(payload["jti"], store)

        # WHEN / THEN
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(token, mock_session, store, cache))

        assert exc_info.value.status_code == 401


class TestGetCurrentTokenPayload:
    """Tests for get_current_token_payload dependency."""

    def test_returns_payload_for_valid_token(self, store):
        """Valid token returns TokenPayload."""
        # GIVEN
        user_id = uuid4()
        token = create_access_token(user_id)

        # WHEN
        payload = get_current_token_payload(token, store)

        # THEN
        assert payload.user_id == user_id
        assert payload.token_type == "access"
        assert payload.jti is not None

    def test_raises_401_for_invalid_token(self, store):
        """Invalid token raises HTTPException 401."""
        # GIVEN
        invalid_token = "invalid.token.here"

        # WHEN / THEN
        with pytest.raises(HTTPException) as exc_info:
            get_current_token_payload(invalid_token, store)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    def test_raises_401_for_malformed_token(self, store):
        """Malformed token raises HTTPException 401."""
        # GIVEN
        malformed_token = "not-a-jwt"

        # WHEN / THEN
        with pytest.raises(HTTPException) as exc_info:
            get_current_token_payload(malformed_token, store)

        assert exc_info.value.status_code == 401

    def test_raises_401_for_revoked_token(self, store):
        """Revoked token raises HTTPException 401."""
        # GIVEN
        user_id = uuid4()
        token = create_access_token(user_id)

        # Extract JTI and revoke
        settings = get_settings()
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        revoke_token(payload["jti"], store)

        # WHEN / THEN
        with pytest.raises(HTTPException) as exc_info:
            get_current_token_payload(token, store)

        assert exc_info.value.status_code == 401
