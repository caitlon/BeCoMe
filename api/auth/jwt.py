"""JWT token creation and decoding."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt  # type: ignore[import-untyped]

from api.config import get_settings

ALGORITHM = "HS256"


class TokenError(Exception):
    """Raised when token validation fails."""


def create_access_token(user_id: UUID) -> str:
    """Create a JWT access token for a user.

    :param user_id: User's UUID
    :return: Encoded JWT token string
    """
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(hours=settings.access_token_expire_hours)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
    }
    encoded: str = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return encoded


def decode_access_token(token: str) -> UUID:
    """Decode and validate a JWT access token.

    :param token: JWT token string
    :return: User UUID from token
    :raises TokenError: If token is invalid or expired
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if user_id_str is None or token_type != "access":
            raise TokenError("Invalid token payload")
        return UUID(user_id_str)
    except JWTError as e:
        raise TokenError("Invalid or expired token") from e
    except ValueError as e:
        raise TokenError("Invalid user ID in token") from e
