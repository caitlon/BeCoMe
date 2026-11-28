"""Hourly caps on assistant chat messages: per user, per client address and across all users.

Modeled on ``api/auth/login_throttle.py``: Redis-backed when a store is configured and
keyed on a hash of the identifier so no raw id sits in the store. It does not share that
module's failure rule: the login throttle fails open, while this one fails closed and
refuses the turn when Redis errors. Unlike the login throttle this is a fixed-window counter,
not a lockout: the window opens with a user's first message and closes an hour later however
many messages follow, because a later message never moves the expiry. A refused message is not
counted: like the login throttle's reservation, a caller past the budget is refused and its
increment is given back. In memory the refused message is never stored. In Redis the increment
sits one above the budget until the guarded script gives it back a moment later, and if that
give-back fails with a store error the counter stays above the budget until the window closes.

The Redis backend runs ``SET key 0 EX <ttl> NX`` and ``INCR key`` in one transaction, so
a counter is created with its TTL in the same step that first increments it. A crash or
a lost connection between two separate calls could otherwise leave a counter with no
expiry, and that user would stay locked out for good.

The global ceiling is the same counter under one fixed key, :data:`GLOBAL_KEY`, with its own
budget, so it bounds what all users together can spend in an hour. Both backends count any key:
``hit``, ``charge`` and ``retry_after`` are the per-user forms and pass the user's digest to
``hit_key``, ``charge_key`` and ``retry_after_key``, so the store failure, the zero limit and the
remaining window apply to the global key as well. Its Redis key is ``assistant:chat:all``, which
no user digest can equal.

The per-address cap is the same counter once more, under a key made by :func:`address_key`:
``addr:`` and a keyed hash of the client address, so its Redis key,
``assistant:chat:addr:<hash>``, equals neither a user digest nor the global key. Both chat routes
count under that one key. An IPv6 address counts as its /64 network, because one subscriber
usually holds a whole /64 and could otherwise take a fresh address for each message, and an
IPv4-mapped IPv6 address counts as its IPv4 address. The hash is an HMAC under the server's
log-hashing key, not a plain digest: the IPv4 space is small enough to enumerate, so an unkeyed
hash of an address could be reversed from the store or from a log. Fixed windows allow up to
twice the cap across a window edge (the cap's worth at the end of one window and again at the
start of the next).

A message can be given back: ``charge`` and ``charge_key`` return a :class:`Charge` that records
what was counted and where, and ``refund`` undoes exactly that charge, on the backend that took it,
and only if it was allowed and stored something: a charge refused by the budget was never counted,
and one made under a zero limit stored nothing, so neither has anything to give back. The user's
message is given back when the global ceiling refuses it, so a refusal that is not the user's
doing leaves the user's budget whole. A refund never creates a counter: the in-memory one acts
only while the window the charge opened in is still open, and the Redis one runs a Lua script that
decrements a key only while it exists and is above zero, because a bare ``DECR`` on an expired key
would create ``-1`` with no expiry and lock the user out for good. The accepted trade-off: a Redis
refund or give-back that lands after the window rolled over takes one message off the new window.

A limit of zero switches the cap off; both backends then allow everything without
touching their store. A deployed service refuses a zero limit at startup
(``Settings._validate_assistant_deploy``), so that is for a laptop only.

A Redis error does not open the cap and is not counted anywhere else: ``charge_key`` raises
:class:`~api.assistant.errors.AssistantUnavailableError`, so the turn is refused with the fixed
503 of an unreachable backend, not with a 429 that blames the caller. A per-process count
that starts at zero would give a user who spent the hour in Redis a second budget as soon as
the store failed on writes (a read-only replica, a full memory) while it still answered
reads. The in-memory throttle used when no store is configured is unaffected. Charges the
request already took are given back by the callers in :mod:`api.assistant.deps`, as for any
later refusal.

A refused message also learns how long the refusal lasts: ``retry_after`` reports the
seconds until the window closes, for the ``Retry-After`` header of the refusal. When the
store cannot be read, it answers with the full window, the longest the wait can be.

The Redis key holds an unkeyed digest of the user id. Never log it: anyone holding the
logs could hash a known id and confirm it appears.
"""

