"""JWT token creation and decoding."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from jose import JWTError, jwt

from api.config import get_settings

ALGORITHM = "HS256"


class TokenError(Exception):
    """Raised when token validation fails."""


def create_access_token(user_id: UUID) -> str:
    """Create a JWT access token for a user.

    Includes standard claims:
    - sub: subject (user ID)
    - exp: expiration time
    - iat: issued at time
    - jti: unique token ID (for future revocation support)
    - type: token type (access)

    :param user_id: User's UUID
    :return: Encoded JWT token string
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(hours=settings.access_token_expire_hours)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "jti": uuid4().hex,  # Unique token ID for revocation support
        "type": "access",
    }
    encoded: str = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return encoded


def decode_access_token(token: str) -> UUID:
    """Decode and validate a JWT access token.

    Validates:
    - Signature (via secret key)
    - Expiration (exp claim)
    - Issued at (iat claim)
    - Token type (must be 'access')
    - Subject presence (sub claim)

    :param token: JWT token string
    :return: User UUID from token
    :raises TokenError: If token is invalid or expired
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

        # Validate token type
        token_type: str | None = payload.get("type")
        if token_type != "access":
            raise TokenError("Invalid token type")

        # Extract and validate user ID
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            raise TokenError("Missing user ID in token")

        return UUID(user_id_str)
    except JWTError as e:
        raise TokenError("Invalid or expired token") from e
    except ValueError as e:
        raise TokenError("Invalid user ID in token") from e
