"""Shared-state store for token revocation and per-user session invalidation."""

import threading
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Protocol, runtime_checkable
from uuid import UUID

import redis

from api.config import get_settings


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


class RevocationStoreError(Exception):
    """Raised when the revocation store cannot be reached (fail-closed)."""


class RedisRevocationStore:
    """Redis-backed RevocationStore shared across replicas and workers."""

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    def revoke_jti(self, jti: str, ttl_seconds: int) -> None:
        try:
            self._client.set(f"revoked:jti:{jti}", "1", ex=max(ttl_seconds, 1))
        except redis.RedisError as e:
            raise RevocationStoreError(str(e)) from e

    def is_jti_revoked(self, jti: str) -> bool:
        try:
            return bool(self._client.exists(f"revoked:jti:{jti}"))
        except redis.RedisError as e:
            raise RevocationStoreError(str(e)) from e

    def set_user_valid_after(self, user_id: UUID, valid_after: datetime) -> None:
        try:
            self._client.set(f"user:valid_after:{user_id}", valid_after.isoformat())
        except redis.RedisError as e:
            raise RevocationStoreError(str(e)) from e

    def get_user_valid_after(self, user_id: UUID) -> datetime | None:
        try:
            raw = self._client.get(f"user:valid_after:{user_id}")
        except redis.RedisError as e:
            raise RevocationStoreError(str(e)) from e
        if raw is None:
            return None
        text = raw.decode() if isinstance(raw, bytes) else str(raw)
        return datetime.fromisoformat(text)


@lru_cache
def get_revocation_store() -> RevocationStore:
    """Return the process-wide revocation store, Redis-backed when configured.

    Selected once per process: a `RedisRevocationStore` when `redis_url` is set
    (production), otherwise an in-memory store for dev and tests.
    """
    settings = get_settings()
    if settings.redis_url:
        client = redis.from_url(  # type: ignore[no-untyped-call]
            settings.redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        return RedisRevocationStore(client)
    return InMemoryRevocationStore()