import hashlib
import hmac
import ipaddress
import logging
import math
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol, runtime_checkable
from uuid import UUID

import redis

from api.assistant.errors import AssistantUnavailableError
from api.config import get_settings
from api.redis_error_text import drop_pipeline_command

logger = logging.getLogger("api.security")

WINDOW_SECONDS = 60 * 60

KEY_PREFIX = "assistant:chat"

# The one key every message is also counted under, for the global ceiling.
GLOBAL_KEY = "all"

# What an address key starts with; no user digest (hex only) or :data:`GLOBAL_KEY` contains it.
ADDRESS_KEY_PREFIX = "addr:"

# The prefix length an IPv6 address is cut to before it is counted.
_IPV6_NETWORK_BITS = 64

# Decrement a counter only while it exists and is above zero. Atomic, so an expired key is never
# recreated by a refund or by the give-back of a refused charge; DECR on an existing key keeps
# its TTL.
_REFUND_SCRIPT = """
local value = redis.call('GET', KEYS[1])
if value and tonumber(value) > 0 then
    redis.call('DECR', KEYS[1])
end
return 0
"""


@dataclass(frozen=True)
class Charge:
    """One message counted against a key, with what a refund needs to undo exactly that.

    :param key: What the message was counted under: a user's digest, :data:`GLOBAL_KEY` or an
        :func:`address_key`. Never log it.
    :param allowed: Whether the message was within budget.
    :param in_store: True when Redis took the charge, False when an in-memory table did or the
        limit is zero and nothing was stored.
    :param window_opened: The monotonic time the in-memory window opened at, or None for a
        charge Redis took or a zero-limit one, which stores nothing and has no window. An
        in-memory refund does nothing once that window has closed or been replaced.
    """

    key: str
    allowed: bool
    in_store: bool = False
    window_opened: float | None = None


def _digest(user_id: UUID) -> str:
    """Return the SHA-256 hex digest of a user id, so no raw id is stored.

    Never log this value; see the module docstring.

    :param user_id: The user id to hash.
    :return: Hex digest, safe to use as a Redis key component.
    """
    return hashlib.sha256(str(user_id).encode()).hexdigest()


def _address_network(address: str) -> str:
    """Return the form a client address is counted in.

    :param address: The client address as :func:`~api.utils.client_ip.get_client_ip` returns
        it.
    :return: The IPv4 address in its canonical form, an IPv4-mapped IPv6 address as its IPv4
        address, any other IPv6 address as its /64 network, and a value that is not an address
        (the unverified-origin sentinel, ``unknown``) as it is.
    """
    try:
        parsed = ipaddress.ip_address(address.strip())
    except ValueError:
        return address
    if isinstance(parsed, ipaddress.IPv4Address):
        return str(parsed)
    if parsed.ipv4_mapped is not None:
        return str(parsed.ipv4_mapped)
    return str(ipaddress.ip_network((parsed, _IPV6_NETWORK_BITS), strict=False))


def address_key(address: str) -> str:
    """Return the throttle key a client address is counted under.

    The key is an HMAC-SHA-256 of the address's network form (see :func:`_address_network`),
    under ``log_hash_key`` when it is set and ``secret_key`` otherwise, the key
    :func:`~api.auth.logging.hash_email` uses, and with a domain prefix so that no other keyed
    hash of the same text equals it. Rotating the fallback key starts every address on a fresh
    count. Never log the result or the address behind it.

    :param address: The client address as :func:`~api.utils.client_ip.get_client_ip` returns
        it.
    :return: ``addr:`` and the hex HMAC, safe to use as a Redis key component.
    """
    settings = get_settings()
    key = (settings.log_hash_key or settings.secret_key).encode()
    message = f"assistant-address:{_address_network(address)}".encode()
    return f"{ADDRESS_KEY_PREFIX}{hmac.new(key, message, hashlib.sha256).hexdigest()}"


