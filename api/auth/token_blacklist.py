"""Token blacklist service for logout functionality.

Uses in-memory storage with automatic expiration cleanup.
"""

import threading
from datetime import UTC, datetime
from typing import ClassVar


class TokenBlacklist:
    """Token blacklist for revoking JWT tokens.

    Stores token JTIs (JWT ID) with TTL matching token expiration.
    Uses in-memory storage with thread-safe access.

    Note: In multi-worker deployments, each worker has its own blacklist.
    For distributed deployments, consider external storage solutions.
    """

    _memory_store: ClassVar[dict[str, datetime]] = {}
    _memory_lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def add(cls, jti: str, expires_at: datetime) -> None:
        """Add token JTI to blacklist.

        :param jti: JWT ID to blacklist
        :param expires_at: Token expiration time (for TTL calculation)
        """
        now = datetime.now(UTC)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at <= now:
            return  # Token already expired

        with cls._memory_lock:
            cls._memory_store[jti] = expires_at

    @classmethod
    def is_blacklisted(cls, jti: str) -> bool:
        """Check if token JTI is blacklisted.

        :param jti: JWT ID to check
        :return: True if token is revoked
        """
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
        """Remove expired entries from store.

        :return: Number of entries removed
        """
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
