"""Per-address throttling of the emails an unauthenticated caller can trigger.

Three endpoints mail an address nobody has authenticated as: forgot-password, register,
and resend-verification. The per-IP rate limiter on each bounds a single source, but an
attacker rotating IPs could still flood a *known* inbox. This throttle caps how often
such an email is sent to a given address (keyed by a hash of the email, so no address is
stored): at most one email per short cooldown plus a small daily total. It fails open --
if the shared store is unreachable the email is still sent, so a store outage never
blocks a legitimate reset or activation.

Each flow gets its own instance with its own Redis key prefix, so requesting a password
reset does not eat the budget an activation email needs (or the other way round).

Two entry points, deliberately: ``allow`` asks and spends, ``record`` only spends. A
caller that must send regardless (the branch of ``/register`` that creates the account)
uses ``record``, because a send that spends nothing would make the endpoint answer a
second, back-to-back submission differently for a free address than for a taken one --
rebuilding by timing the account-existence oracle the uniform response removes.
"""

import hashlib
import threading
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Protocol, runtime_checkable

import redis

from api.config import get_settings

# At most one email per address per cooldown, plus a small daily total, so a known
# inbox cannot be flooded even when the per-IP limiter is evaded across many IPs.
COOLDOWN_SECONDS = 60
DAILY_CAP = 5
DAILY_WINDOW_SECONDS = 24 * 60 * 60

# Redis key namespaces, one per flow, so the two budgets stay independent.
RESET_KEY_PREFIX = "reset"
VERIFICATION_KEY_PREFIX = "verify"


def _digest(identifier: str) -> str:
    """Return the SHA-256 hex digest of a normalized email, so no address is stored."""
    return hashlib.sha256(identifier.strip().lower().encode()).hexdigest()


@runtime_checkable
class EmailSendThrottle(Protocol):
    """Backend deciding whether another email may be sent to an address."""

    def allow(self, identifier: str) -> bool: ...
    def record(self, identifier: str) -> None: ...


class InMemoryEmailSendThrottle:
    """Process-local throttle for dev and tests (not shared across replicas).

    Takes no key prefix: each flow holds its own instance, so the send log lives in
    that instance instead of in a shared keyspace.
    """

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
        """Return whether an email may be sent now, recording it when allowed."""
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

    def record(self, identifier: str) -> None:
        """Spend a slot for an email that is sent whatever the budget says."""
        now = datetime.now(UTC)
        key = _digest(identifier)
        with self._lock:
            recent = [t for t in self._sends.get(key, []) if now - t < self._daily_window]
            recent.append(now)
            self._sends[key] = recent


class RedisEmailSendThrottle:
    """Redis-backed throttle shared across replicas.

    :param client: Redis client for the shared store.
    :param key_prefix: Key namespace for this flow; required rather than defaulted so
        two flows sharing one Redis cannot silently consume each other's budget.
    :param cooldown_seconds: Minimum gap between two emails to the same address.
    :param daily_cap: Maximum emails to one address per rolling window.
    :param daily_window_seconds: Length of the rolling window, in seconds.
    """

    def __init__(
        self,
        client: redis.Redis,
        *,
        key_prefix: str,
        cooldown_seconds: int = COOLDOWN_SECONDS,
        daily_cap: int = DAILY_CAP,
        daily_window_seconds: int = DAILY_WINDOW_SECONDS,
    ) -> None:
        self._client = client
        self._key_prefix = key_prefix
        self._cooldown = cooldown_seconds
        self._daily_cap = daily_cap
        self._daily_window = daily_window_seconds

    def allow(self, identifier: str) -> bool:
        """Return whether an email may be sent now, recording it when allowed."""
        digest = _digest(identifier)
        cooldown_key = f"{self._key_prefix}:cooldown:{digest}"
        daily_key = f"{self._key_prefix}:daily:{digest}"
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
            # Fail open: a store outage must never suppress a legitimate email.
            return True

    def record(self, identifier: str) -> None:
        """Spend a slot for an email that is sent whatever the budget says."""
        digest = _digest(identifier)
        try:
            # No NX: this send happens either way, so the cooldown window is restarted
            # rather than consulted.
            self._client.set(f"{self._key_prefix}:cooldown:{digest}", "1", ex=self._cooldown)
            daily_key = f"{self._key_prefix}:daily:{digest}"
            if self._client.incr(daily_key) == 1:
                self._client.expire(daily_key, self._daily_window)
        except redis.RedisError:
            # Fail open, as ``allow`` does: a store outage must not turn into an error
            # on a request whose email has already been decided.
            return


def _build_throttle(key_prefix: str) -> EmailSendThrottle:
    """Build one flow's throttle, Redis-backed when a shared store is configured.

    :param key_prefix: Redis key namespace for the flow.
    :return: The throttle backend for that flow.
    """
    settings = get_settings()
    if settings.redis_url:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        return RedisEmailSendThrottle(client, key_prefix=key_prefix)
    return InMemoryEmailSendThrottle()


@lru_cache
def get_reset_email_throttle() -> EmailSendThrottle:
    """Return the process-wide throttle for password-reset emails.

    :return: The reset-email throttle.
    """
    return _build_throttle(RESET_KEY_PREFIX)


@lru_cache
def get_verification_email_throttle() -> EmailSendThrottle:
    """Return the process-wide throttle for the emails the registration flow sends.

    One budget covers activation links, registration-attempt notices, and resends:
    they all land in the same inbox, so an attacker picking between them must not get
    a separate allowance for each.

    :return: The verification-email throttle.
    """
    return _build_throttle(VERIFICATION_KEY_PREFIX)
