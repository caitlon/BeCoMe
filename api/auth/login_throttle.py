"""Failure throttling guarding both login and activation password guesses.

The per-IP rate limiter only bounds one source; an attacker spreading guesses across
many IPs can still hammer a single target. This throttle counts failed password
attempts against a caller-chosen identifier and locks that identifier out for a cooldown
once the threshold is passed, so the number of guesses against it is capped no matter
how the requests are distributed. It fails open: if the shared store is unreachable the
identifier is treated as unlocked, so a store outage never denies every attempt.

Two flows share this mechanism but never a counter, and each keys it on something
different. ``POST /login`` hashes the account's normalized email, so the lockout follows
the address no matter which token, if any, a caller presents. ``POST /verify-email``
hashes the token's own stored hash instead, so only a caller who already holds a live
token can move it at all, and a run of failed logins -- which anyone who merely knows
the address can produce without ever holding an activation link -- cannot lock someone
out of their own activation. Keying activation on the token rather than the account also
confines a burned token's damage to itself: an address can carry several live tokens at
once, and a shared per-account bucket would let one obtained token -- forwarded or
intercepted, not read from the mailbox -- exhaust the whole account's budget and deny a
different, freshly resent link along with it. The two flows are further distinguished by
a Redis key prefix.

The two budgets are therefore independent, and they add up: ``MAX_FAILURES`` each per
window, not ``MAX_FAILURES`` between them. Sharing one counter is the only thing that
would bound the total, and sharing is what brings the denial back, because the login half
takes no credential to move and every failure refreshes its expiry. The activation half
needs a live single-use token, which exists only in the mailbox it was sent to, and
whoever has read that mailbox can already take the account through ``forgot-password``
without guessing. A wrong activation guess does still spend from the login counter (see
``verify_email`` in ``api/routes/auth.py``), which costs the guesser their login budget
rather than capping the pair.
"""

import hashlib
import logging
import threading
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Protocol, runtime_checkable

import redis

from api.config import get_settings

logger = logging.getLogger("api.security")

# After this many failures within the window, the account is locked until the window
# elapses with no further failures. Ten is generous for a mistyped password while still
# capping guesses to a few dozen per hour.
MAX_FAILURES = 10
WINDOW_SECONDS = 15 * 60

# Redis key namespaces, one per flow, so a lockout on one never reads or writes the
# other's counter.
LOGIN_KEY_PREFIX = "login"
ACTIVATION_KEY_PREFIX = "activation"


def _digest(identifier: str) -> str:
    """Return the SHA-256 hex digest of a normalized identifier, so no raw value is stored.

    Never log this value. It is an unkeyed digest, so anyone holding the logs could
    hash a guessed address and confirm it appears -- exactly the account-existence
    oracle ``api.auth.logging.hash_email`` is keyed to prevent. Records in this module
    name the flow, never the account.
    """
    return hashlib.sha256(identifier.strip().lower().encode()).hexdigest()


def _log_store_unavailable(op: str, exc: redis.RedisError, key_prefix: str) -> None:
    """Record a lockout store that could not be reached.

    Worth a record because this throttle fails open: the attempt proceeds as if no
    failures had been counted, so an outage silently disables the account lockout with
    nothing else to show for it. ``docs/security.md`` accepts that risk; this makes it
    observable.

    ERROR, not WARNING, and for the same reason as the swallowed email failures in
    ``api/routes/auth.py``: Sentry is initialised without a ``LoggingIntegration``, so the
    SDK's default ``event_level`` of ERROR decides what becomes an issue, and a warning
    would only ever be a breadcrumb on some later event. Nothing else marks the outage --
    the request it happened during succeeds and the caller sees a normal response -- so at
    WARNING the brute-force lockout could stay off for as long as Redis is down with no
    alert anywhere. The level *is* the alert.

    :param op: Throttle operation that failed -- ``record_failure``, ``is_locked``, or ``reset``.
    :param exc: The Redis error that caused it.
    :param key_prefix: Key namespace of the flow whose lockout stopped being enforced.
    """
    logger.error(
        "Login throttle store unavailable, lockout not enforced",
        extra={"event": "throttle_store_unavailable", "op": op, "key_prefix": key_prefix},
        exc_info=exc,
    )


@runtime_checkable
class LoginThrottle(Protocol):
    """Backend tracking failed password attempts against a caller-chosen identifier."""

    def record_failure(self, identifier: str) -> None: ...
    def is_locked(self, identifier: str) -> bool: ...
    def reset(self, identifier: str) -> None: ...


