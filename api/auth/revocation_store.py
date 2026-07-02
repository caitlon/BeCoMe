"""Shared-state store for token revocation and per-user session invalidation."""

import threading
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class RevocationStore(Protocol):
    """Backend for JWT revocation (jti blacklist) and per-user token invalidation."""

    def revoke_jti(self, jti: str, ttl_seconds: int) -> None: ...
    def is_jti_revoked(self, jti: str) -> bool: ...
    def set_user_valid_after(self, user_id: UUID, valid_after: datetime) -> None: ...
    def get_user_valid_after(self, user_id: UUID) -> datetime | None: ...


class InMemoryRevocationStore:
    """Process-local RevocationStore for dev and tests (not shared across replicas)."""

    def __init__(self) -> None:
        self._revoked_jti: dict[str, datetime] = {}
        self._user_valid_after: dict[UUID, datetime] = {}
        self._lock = threading.Lock()

    def revoke_jti(self, jti: str, ttl_seconds: int) -> None:
        """Mark a JTI revoked until ``ttl_seconds`` from now."""
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        with self._lock:
            self._revoked_jti[jti] = expires_at

    def is_jti_revoked(self, jti: str) -> bool:
        """Return whether the JTI is currently revoked, purging it once expired."""
        with self._lock:
            expires_at = self._revoked_jti.get(jti)
            if expires_at is None:
                return False
            if expires_at <= datetime.now(UTC):
                del self._revoked_jti[jti]
                return False
            return True

    def set_user_valid_after(self, user_id: UUID, valid_after: datetime) -> None:
        """Invalidate every token for the user issued before ``valid_after``."""
        with self._lock:
            self._user_valid_after[user_id] = valid_after

    def get_user_valid_after(self, user_id: UUID) -> datetime | None:
        """Return the user's ``valid_after`` cutoff, or ``None`` if never set."""
        with self._lock:
            return self._user_valid_after.get(user_id)

    def clear(self) -> None:
        """Drop all revocation state (test helper)."""
        with self._lock:
            self._revoked_jti.clear()
            self._user_valid_after.clear()
