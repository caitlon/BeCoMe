"""Failure throttling guarding the login, activation and current-password guesses.

The per-IP rate limiter only bounds one source; an attacker spreading guesses across
many IPs can still hammer a single target. This throttle counts failed password
attempts against a caller-chosen identifier and locks that identifier out for a cooldown
once the threshold is passed, so the number of guesses against it is capped no matter
how the requests are distributed. It fails open: if the shared store is unreachable the
identifier is treated as unlocked, so a store outage never denies every attempt.

A route takes a slot with ``reserve`` before it checks the password, and settles it
afterwards: ``confirm_failure`` when the guess was wrong, ``release`` when the attempt was
neither a wrong guess nor a success (a correct password on an unverified account, an
unexpected error), ``reset`` when it succeeded. Because the slot is counted before the slow
password check starts, requests running in parallel cannot between them pass more than
``MAX_FAILURES`` checks per window. Only a confirmed failure restarts the window, as a
recorded failure always did; taking a slot, being refused one or giving one back leaves the
expiry where it was.

Three flows share this mechanism but never a counter, and each keys it on something
different. ``POST /login`` hashes the account's normalized email, so the lockout follows
the address no matter which token, if any, a caller presents. ``POST /verify-email``
hashes the token's own stored hash instead, so only a caller who already holds a live
token can move it at all, and a run of failed logins cannot lock someone out of their own
activation. Anyone who merely knows the address can produce such a run without ever
holding an activation link. Keying activation on the token rather than the account also
confines a burned token's damage to itself: an address can carry several live tokens at
once, and a shared per-account bucket would let one obtained token, forwarded or
intercepted rather than read from the mailbox, exhaust the whole account's budget and
deny a different, freshly resent link along with it.

``PUT /users/me/password`` and ``DELETE /users/me`` share the third counter, keyed on the
signed-in account's id: both confirm the current password, and a wrong one on either spends
from the same budget, so alternating between the two routes buys no extra guesses. It sits
apart from login for the same reason activation does, seen from the other side. Whoever holds
a stolen session can produce failures here at will, and on the login counter they would lock
the owner out of signing in. Keyed on the account rather than the address, rotating source
addresses does not widen the budget either. A locked login does not gate these routes in
turn, for the same reason in reverse.

The flows are further distinguished by a Redis key prefix. The three budgets are therefore
independent, and they add up: ``MAX_FAILURES`` each per window, not ``MAX_FAILURES`` between
them. Sharing one counter is the only thing that
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
RECONFIRM_KEY_PREFIX = "reconfirm"


def _digest(identifier: str) -> str:
    """Return the SHA-256 hex digest of a normalized identifier, so no raw value is stored.

    Never log this value. It is an unkeyed digest, so anyone holding the logs could
    hash a guessed address and confirm it appears, which is exactly the account-existence
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
    would only ever be a breadcrumb on some later event. Nothing else marks the outage,
    since the request it happened during succeeds and the caller sees a normal response.
    At WARNING the brute-force lockout could stay off for as long as Redis is down with no
    alert anywhere. The level *is* the alert.

    :param op: Throttle operation that failed: ``reserve``, ``confirm_failure``, ``release``,
        ``record_failure``, ``is_locked``, or ``reset``.
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

    def reserve(self, identifier: str) -> bool: ...
    def confirm_failure(self, identifier: str) -> None: ...
    def release(self, identifier: str) -> None: ...
    def record_failure(self, identifier: str) -> None: ...
    def is_locked(self, identifier: str) -> bool: ...
    def reset(self, identifier: str) -> None: ...