def _log_store_unavailable(exc: redis.RedisError) -> None:
    """Record a throttle store that could not be reached, before the turn is refused.

    ERROR, not WARNING, like the login throttle's own record: it marks the outage, and a lower
    level would let every assistant turn be refused for as long as Redis is down without anyone
    seeing it.

    :param exc: The Redis error that refused the turn.
    """
    drop_pipeline_command(exc)
    logger.error(
        "Assistant throttle store unavailable, turn refused",
        extra={"event": "assistant_throttle_unavailable"},
        # exc_info: the traceback names the Redis error class and the server's reason, which
        # tells a lost connection from a store that refuses writes; the command text of the
        # pipeline is dropped first, so it holds no key.
        exc_info=exc,
    )


@runtime_checkable
class AssistantThrottle(Protocol):
    """Backend counting how many assistant messages a user, or one fixed key, has sent this hour."""

    def hit(self, user_id: UUID) -> bool: ...

    def retry_after(self, user_id: UUID) -> int: ...

    def hit_key(self, key: str) -> bool: ...

    def retry_after_key(self, key: str) -> int: ...

    def charge(self, user_id: UUID) -> Charge: ...

    def charge_key(self, key: str) -> Charge: ...

    def refund(self, charge: Charge) -> None: ...


class InMemoryAssistantThrottle:
    """Process-local throttle for dev and tests (not shared across processes).

    Safe to call from a thread pool: one lock guards the table.

    :param max_per_hour: Messages allowed per key (one user, one address, or everyone for the
        global ceiling) within one window; 0 means no limit.
    :param window_seconds: Length of the window, in seconds.
    """

    def __init__(self, max_per_hour: int, window_seconds: int = WINDOW_SECONDS) -> None:
        self._max = max_per_hour
        self._window = window_seconds
        # digest -> (messages in the current window, when the window opened)
        self._counts: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def hit(self, user_id: UUID) -> bool:
        """Record one message and report whether the user is still within budget.

        :param user_id: The user sending the message.
        :return: True when this message is allowed, False when this window's budget
            is already spent.
        """
        return self.charge(user_id).allowed

    def hit_key(self, key: str) -> bool:
        """Record one message under a key and report whether it is still within budget.

        :param key: What the message is counted under: a user's digest,
            :data:`GLOBAL_KEY` or an :func:`address_key`.
        :return: True when this message is allowed, False when this window's budget
            is already spent.
        """
        return self.charge_key(key).allowed

    def charge(self, user_id: UUID) -> Charge:
        """Record one message and return the charge, so it can be given back.

        :param user_id: The user sending the message.
        :return: The charge; ``allowed`` is False when this window's budget is already spent.
        """
        return self.charge_key(_digest(user_id))

    def charge_key(self, key: str) -> Charge:
        """Record one message under a key and return the charge, so it can be given back.

        A refused message is not counted: the count stays as it was found, so a refusal never
        leaves the key more spent than the messages that were let through.

        :param key: What the message is counted under: a user's digest,
            :data:`GLOBAL_KEY` or an :func:`address_key`.
        :return: The charge; ``allowed`` is False when this window's budget is already spent.
        """
        if self._max == 0:
            return Charge(key, allowed=True)
        now = time.monotonic()
        with self._lock:
            # Drop every window that has closed, so the table holds only users active
            # within the last hour rather than every user the process has ever seen.
            self._counts = {
                k: (count, opened)
                for k, (count, opened) in self._counts.items()
                if now - opened < self._window
            }
            count, opened = self._counts.get(key, (0, now))
            allowed = count + 1 <= self._max
            if allowed:
                self._counts[key] = (count + 1, opened)
        return Charge(key, allowed=allowed, window_opened=opened)

    def refund(self, charge: Charge) -> None:
        """Give back a message, if its window is still the one it was counted in.

        Does nothing for a charge that was refused, a zero-limit one or one taken by another
        store, and when the key's window has closed or been replaced since. It never creates an
        entry.

        :param charge: The charge to undo.
        """
        if not charge.allowed or charge.window_opened is None:
            return
        now = time.monotonic()
        with self._lock:
            entry = self._counts.get(charge.key)
            if entry is None:
                return
            count, opened = entry
            if opened != charge.window_opened or now - opened >= self._window or count <= 0:
                return
            self._counts[charge.key] = (count - 1, opened)

    def remaining(self, key: str) -> int | None:
        """Report how long until a key's open window closes.

        :param key: The key to look up.
        :return: Whole seconds until the window closes, at least 1, or None when the key
            has no open window.
        """
        now = time.monotonic()
        with self._lock:
            entry = self._counts.get(key)
        if entry is None or now - entry[1] >= self._window:
            return None
        return max(1, math.ceil(self._window - (now - entry[1])))

    def retry_after(self, user_id: UUID) -> int:
        """Report how long until the user's window closes; call it after a refusal.

        :param user_id: The user whose message was refused.
        :return: Whole seconds until the window closes, at least 1.
        """
        return self.retry_after_key(_digest(user_id))

    def retry_after_key(self, key: str) -> int:
        """Report how long until a key's window closes; call it after a refusal.

        :param key: The key whose message was refused.
        :return: Whole seconds until the window closes, at least 1.
        """
        return self.remaining(key) or 1


