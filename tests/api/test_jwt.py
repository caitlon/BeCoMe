"""Unit tests for JWT token creation and validation."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest

from api.auth.jwt import ALGORITHM, TokenError, create_access_token, decode_access_token


class TestCreateAccessToken:
    """Tests for create_access_token function."""

    def test_creates_valid_token(self):
        """Token creation returns a non-empty string."""
        # GIVEN
        user_id = uuid4()

        # WHEN
        token = create_access_token(user_id)

        # THEN
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_three_parts(self):
        """JWT token has header.payload.signature format."""
        # GIVEN
        user_id = uuid4()

        # WHEN
        token = create_access_token(user_id)

        # THEN
        parts = token.split(".")
        assert len(parts) == 3


class TestDecodeAccessToken:
    """Tests for decode_access_token function."""

    def test_decodes_valid_token(self):
        """Valid token returns correct user_id."""
        # GIVEN
        user_id = uuid4()
        token = create_access_token(user_id)

        # WHEN
        decoded_id = decode_access_token(token)

        # THEN
        assert decoded_id == user_id

    def test_invalid_token_raises_error(self):
        """Invalid token string raises TokenError."""
        # GIVEN
        invalid_token = "invalid.token.string"

        # WHEN / THEN
        with pytest.raises(TokenError, match="Invalid or expired token"):
            decode_access_token(invalid_token)

    def test_malformed_token_raises_error(self):
        """Malformed token raises TokenError."""
        # GIVEN
        malformed_token = "not-a-jwt"

        # WHEN / THEN
        with pytest.raises(TokenError, match="Invalid or expired token"):
            decode_access_token(malformed_token)

    def test_expired_token_raises_error(self):
        """Expired token raises TokenError."""
        # GIVEN
        user_id = uuid4()

        # Create token that expired in the past
        with patch("api.auth.jwt.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime.now(UTC) - timedelta(hours=48)
            mock_datetime.side_effect = datetime
            token = create_access_token(user_id)

        # WHEN / THEN
        with pytest.raises(TokenError, match="Invalid or expired token"):
            decode_access_token(token)

    def test_token_with_invalid_uuid_raises_error(self):
        """Token with invalid UUID in sub claim raises TokenError."""
        from jose import jwt

        from api.config import get_settings

        # GIVEN
        settings = get_settings()
        payload = {
            "sub": "not-a-valid-uuid",
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
            "jti": "test-jti-123",
            "type": "access",
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

        # WHEN / THEN
        with pytest.raises(TokenError, match="Invalid user ID in token"):
            decode_access_token(token)

    def test_token_with_wrong_type_raises_error(self):
        """Token with wrong type claim raises TokenError."""
        from jose import jwt

        from api.config import get_settings

        # GIVEN
        settings = get_settings()
        user_id = uuid4()
        payload = {
            "sub": str(user_id),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
            "jti": "test-jti-789",
            "type": "refresh",  # Wrong type
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

        # WHEN / THEN
        with pytest.raises(TokenError, match="Invalid token type"):
            decode_access_token(token)

    def test_token_without_sub_raises_error(self):
        """Token missing sub claim raises TokenError."""
        from jose import jwt

        from api.config import get_settings

        # GIVEN
        settings = get_settings()
        payload = {
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
            "jti": "test-jti-456",
            "type": "access",
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

        # WHEN / THEN
        with pytest.raises(TokenError, match="Missing user ID in token"):
            decode_access_token(token)
