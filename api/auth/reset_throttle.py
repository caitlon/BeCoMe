"""Per-address throttling of password-reset emails.

The per-IP rate limiter on the forgot-password endpoint bounds a single source, but an
attacker rotating IPs could still flood a *known* inbox with reset emails. This throttle
caps how often a reset email is sent to a given address (keyed by a hash of the email, so
no address is stored): at most one email per short cooldown plus a small daily total. It
fails open -- if the shared store is unreachable a reset email is still sent, so a store
outage never blocks a legitimate reset.
"""

import hashlib
import threading
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Protocol, runtime_checkable

import redis

from api.config import get_settings

# At most one reset email per address per cooldown, plus a small daily total, so a known
# inbox cannot be flooded even when the per-IP limiter is evaded across many IPs.
COOLDOWN_SECONDS = 60
DAILY_CAP = 5
DAILY_WINDOW_SECONDS = 24 * 60 * 60


def _digest(identifier: str) -> str:
    """Return the SHA-256 hex digest of a normalized email, so no address is stored."""
    return hashlib.sha256(identifier.strip().lower().encode()).hexdigest()


@runtime_checkable
class ResetEmailThrottle(Protocol):
    """Backend deciding whether another reset email may be sent to an address."""

    def allow(self, identifier: str) -> bool: ...


class InMemoryResetEmailThrottle:
    """Process-local throttle for dev and tests (not shared across replicas)."""

    def __init__(
        self,
        cooldown_seconds: int = COOLDOWN_SECONDS,
        daily_cap: int = DAILY_CAP,
        daily_window_seconds: int = DAILY_WINDOW_SECONDS,
    ) -> None:
        self._cooldown = timedelta(seconds=cooldown_seconds)
        self._daily_cap = daily_cap
        self._daily_window = timedelta(seconds=daily_window_seconds)
        self._sends: dict[str, list[datetime]] = {}
        self._lock = threading.Lock()

    def allow(self, identifier: str) -> bool:
        """Return whether a reset email may be sent now, recording it when allowed."""
        now = datetime.now(UTC)
        key = _digest(identifier)
        with self._lock:
            recent = [t for t in self._sends.get(key, []) if now - t < self._daily_window]
            if recent and now - recent[-1] < self._cooldown:
                self._sends[key] = recent
                return False
            if len(recent) >= self._daily_cap:
                self._sends[key] = recent
                return False
            recent.append(now)
            self._sends[key] = recent
            return True


class RedisResetEmailThrottle:
    """Redis-backed throttle shared across replicas."""

    def __init__(
        self,
        client: redis.Redis,
        cooldown_seconds: int = COOLDOWN_SECONDS,
        daily_cap: int = DAILY_CAP,
        daily_window_seconds: int = DAILY_WINDOW_SECONDS,
    ) -> None:
        self._client = client
        self._cooldown = cooldown_seconds
        self._daily_cap = daily_cap
        self._daily_window = daily_window_seconds

    def allow(self, identifier: str) -> bool:
        """Return whether a reset email may be sent now, recording it when allowed."""
        digest = _digest(identifier)
        cooldown_key = f"reset:cooldown:{digest}"
        daily_key = f"reset:daily:{digest}"
        try:
            # Cooldown gate: SET NX succeeds only when the cooldown window is clear.
            if not self._client.set(cooldown_key, "1", nx=True, ex=self._cooldown):
                return False
            raw = self._client.get(daily_key)
            sent_today = int(raw) if isinstance(raw, bytes | str | int) else 0
            if sent_today >= self._daily_cap:
                return False
            if self._client.incr(daily_key) == 1:
                self._client.expire(daily_key, self._daily_window)
            return True
        except redis.RedisError:
            # Fail open: a store outage must never suppress a legitimate reset email.
            return True


@lru_cache
def get_reset_email_throttle() -> ResetEmailThrottle:
    """Return the process-wide reset-email throttle, Redis-backed when configured."""
    settings = get_settings()
    if settings.redis_url:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        return RedisResetEmailThrottle(client)
    return InMemoryResetEmailThrottle()