class RedisAssistantThrottle:
    """Redis-backed throttle shared across processes; refuses every turn on a store outage.

    :param client: Redis client for the shared store.
    :param max_per_hour: Messages allowed per key (one user, one address, or everyone for the
        global ceiling) within one window; 0 means no limit.
    :param window_seconds: Length of the window, in seconds.
    """

    def __init__(
        self, client: redis.Redis, *, max_per_hour: int, window_seconds: int = WINDOW_SECONDS
    ) -> None:
        self._client = client
        self._max = max_per_hour
        self._window = window_seconds

    def close(self) -> None:
        """Close the Redis client, for application shutdown."""
        self._client.close()

    def hit(self, user_id: UUID) -> bool:
        """Count one message and report whether the user is within budget.

        :param user_id: The user sending the message.
        :return: True when this message is allowed, False when the budget is spent.
        :raises AssistantUnavailableError: When the store cannot be reached.
        """
        return self.charge(user_id).allowed

    def hit_key(self, key: str) -> bool:
        """Count one message under a key and report whether it is within budget.

        :param key: What the message is counted under: a user's digest,
            :data:`GLOBAL_KEY` or an :func:`address_key`.
        :return: True when this message is allowed, False when the budget is spent.
        :raises AssistantUnavailableError: When the store cannot be reached.
        """
        return self.charge_key(key).allowed

    def charge(self, user_id: UUID) -> Charge:
        """Count one message and return the charge, so it can be given back.

        :param user_id: The user sending the message.
        :return: The charge; ``allowed`` is False when the budget is spent.
        :raises AssistantUnavailableError: When the store cannot be reached.
        """
        return self.charge_key(_digest(user_id))

    def charge_key(self, key: str) -> Charge:
        """Count one message under a key and return the charge, so it can be given back.

        A refused message is not counted: its increment is given back by the same guarded script
        a refund uses, so the key never creates itself or loses its TTL. When that give-back
        fails, the error is logged and not raised, and the message is still refused. A store
        error on the count itself is logged and raised as :class:`AssistantUnavailableError`:
        a read timeout after Redis ran the count can leave at most one message counted until the
        window closes, and no count is kept anywhere else.

        :param key: What the message is counted under: a user's digest,
            :data:`GLOBAL_KEY` or an :func:`address_key`.
        :return: The charge; ``allowed`` is False when the budget is spent.
        :raises AssistantUnavailableError: When the store cannot be reached.
        """
        if self._max == 0:
            return Charge(key, allowed=True)
        redis_key = f"{KEY_PREFIX}:{key}"
        try:
            pipe = self._client.pipeline(transaction=True)
            pipe.set(redis_key, 0, ex=self._window, nx=True)
            pipe.incr(redis_key)
            results = pipe.execute()
        except redis.RedisError as e:
            _log_store_unavailable(e)
            raise AssistantUnavailableError("the assistant's throttle store is unavailable") from e
        if int(results[1]) <= self._max:
            return Charge(key, allowed=True, in_store=True)
        try:
            self._client.eval(_REFUND_SCRIPT, 1, redis_key)
        except redis.RedisError as e:
            logger.warning(
                "Assistant throttle store unavailable, refused message not given back",
                extra={"event": "assistant_throttle_giveback_unavailable"},
                # exc_info: a Redis error from a single command names the failing call, or the
                # store's host and port if it cannot connect; never a key, password or user text.
                exc_info=e,
            )
        return Charge(key, allowed=False, in_store=True)

    def refund(self, charge: Charge) -> None:
        """Give back a message on the backend that took it.

        Does nothing for a charge that was refused, which was never counted, or for one Redis
        did not take, a zero-limit one. A charge Redis took is undone by one script that
        decrements the key only while it exists and is above zero, so an expired window is
        never recreated. A store error is logged and not raised: the charge is in Redis, and
        the message stays spent there until its window closes.

        :param charge: The charge to undo.
        """
        if not charge.allowed or not charge.in_store:
            return
        try:
            self._client.eval(_REFUND_SCRIPT, 1, f"{KEY_PREFIX}:{charge.key}")
        except redis.RedisError as e:
            logger.warning(
                "Assistant throttle store unavailable, message not given back",
                extra={"event": "assistant_throttle_refund_unavailable"},
                # exc_info: a Redis error from a single command names the failing call, or the
                # store's host and port if it cannot connect; never a key, password or user text.
                exc_info=e,
            )

    def retry_after(self, user_id: UUID) -> int:
        """Report how long until the user's window closes; call it after a refusal.

        A key that is gone means the window closed just now, so the wait is one second.
        A key with no expiry cannot be told apart from a fresh window, so it gets the
        full window. An unreachable store gets the full window too, the longest the wait can be.

        :param user_id: The user whose message was refused.
        :return: Whole seconds until the window closes, at least 1.
        """
        return self.retry_after_key(_digest(user_id))

    def retry_after_key(self, key: str) -> int:
        """Report how long until a key's window closes; call it after a refusal.

        The same answers as :meth:`retry_after`, for a key that is not a user.

        :param key: The key whose message was refused.
        :return: Whole seconds until the window closes, at least 1.
        """
        try:
            ttl = int(self._client.ttl(f"{KEY_PREFIX}:{key}"))
        except redis.RedisError as e:
            logger.warning(
                "Assistant throttle store unavailable, retry time not known",
                extra={"event": "assistant_throttle_retry_unavailable"},
                # exc_info: a Redis error from a single command names the failing call, or the
                # store's host and port if it cannot connect; never a key, password or user text.
                exc_info=e,
            )
            return self._window
        if ttl == -2:
            return 1
        if ttl == -1:
            return self._window
        return max(1, ttl)