class InMemoryLoginThrottle:
    """Process-local throttle for dev and tests (not shared across replicas).

    Takes no key prefix: each flow holds its own instance, so its failure log lives in
    that instance instead of in a shared keyspace.

    Keeps what Redis keeps: a count and the time of the last failure. Every failure
    refreshes the window, a failure while locked included, and the count starts over once a
    whole window passes with none.
    """

    def __init__(
        self, max_failures: int = MAX_FAILURES, window_seconds: int = WINDOW_SECONDS
    ) -> None:
        self._max_failures = max_failures
        self._window = timedelta(seconds=window_seconds)
        self._failures: dict[str, tuple[int, datetime]] = {}
        self._lock = threading.Lock()

    def _live(self, key: str, now: datetime) -> tuple[int, datetime] | None:
        """Return the account's count and last failure, or None once the window has passed."""
        entry = self._failures.get(key)
        if entry is not None and now - entry[1] >= self._window:
            del self._failures[key]
            return None
        return entry

    def reserve(self, identifier: str) -> bool:
        """Count one attempt if the account is inside its budget, and say whether it is.

        A refusal changes nothing. A granted slot on a live entry leaves its window where
        it was; on a new entry it starts the window.
        """
        now = datetime.now(UTC)
        key = _digest(identifier)
        with self._lock:
            entry = self._live(key, now)
            if entry is not None and entry[0] >= self._max_failures:
                return False
            self._failures[key] = ((entry[0] if entry else 0) + 1, entry[1] if entry else now)
            return True

    def confirm_failure(self, identifier: str) -> None:
        """Settle a reserved attempt as a failed guess, restarting the account's window.

        If the entry is gone (the window passed, or a reset landed while the password was
        being checked) it is recreated at one, so the failure is not lost.
        """
        now = datetime.now(UTC)
        key = _digest(identifier)
        with self._lock:
            entry = self._live(key, now)
            self._failures[key] = (entry[0] if entry else 1, now)

    def release(self, identifier: str) -> None:
        """Give a reserved attempt back, leaving the window where it was."""
        now = datetime.now(UTC)
        key = _digest(identifier)
        with self._lock:
            entry = self._live(key, now)
            if entry is None:
                return
            if entry[0] <= 1:
                del self._failures[key]
            else:
                self._failures[key] = (entry[0] - 1, entry[1])

    def record_failure(self, identifier: str) -> None:
        """Record a failed attempt for the account, refreshing its window."""
        now = datetime.now(UTC)
        key = _digest(identifier)
        with self._lock:
            entry = self._live(key, now)
            self._failures[key] = ((entry[0] if entry else 0) + 1, now)

    def is_locked(self, identifier: str) -> bool:
        """Return whether the account is currently locked out.

        Read-only: an attempt is gated with :meth:`reserve`, not with this.
        """
        now = datetime.now(UTC)
        with self._lock:
            entry = self._live(_digest(identifier), now)
            return entry is not None and entry[0] >= self._max_failures

    def reset(self, identifier: str) -> None:
        """Clear the account's failure count (called on a successful attempt)."""
        with self._lock:
            self._failures.pop(_digest(identifier), None)


class RedisLoginThrottle:
    """Redis-backed throttle shared across replicas.

    :param client: Redis client for the shared store.
    :param key_prefix: Key namespace for this flow, required rather than defaulted so
        two flows sharing one Redis cannot silently share each other's lockout, and
        cannot trip it for one another.
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

    def _give_back(self, key: str) -> None:
        """Take one attempt off the counter, removing the key once nothing is left.

        A key that vanished in the meantime goes negative on the decrement and is deleted
        by the same check, so no negative count is ever left behind.
        """
        if int(self._client.decr(key)) <= 0:
            self._client.delete(key)

    def reserve(self, identifier: str) -> bool:
        """Count one attempt if the account is inside its budget, and say whether it is.

        The increment hands every caller a distinct value, so exactly ``max_failures``
        concurrent callers see a count inside the budget whatever the interleaving. A
        caller past it gives its increment back and is refused, which changes nothing. A
        granted slot on a live key leaves its expiry alone; a key with none (new, or left
        bare by a crash) gets the window before the refusal check, so it can never stay
        immortal. Fails open when the store is unreachable.
        """
        key = self._key(identifier)
        try:
            pipe = self._client.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            count, ttl = pipe.execute()
            if int(ttl) < 0:
                self._client.expire(key, self._window)
            if int(count) > self._max_failures:
                self._give_back(key)
                return False
        except redis.RedisError as e:
            _log_store_unavailable("reserve", e, self._key_prefix)
            return True
        return True

    def confirm_failure(self, identifier: str) -> None:
        """Settle a reserved attempt as a failed guess, restarting the account's window.

        If the key is gone (it expired, or a reset landed while the password was being
        checked) it is recreated at one with the window, so the failure is not lost.
        """
        key = self._key(identifier)
        try:
            if not self._client.expire(key, self._window):
                self._client.set(key, 1, ex=self._window, nx=True)
        except redis.RedisError as e:
            _log_store_unavailable("confirm_failure", e, self._key_prefix)

    def release(self, identifier: str) -> None:
        """Give a reserved attempt back, leaving the expiry where it was."""
        try:
            self._give_back(self._key(identifier))
        except redis.RedisError as e:
            _log_store_unavailable("release", e, self._key_prefix)

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
        """Return whether the account has reached the failure threshold.

        Read-only: an attempt is gated with :meth:`reserve`, not with this.
        """
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

    Gates ``POST /login`` only. A wrong password anywhere still spends from this counter,
    including one posted with an activation link (see
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


@lru_cache
def get_current_password_throttle() -> LoginThrottle:
    """Return the process-wide current-password throttle, Redis-backed when configured.

    Gates ``PUT /users/me/password`` and ``DELETE /users/me`` together, keyed on the
    signed-in account's id, under its own Redis key prefix. A wrong current password on
    either route spends from it, never from :func:`get_login_throttle`, so a stolen
    session cannot lock the owner out of signing in; a locked login does not gate these
    routes either. The module docstring records why the budgets add up.

    :return: The current-password throttle.
    """
    return _build_throttle(RECONFIRM_KEY_PREFIX)
