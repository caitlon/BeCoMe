"""Per-account login throttling to blunt brute-force and credential stuffing.

The per-IP rate limiter only bounds one source; an attacker spreading guesses across
many IPs can still hammer a single account. This throttle counts failed logins per
account (keyed by a hash of the email) and locks the account for a cooldown once the
threshold is passed, so the number of password guesses per account is capped no matter
how the requests are distributed. It fails open: if the shared store is unreachable the
account is treated as unlocked, so a store outage never denies every login.
"""

import hashlib
import threading
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Protocol, runtime_checkable

import redis

from api.config import get_settings

# After this many failures within the window, the account is locked until the window
# elapses with no further failures. Ten is generous for a mistyped password while still
# capping guesses to a few dozen per hour.
MAX_FAILURES = 10
WINDOW_SECONDS = 15 * 60


def _key(identifier: str) -> str:
    """Return a store key for an account, hashing the email so no PII is stored."""
    digest = hashlib.sha256(identifier.strip().lower().encode()).hexdigest()
    return f"login:fail:{digest}"


@runtime_checkable
class LoginThrottle(Protocol):
    """Backend tracking failed logins per account."""

    def record_failure(self, identifier: str) -> None: ...
    def is_locked(self, identifier: str) -> bool: ...
    def reset(self, identifier: str) -> None: ...


class InMemoryLoginThrottle:
    """Process-local throttle for dev and tests (not shared across replicas)."""

    def __init__(
        self, max_failures: int = MAX_FAILURES, window_seconds: int = WINDOW_SECONDS
    ) -> None:
        self._max_failures = max_failures
        self._window = timedelta(seconds=window_seconds)
        self._failures: dict[str, list[datetime]] = {}
        self._lock = threading.Lock()

    def _recent(self, identifier: str, now: datetime) -> list[datetime]:
        """Return (and prune to) failures still inside the window."""
        key = _key(identifier)
        recent = [t for t in self._failures.get(key, []) if now - t < self._window]
        self._failures[key] = recent
        return recent

    def record_failure(self, identifier: str) -> None:
        """Record a failed login attempt for the account."""
        now = datetime.now(UTC)
        with self._lock:
            recent = self._recent(identifier, now)
            recent.append(now)

    def is_locked(self, identifier: str) -> bool:
        """Return whether the account is currently locked out."""
        now = datetime.now(UTC)
        with self._lock:
            return len(self._recent(identifier, now)) >= self._max_failures

    def reset(self, identifier: str) -> None:
        """Clear the account's failure count (called on a successful login)."""
        with self._lock:
            self._failures.pop(_key(identifier), None)


class RedisLoginThrottle:
    """Redis-backed throttle shared across replicas."""

    def __init__(
        self,
        client: redis.Redis,
        max_failures: int = MAX_FAILURES,
        window_seconds: int = WINDOW_SECONDS,
    ) -> None:
        self._client = client
        self._max_failures = max_failures
        self._window = window_seconds

    def record_failure(self, identifier: str) -> None:
        """Increment the account's failure counter, refreshing its expiry."""
        key = _key(identifier)
        try:
            pipe = self._client.pipeline()
            pipe.incr(key)
            pipe.expire(key, self._window)
            pipe.execute()
        except redis.RedisError:
            # Fail open: never block a login because the throttle store hiccupped.
            return

    def is_locked(self, identifier: str) -> bool:
        """Return whether the account has reached the failure threshold."""
        try:
            raw = self._client.get(_key(identifier))
        except redis.RedisError:
            return False
        if not isinstance(raw, bytes | str | int):
            return False
        try:
            return int(raw) >= self._max_failures
        except ValueError:
            return False

    def reset(self, identifier: str) -> None:
        """Clear the account's failure counter (called on a successful login)."""
        try:
            self._client.delete(_key(identifier))
        except redis.RedisError:
            return


@lru_cache
def get_login_throttle() -> LoginThrottle:
    """Return the process-wide login throttle, Redis-backed when configured."""
    settings = get_settings()
    if settings.redis_url:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        return RedisLoginThrottle(client)
    return InMemoryLoginThrottle()
