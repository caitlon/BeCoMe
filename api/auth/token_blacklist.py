"""Token blacklist service for logout functionality.

Uses Redis to store revoked token JTIs with automatic expiration.
Falls back to in-memory storage if Redis is not configured.
"""

import threading
from datetime import UTC, datetime
from typing import Any, ClassVar

from api.config import get_settings


class TokenBlacklist:
    """Token blacklist for revoking JWT tokens.

    Stores token JTIs (JWT ID) with TTL matching token expiration.
    Supports Redis for production and in-memory fallback for development.

    Note: In-memory fallback is intended for development/testing only.
    In multi-worker deployments, each worker has its own blacklist.
    Use Redis in production for consistent revocation across workers.
    """

    _redis_client: ClassVar[Any] = None
    _memory_store: ClassVar[dict[str, datetime]] = {}
    _memory_lock: ClassVar[threading.Lock] = threading.Lock()
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

                cls._redis_client = redis.from_url(  # type: ignore[no-untyped-call]
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

        now = datetime.now(UTC)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        ttl_seconds = int((expires_at - now).total_seconds())
        if ttl_seconds <= 0:
            return  # Token already expired

        if cls._redis_client:
            cls._redis_client.setex(f"blacklist:{jti}", ttl_seconds, "revoked")
        else:
            with cls._memory_lock:
                cls._memory_store[jti] = expires_at

    @classmethod
    def is_blacklisted(cls, jti: str) -> bool:
        """Check if token JTI is blacklisted.

        :param jti: JWT ID to check
        :return: True if token is revoked
        """
        cls._initialize()

        if cls._redis_client:
            return bool(cls._redis_client.exists(f"blacklist:{jti}"))

        # In-memory fallback with cleanup
        with cls._memory_lock:
            if jti in cls._memory_store:
                expires_at = cls._memory_store[jti]
                now = datetime.now(UTC)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
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

        with cls._memory_lock:
            now = datetime.now(UTC)
            expired = [
                jti
                for jti, exp in cls._memory_store.items()
                if (exp.replace(tzinfo=UTC) if exp.tzinfo is None else exp) <= now
            ]
            for jti in expired:
                del cls._memory_store[jti]
            return len(expired)

    @classmethod
    def reset(cls) -> None:
        """Reset blacklist state (for testing)."""
        with cls._memory_lock:
            cls._memory_store.clear()
        cls._redis_client = None
        cls._initialized = False
