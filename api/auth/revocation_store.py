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
    """Backend for JWT revocation, refresh-token sessions, and per-user invalidation.

    A *session* is one refresh-token family, minted at login and carried through every
    rotation via a ``sid`` claim. The store tracks each session's current refresh jti so
    a rotation can atomically consume it; presenting a jti that is not the current one is
    reuse, which revokes the whole session (breach containment).
    """

    def revoke_jti(self, jti: str, ttl_seconds: int) -> None: ...
    def is_jti_revoked(self, jti: str) -> bool: ...
    def set_user_valid_after(self, user_id: UUID, valid_after: datetime) -> None: ...
    def get_user_valid_after(self, user_id: UUID) -> datetime | None: ...
    def start_session(self, sid: str, jti: str, ttl_seconds: int) -> None: ...
    def rotate_session(
        self, sid: str, expected_jti: str, new_jti: str, ttl_seconds: int
    ) -> bool: ...
    def revoke_session(self, sid: str, ttl_seconds: int) -> None: ...
    def is_session_revoked(self, sid: str) -> bool: ...


class InMemoryRevocationStore:
    """Process-local RevocationStore for dev and tests (not shared across replicas)."""

    def __init__(self) -> None:
        self._revoked_jti: dict[str, datetime] = {}
        self._user_valid_after: dict[UUID, datetime] = {}
        self._session_current: dict[str, str] = {}
        self._session_revoked: dict[str, datetime] = {}
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

    def start_session(self, sid: str, jti: str, ttl_seconds: int) -> None:
        """Record ``jti`` as the current refresh token for session ``sid``."""
        with self._lock:
            self._session_current[sid] = jti

    def rotate_session(self, sid: str, expected_jti: str, new_jti: str, ttl_seconds: int) -> bool:
        """Atomically swap the session's current jti, returning False on a mismatch."""
        with self._lock:
            if self._session_current.get(sid) != expected_jti:
                return False
            self._session_current[sid] = new_jti
            return True

    def revoke_session(self, sid: str, ttl_seconds: int) -> None:
        """Revoke the whole session so every token carrying ``sid`` is rejected."""
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        with self._lock:
            self._session_revoked[sid] = expires_at
            self._session_current.pop(sid, None)

    def is_session_revoked(self, sid: str) -> bool:
        """Return whether the session is currently revoked, purging it once expired."""
        with self._lock:
            expires_at = self._session_revoked.get(sid)
            if expires_at is None:
                return False
            if expires_at <= datetime.now(UTC):
                del self._session_revoked[sid]
                return False
            return True

    def clear(self) -> None:
        """Drop all revocation state (test helper)."""
        with self._lock:
            self._revoked_jti.clear()
            self._user_valid_after.clear()
            self._session_current.clear()
            self._session_revoked.clear()


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
        # Expire a bit after the longest-lived token so the cutoff outlives every token
        # it must invalidate, yet the key does not accumulate forever per user.
        ttl = get_settings().refresh_token_expire_days * 86400 + 3600
        try:
            self._client.set(f"user:valid_after:{user_id}", valid_after.isoformat(), ex=ttl)
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

    def start_session(self, sid: str, jti: str, ttl_seconds: int) -> None:
        try:
            self._client.set(f"session:current:{sid}", jti, ex=max(ttl_seconds, 1))
        except redis.RedisError as e:
            raise RevocationStoreError(str(e)) from e

    def rotate_session(self, sid: str, expected_jti: str, new_jti: str, ttl_seconds: int) -> bool:
        key = f"session:current:{sid}"
        try:
            with self._client.pipeline() as pipe:
                while True:
                    try:
                        pipe.watch(key)  # type: ignore[no-untyped-call]
                        raw = pipe.get(key)
                        current = raw.decode() if isinstance(raw, bytes) else raw
                        if current != expected_jti:
                            pipe.unwatch()
                            return False
                        pipe.multi()
                        pipe.set(key, new_jti, ex=max(ttl_seconds, 1))
                        pipe.execute()
                        return True
                    except redis.WatchError:
                        continue
        except redis.RedisError as e:
            raise RevocationStoreError(str(e)) from e

    def revoke_session(self, sid: str, ttl_seconds: int) -> None:
        try:
            pipe = self._client.pipeline()
            pipe.set(f"session:revoked:{sid}", "1", ex=max(ttl_seconds, 1))
            pipe.delete(f"session:current:{sid}")
            pipe.execute()
        except redis.RedisError as e:
            raise RevocationStoreError(str(e)) from e

    def is_session_revoked(self, sid: str) -> bool:
        try:
            return bool(self._client.exists(f"session:revoked:{sid}"))
        except redis.RedisError as e:
            raise RevocationStoreError(str(e)) from e


@lru_cache
def get_revocation_store() -> RevocationStore:
    """Return the process-wide revocation store, Redis-backed when configured.

    Selected once per process: a `RedisRevocationStore` when `redis_url` is set
    (production), otherwise an in-memory store for dev and tests.
    """
    settings = get_settings()
    if settings.redis_url:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        return RedisRevocationStore(client)
    return InMemoryRevocationStore()
