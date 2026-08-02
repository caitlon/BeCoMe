"""Shared-state store for token revocation and per-user session invalidation."""

import logging
import threading
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from time import perf_counter
from typing import Protocol, runtime_checkable
from uuid import UUID

import redis

from api.config import get_settings

logger = logging.getLogger("api.security")


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


def _store_error(op: str, exc: redis.RedisError) -> RevocationStoreError:
    """Log an unreachable revocation store and build the error to raise.

    This record exists because the store is fail-closed and most callers hide the
    cause: every ``decode_token`` path in :mod:`api.auth.jwt` turns this error into
    a plain 401, so without a log line a Redis outage is indistinguishable from a
    wave of bad tokens. Only the 503 path
    (``revocation_store_unavailable_handler``) was visible before.

    :param op: Store operation that failed, e.g. ``is_jti_revoked``.
    :param exc: The Redis error that caused it.
    :return: The error the caller should raise.
    """
    logger.warning(
        "Revocation store unavailable",
        extra={"event": "revocation_store_unavailable", "op": op},
        exc_info=exc,
    )
    return RevocationStoreError(str(exc))


def _log_call(op: str, start: float, **fields: object) -> None:
    """Trace one revocation-store round trip.

    :param op: Store operation that ran.
    :param start: ``perf_counter()`` reading taken before the call.
    :param fields: Extra context to attach to the record.
    """
    logger.debug(
        "Revocation store call",
        extra={
            "event": "revocation_store_call",
            "op": op,
            "duration_ms": round((perf_counter() - start) * 1000.0, 1),
            **fields,
        },
    )


class RedisRevocationStore:
    """Redis-backed RevocationStore shared across replicas and workers."""

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    def revoke_jti(self, jti: str, ttl_seconds: int) -> None:
        try:
            self._client.set(f"revoked:jti:{jti}", "1", ex=max(ttl_seconds, 1))
        except redis.RedisError as e:
            raise _store_error("revoke_jti", e) from e

    def is_jti_revoked(self, jti: str) -> bool:
        try:
            return bool(self._client.exists(f"revoked:jti:{jti}"))
        except redis.RedisError as e:
            raise _store_error("is_jti_revoked", e) from e

    def set_user_valid_after(self, user_id: UUID, valid_after: datetime) -> None:
        # Expire a bit after the longest-lived token so the cutoff outlives every token
        # it must invalidate, yet the key does not accumulate forever per user.
        ttl = get_settings().refresh_token_expire_days * 86400 + 3600
        start = perf_counter()
        try:
            self._client.set(f"user:valid_after:{user_id}", valid_after.isoformat(), ex=ttl)
        except redis.RedisError as e:
            raise _store_error("set_user_valid_after", e) from e
        _log_call("set_user_valid_after", start, user_id=str(user_id))

    def get_user_valid_after(self, user_id: UUID) -> datetime | None:
        try:
            raw = self._client.get(f"user:valid_after:{user_id}")
        except redis.RedisError as e:
            raise _store_error("get_user_valid_after", e) from e
        if raw is None:
            return None
        text = raw.decode() if isinstance(raw, bytes) else str(raw)
        return datetime.fromisoformat(text)

    def start_session(self, sid: str, jti: str, ttl_seconds: int) -> None:
        try:
            self._client.set(f"session:current:{sid}", jti, ex=max(ttl_seconds, 1))
        except redis.RedisError as e:
            raise _store_error("start_session", e) from e

    def rotate_session(self, sid: str, expected_jti: str, new_jti: str, ttl_seconds: int) -> bool:
        key = f"session:current:{sid}"
        start = perf_counter()
        try:
            with self._client.pipeline() as pipe:
                while True:
                    try:
                        pipe.watch(key)  # type: ignore[no-untyped-call]
                        raw = pipe.get(key)
                        current = raw.decode() if isinstance(raw, bytes) else raw
                        if current != expected_jti:
                            pipe.unwatch()
                            _log_call("rotate_session", start, sid=sid, rotated=False)
                            return False
                        pipe.multi()
                        pipe.set(key, new_jti, ex=max(ttl_seconds, 1))
                        pipe.execute()
                        _log_call("rotate_session", start, sid=sid, rotated=True)
                        return True
                    except redis.WatchError:
                        continue
        except redis.RedisError as e:
            raise _store_error("rotate_session", e) from e

    def revoke_session(self, sid: str, ttl_seconds: int) -> None:
        start = perf_counter()
        try:
            pipe = self._client.pipeline()
            pipe.set(f"session:revoked:{sid}", "1", ex=max(ttl_seconds, 1))
            pipe.delete(f"session:current:{sid}")
            pipe.execute()
        except redis.RedisError as e:
            raise _store_error("revoke_session", e) from e
        _log_call("revoke_session", start, sid=sid)

    def is_session_revoked(self, sid: str) -> bool:
        try:
            return bool(self._client.exists(f"session:revoked:{sid}"))
        except redis.RedisError as e:
            raise _store_error("is_session_revoked", e) from e


@lru_cache
def get_revocation_store() -> RevocationStore:
    """Return the process-wide revocation store, Redis-backed when configured.

    Selected once per process: a `RedisRevocationStore` when `redis_url` is set
    (production), otherwise an in-memory store for dev and tests.
    """
    settings = get_settings()
    backend = "redis" if settings.redis_url else "memory"
    logger.info(
        "Revocation store selected",
        extra={"event": "revocation_store_selected", "backend": backend},
    )
    if settings.redis_url:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        return RedisRevocationStore(client)
    return InMemoryRevocationStore()
