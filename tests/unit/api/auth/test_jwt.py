"""Unit tests for JWT token creation and validation."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from api.auth.jwt import (
    ALGORITHM,
    TokenError,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_access_token,
    decode_refresh_token,
    revoke_token,
)
from api.auth.token_blacklist import TokenBlacklist
from tests.unit.api.conftest import mock_datetime_offset


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
        with mock_datetime_offset("api.auth.jwt.datetime", timedelta(hours=48)):
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

    def test_token_without_jti_raises_error(self):
        """Token missing jti claim raises TokenError."""
        from jose import jwt

        from api.config import get_settings

        # GIVEN
        settings = get_settings()
        user_id = uuid4()
        payload = {
            "sub": str(user_id),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
            "type": "access",
            # No jti
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

        # WHEN / THEN
        with pytest.raises(TokenError, match="Missing token ID"):
            decode_access_token(token)

    def test_token_without_exp_raises_error(self):
        """Token missing exp claim raises TokenError."""
        from jose import jwt

        from api.config import get_settings

        # GIVEN
        settings = get_settings()
        user_id = uuid4()
        payload = {
            "sub": str(user_id),
            "iat": datetime.now(UTC),
            "jti": "test-jti-no-exp",
            "type": "access",
            # No exp
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

        # WHEN / THEN - jose library raises JWTError for missing exp due to require_exp=True
        with pytest.raises(TokenError, match="Invalid or expired token"):
            decode_access_token(token)


class TestCreateRefreshToken:
    """Tests for create_refresh_token function."""

    def test_creates_valid_refresh_token(self):
        """Refresh token creation returns a non-empty string and jti."""
        # GIVEN
        user_id = uuid4()

        # WHEN
        token, jti = create_refresh_token(user_id)

        # THEN
        assert isinstance(token, str)
        assert len(token) > 0
        assert isinstance(jti, str)
        assert len(jti) > 0

    def test_returns_tuple_with_jti(self):
        """Refresh token returns tuple of (token, jti)."""
        # GIVEN
        user_id = uuid4()

        # WHEN
        result = create_refresh_token(user_id)

        # THEN
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_token_has_correct_type_claim(self):
        """Refresh token has 'refresh' type in payload."""
        from jose import jwt

        from api.config import get_settings

        # GIVEN
        user_id = uuid4()
        settings = get_settings()

        # WHEN
        token, _ = create_refresh_token(user_id)

        # THEN
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
        assert payload["type"] == "refresh"

    def test_token_contains_user_id(self):
        """Refresh token contains correct user_id in sub claim."""
        from jose import jwt

        from api.config import get_settings

        # GIVEN
        user_id = uuid4()
        settings = get_settings()

        # WHEN
        token, _ = create_refresh_token(user_id)

        # THEN
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
        assert payload["sub"] == str(user_id)


class TestCreateTokenPair:
    """Tests for create_token_pair function."""

    def test_creates_both_tokens(self):
        """Token pair contains both access and refresh tokens."""
        # GIVEN
        user_id = uuid4()

        # WHEN
        pair = create_token_pair(user_id)

        # THEN
        assert pair.access_token is not None
        assert pair.refresh_token is not None
        assert len(pair.access_token) > 0
        assert len(pair.refresh_token) > 0

    def test_tokens_share_same_jti(self):
        """Access and refresh tokens share the same JTI."""
        from jose import jwt

        from api.config import get_settings

        # GIVEN
        user_id = uuid4()
        settings = get_settings()

        # WHEN
        pair = create_token_pair(user_id)

        # THEN
        access_payload = jwt.decode(
            pair.access_token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
        refresh_payload = jwt.decode(
            pair.refresh_token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
        assert access_payload["jti"] == refresh_payload["jti"]

    def test_expires_in_matches_settings(self):
        """Token pair expires_in matches access token settings."""
        from api.config import get_settings

        # GIVEN
        user_id = uuid4()
        settings = get_settings()

        # WHEN
        pair = create_token_pair(user_id)

        # THEN
        expected_seconds = settings.access_token_expire_minutes * 60
        assert pair.expires_in == expected_seconds

    def test_token_type_is_bearer(self):
        """Token pair has 'bearer' token type."""
        # GIVEN
        user_id = uuid4()

        # WHEN
        pair = create_token_pair(user_id)

        # THEN
        assert pair.token_type == "bearer"


class TestDecodeRefreshToken:
    """Tests for decode_refresh_token function."""

    def test_decodes_valid_refresh_token(self):
        """Valid refresh token returns TokenPayload with correct data."""
        # GIVEN
        user_id = uuid4()
        token, expected_jti = create_refresh_token(user_id)

        # WHEN
        payload = decode_refresh_token(token)

        # THEN
        assert payload.user_id == user_id
        assert payload.jti == expected_jti
        assert payload.token_type == "refresh"

    def test_rejects_access_token(self):
        """Access token is rejected when decoded as refresh token."""
        # GIVEN
        user_id = uuid4()
        access_token = create_access_token(user_id)

        # WHEN / THEN
        with pytest.raises(TokenError, match="Invalid token type"):
            decode_refresh_token(access_token)

    def test_rejects_expired_refresh_token(self):
        """Expired refresh token raises TokenError."""
        # GIVEN
        user_id = uuid4()

        # Create token that expired in the past
        with mock_datetime_offset("api.auth.jwt.datetime", timedelta(days=30)):
            token, _ = create_refresh_token(user_id)

        # WHEN / THEN
        with pytest.raises(TokenError, match="Invalid or expired token"):
            decode_refresh_token(token)


class TestRevokeToken:
    """Tests for revoke_token function."""

    def setup_method(self):
        """Reset blacklist before each test."""
        TokenBlacklist.reset()

    def test_adds_to_blacklist(self):
        """Revoked token JTI is added to blacklist."""
        # GIVEN
        jti = "test-jti-revoke-123"

        # WHEN
        revoke_token(jti)

        # THEN
        assert TokenBlacklist.is_blacklisted(jti) is True

    def test_revoked_token_cannot_be_decoded(self):
        """Token with revoked JTI cannot be decoded."""
        # GIVEN
        user_id = uuid4()
        token, jti = create_refresh_token(user_id)

        # WHEN
        revoke_token(jti)

        # THEN
        with pytest.raises(TokenError, match="Token has been revoked"):
            decode_refresh_token(token)

    def test_revoked_access_token_cannot_be_decoded(self):
        """Access token sharing revoked JTI cannot be decoded."""
        # GIVEN
        user_id = uuid4()
        pair = create_token_pair(user_id)

        # Extract JTI from access token
        from jose import jwt

        from api.config import get_settings

        settings = get_settings()
        payload = jwt.decode(
            pair.access_token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
        jti = payload["jti"]

        # WHEN
        revoke_token(jti)

        # THEN
        with pytest.raises(TokenError, match="Token has been revoked"):
            decode_access_token(pair.access_token)
