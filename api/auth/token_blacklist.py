"""Token blacklist service for logout functionality.

Uses Redis to store revoked token JTIs with automatic expiration.
Falls back to in-memory storage if Redis is not configured.
"""

from datetime import datetime, timedelta, timezone
from typing import ClassVar

from api.config import get_settings


class TokenBlacklist:
    """Token blacklist for revoking JWT tokens.

    Stores token JTIs (JWT ID) with TTL matching token expiration.
    Supports Redis for production and in-memory fallback for development.
    """

    _redis_client: ClassVar["Redis | None"] = None  # type: ignore[name-defined]
    _memory_store: ClassVar[dict[str, datetime]] = {}
    _initialized: ClassVar[bool] = False

    @classmethod
    def _initialize(cls) -> None:
        """Initialize Redis connection if configured."""
        if cls._initialized:
            return

        settings = get_settings()
        if settings.redis_url:
            try:
                import redis

                cls._redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                )
                # Test connection
                cls._redis_client.ping()
            except Exception:
                cls._redis_client = None

        cls._initialized = True

    @classmethod
    def add(cls, jti: str, expires_at: datetime) -> None:
        """Add token JTI to blacklist.

        :param jti: JWT ID to blacklist
        :param expires_at: Token expiration time (for TTL calculation)
        """
        cls._initialize()

        now = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        ttl_seconds = int((expires_at - now).total_seconds())
        if ttl_seconds <= 0:
            return  # Token already expired

        if cls._redis_client:
            cls._redis_client.setex(f"blacklist:{jti}", ttl_seconds, "revoked")
        else:
            cls._memory_store[jti] = expires_at

    @classmethod
    def is_blacklisted(cls, jti: str) -> bool:
        """Check if token JTI is blacklisted.

        :param jti: JWT ID to check
        :return: True if token is revoked
        """
        cls._initialize()

        if cls._redis_client:
            return cls._redis_client.exists(f"blacklist:{jti}") > 0

        # In-memory fallback with cleanup
        if jti in cls._memory_store:
            expires_at = cls._memory_store[jti]
            now = datetime.now(timezone.utc)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now < expires_at:
                return True
            del cls._memory_store[jti]

        return False

    @classmethod
    def cleanup_expired(cls) -> int:
        """Remove expired entries from in-memory store.

        :return: Number of entries removed
        """
        if cls._redis_client:
            return 0  # Redis handles TTL automatically

        now = datetime.now(timezone.utc)
        expired = [
            jti
            for jti, exp in cls._memory_store.items()
            if (exp.replace(tzinfo=timezone.utc) if exp.tzinfo is None else exp) <= now
        ]
        for jti in expired:
            del cls._memory_store[jti]
        return len(expired)

    @classmethod
    def reset(cls) -> None:
        """Reset blacklist state (for testing)."""
        cls._memory_store.clear()
        cls._redis_client = None
        cls._initialized = False