class InMemoryLoginThrottle:
    """Process-local throttle for dev and tests (not shared across replicas).

    Takes no key prefix: each flow holds its own instance, so its failure log lives in
    that instance instead of in a shared keyspace.
    """

    def __init__(
        self, max_failures: int = MAX_FAILURES, window_seconds: int = WINDOW_SECONDS
    ) -> None:
        self._max_failures = max_failures
        self._window = timedelta(seconds=window_seconds)
        self._failures: dict[str, list[datetime]] = {}
        self._lock = threading.Lock()

    def _recent(self, identifier: str, now: datetime) -> list[datetime]:
        """Return (and prune to) failures still inside the window."""
        key = _digest(identifier)
        recent = [t for t in self._failures.get(key, []) if now - t < self._window]
        self._failures[key] = recent
        return recent

    def record_failure(self, identifier: str) -> None:
        """Record a failed attempt for the account."""
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
        """Clear the account's failure count (called on a successful attempt)."""
        with self._lock:
            self._failures.pop(_digest(identifier), None)


class RedisLoginThrottle:
    """Redis-backed throttle shared across replicas.

    :param client: Redis client for the shared store.
    :param key_prefix: Key namespace for this flow; required rather than defaulted so
        two flows sharing one Redis cannot silently share -- or trip -- each other's
        lockout.
    :param max_failures: Failures allowed within the window before locking.
    :param window_seconds: Length of the failure window, in seconds.
    """

    def __init__(
        self,
        client: redis.Redis,
        *,
        key_prefix: str,
        max_failures: int = MAX_FAILURES,
        window_seconds: int = WINDOW_SECONDS,
    ) -> None:
        self._client = client
        self._key_prefix = key_prefix
        self._max_failures = max_failures
        self._window = window_seconds

    def _key(self, identifier: str) -> str:
        """Return this flow's store key for an account."""
        return f"{self._key_prefix}:fail:{_digest(identifier)}"

    def record_failure(self, identifier: str) -> None:
        """Increment the account's failure counter, refreshing its expiry."""
        key = self._key(identifier)
        try:
            pipe = self._client.pipeline()
            pipe.incr(key)
            pipe.expire(key, self._window)
            pipe.execute()
        except redis.RedisError as e:
            # Fail open: never block an attempt because the throttle store hiccupped.
            _log_store_unavailable("record_failure", e, self._key_prefix)
            return

    def is_locked(self, identifier: str) -> bool:
        """Return whether the account has reached the failure threshold."""
        try:
            raw = self._client.get(self._key(identifier))
        except redis.RedisError as e:
            _log_store_unavailable("is_locked", e, self._key_prefix)
            return False
        if not isinstance(raw, bytes | str | int):
            return False
        try:
            return int(raw) >= self._max_failures
        except ValueError:
            return False

    def reset(self, identifier: str) -> None:
        """Clear the account's failure counter (called on a successful attempt)."""
        try:
            self._client.delete(self._key(identifier))
        except redis.RedisError as e:
            _log_store_unavailable("reset", e, self._key_prefix)
            return


def _build_throttle(key_prefix: str) -> LoginThrottle:
    """Build one flow's throttle, Redis-backed when a shared store is configured.

    :param key_prefix: Redis key namespace for the flow.
    :return: The throttle backend for that flow.
    """
    settings = get_settings()
    backend = "redis" if settings.redis_url else "memory"
    logger.debug(
        "Login throttle backend selected",
        extra={
            "event": "throttle_backend_selected",
            "throttle": "login",
            "key_prefix": key_prefix,
            "backend": backend,
        },
    )
    if settings.redis_url:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        return RedisLoginThrottle(client, key_prefix=key_prefix)
    return InMemoryLoginThrottle()


@lru_cache
def get_login_throttle() -> LoginThrottle:
    """Return the process-wide login throttle, Redis-backed when configured.

    Gates ``POST /login`` only. A wrong password anywhere -- including one posted with
    an activation link -- still spends from this counter (see
    :func:`get_activation_throttle`), but nothing outside ``/login`` ever consults or
    clears it.

    :return: The login throttle.
    """
    return _build_throttle(LOGIN_KEY_PREFIX)


@lru_cache
def get_activation_throttle() -> LoginThrottle:
    """Return the process-wide activation-guess throttle, Redis-backed when configured.

    Gates ``POST /verify-email`` only, under its own Redis key prefix, so this lockout
    can only be tripped by someone who already holds a live activation token. A run of
    failed attempts against ``/login`` requires no such token, so it never counts
    against this counter and can never deny someone their own activation. The price of
    that independence is that the two budgets add up instead of sharing one; the module
    docstring records why the trade goes this way. Every activation mismatch still also
    spends from :func:`get_login_throttle`, which costs the guesser their login budget.

    :return: The activation-guess throttle.
    """
    return _build_throttle(ACTIVATION_KEY_PREFIX)