def _build_throttle(max_per_hour: int) -> AssistantThrottle:
    """Build a throttle with the given budget, Redis-backed when a store is configured.

    :param max_per_hour: Messages allowed within one window; 0 means no limit.
    :return: The throttle backend.
    """
    settings = get_settings()
    if settings.redis_url:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        return RedisAssistantThrottle(client, max_per_hour=max_per_hour)
    return InMemoryAssistantThrottle(max_per_hour=max_per_hour)


@lru_cache
def get_assistant_throttle() -> AssistantThrottle:
    """Return the process-wide per-user assistant throttle, Redis-backed when configured.

    :return: The throttle backend.
    """
    return _build_throttle(get_settings().assistant_rate_limit_per_hour)


@lru_cache
def get_assistant_global_throttle() -> AssistantThrottle:
    """Return the process-wide throttle for all users together, Redis-backed when configured.

    Hit it under :data:`GLOBAL_KEY`; its budget is ``assistant_global_turns_per_hour``.

    :return: The throttle backend.
    """
    return _build_throttle(get_settings().assistant_global_turns_per_hour)


@lru_cache
def get_assistant_address_throttle() -> AssistantThrottle:
    """Return the process-wide per-address throttle, Redis-backed when configured.

    Charge it under :func:`address_key`; its budget is ``assistant_address_turns_per_hour``.

    :return: The throttle backend.
    """
    return _build_throttle(get_settings().assistant_address_turns_per_hour)
