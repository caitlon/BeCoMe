"""JWT token creation and decoding with refresh token support."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from jose import JWTError, jwt

from api.auth.token_blacklist import TokenBlacklist
from api.config import get_settings

ALGORITHM = "HS256"


class TokenError(Exception):
    """Raised when token validation fails."""


@dataclass(frozen=True)
class TokenPair:
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 0  # Access token lifetime in seconds


@dataclass(frozen=True)
class TokenPayload:
    """Decoded token payload."""

    user_id: UUID
    jti: str
    token_type: str
    exp: datetime


def create_access_token(user_id: UUID, jti: str | None = None) -> str:
    """Create a JWT access token for a user.

    :param user_id: User's UUID
    :param jti: Optional JWT ID (generated if not provided)
    :return: Encoded JWT token string
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "jti": jti or uuid4().hex,
        "type": "access",
    }
    encoded: str = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return encoded


def create_refresh_token(user_id: UUID) -> tuple[str, str]:
    """Create a JWT refresh token for a user.

    :param user_id: User's UUID
    :return: Tuple of (encoded token, jti)
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.refresh_token_expire_days)
    jti = uuid4().hex
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "jti": jti,
        "type": "refresh",
    }
    encoded: str = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return encoded, jti


def create_token_pair(user_id: UUID) -> TokenPair:
    """Create both access and refresh tokens for a user.

    :param user_id: User's UUID
    :return: TokenPair with both tokens
    """
    settings = get_settings()
    refresh_token, jti = create_refresh_token(user_id)
    access_token = create_access_token(user_id, jti)
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


def decode_token(token: str, expected_type: str) -> TokenPayload:
    """Decode and validate a JWT token.

    :param token: JWT token string
    :param expected_type: Expected token type ('access' or 'refresh')
    :return: TokenPayload with decoded data
    :raises TokenError: If token is invalid, expired, or blacklisted
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "require_exp": True,
                "require_iat": True,
            },
        )

        token_type: str | None = payload.get("type")
        if token_type != expected_type:
            raise TokenError(f"Invalid token type: expected {expected_type}")

        jti: str | None = payload.get("jti")
        if not jti:
            raise TokenError("Missing token ID")

        # Check blacklist
        if TokenBlacklist.is_blacklisted(jti):
            raise TokenError("Token has been revoked")

        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            raise TokenError("Missing user ID in token")

        # exp is guaranteed by jose with require_exp=True
        exp_datetime = datetime.fromtimestamp(payload["exp"], tz=UTC)

        return TokenPayload(
            user_id=UUID(user_id_str),
            jti=jti,
            token_type=token_type,
            exp=exp_datetime,
        )
    except JWTError as e:
        raise TokenError("Invalid or expired token") from e
    except ValueError as e:
        raise TokenError("Invalid user ID in token") from e


def decode_access_token(token: str) -> UUID:
    """Decode and validate a JWT access token.

    :param token: JWT token string
    :return: User UUID from token
    :raises TokenError: If token is invalid or expired
    """
    payload = decode_token(token, "access")
    return payload.user_id


def decode_refresh_token(token: str) -> TokenPayload:
    """Decode and validate a JWT refresh token.

    :param token: JWT token string
    :return: TokenPayload with user_id, jti, and exp
    :raises TokenError: If token is invalid or expired
    """
    return decode_token(token, "refresh")


def revoke_token(jti: str) -> None:
    """Revoke a token by adding its JTI to the blacklist.

    Blacklists for the full refresh token lifetime to ensure that any
    refresh token sharing this JTI cannot be used after revocation,
    even if revocation was initiated using an access token.

    :param jti: JWT ID to revoke
    """
    settings = get_settings()
    blacklist_exp = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    TokenBlacklist.add(jti, blacklist_exp)
