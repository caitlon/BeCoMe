"""Hourly caps on assistant chat messages: one per user and one across all users.

Modeled on ``api/auth/login_throttle.py``: Redis-backed when a store is configured,
keyed on a hash of the identifier so no raw id sits in the store, and counted per process
when Redis errors. Unlike the login throttle this is a plain fixed-window counter, not a lockout:
the window opens with a user's first message and closes an hour later however many
messages follow, because a later message never moves the expiry.

The Redis backend runs ``SET key 0 EX <ttl> NX`` and ``INCR key`` in one transaction, so
a counter is created with its TTL in the same step that first increments it. A crash or
a lost connection between two separate calls could otherwise leave a counter with no
expiry, and that user would stay locked out for good.

The global ceiling is the same counter under one fixed key, :data:`GLOBAL_KEY`, with its own
budget, so it bounds what all users together can spend in an hour. Both backends count any key:
``hit`` and ``retry_after`` are the per-user forms and pass the user's digest to ``hit_key`` and
``retry_after_key``, so the fallback, the zero limit and the remaining window apply to the global
key as well. Its Redis key is ``assistant:chat:all``, which no user digest can equal.

A limit of zero switches the cap off; both backends then allow everything without
touching their store. A deployed service refuses a zero limit at startup
(``Settings._validate_assistant_deploy``), so that is for a laptop only.

A Redis error does not open the cap. The Redis backend owns an in-memory throttle with the
same budget and window and counts there for as long as the store is down, so each process
enforces the cap on its own: with several processes the real ceiling is their number times
the budget, which is still a bound, where an open cap is none. That count restarts with the
process and is lost when Redis comes back; the window of the shared counter is unaffected.

A refused message also learns how long the refusal lasts: ``retry_after`` reports the
seconds until the window closes, for the ``Retry-After`` header of the refusal. When the
store cannot be read, it answers with this process's own remaining window if it holds one
for the key, otherwise the full window, the longest the wait can be; a window left from an
earlier outage can understate the wait, which only makes the client retry early.

The Redis key holds an unkeyed digest of the user id. Never log it: anyone holding the
logs could hash a known id and confirm it appears.
"""

import hashlib
import logging
import math
import threading
import time
from functools import lru_cache
from typing import Protocol, runtime_checkable
from uuid import UUID

import redis

from api.config import get_settings

logger = logging.getLogger("api.security")

WINDOW_SECONDS = 60 * 60

KEY_PREFIX = "assistant:chat"

# The one key every message is also counted under, for the global ceiling.
GLOBAL_KEY = "all"


def _digest(user_id: UUID) -> str:
    """Return the SHA-256 hex digest of a user id, so no raw id is stored.

    Never log this value; see the module docstring.

    :param user_id: The user id to hash.
    :return: Hex digest, safe to use as a Redis key component.
    """
    return hashlib.sha256(str(user_id).encode()).hexdigest()


def _log_store_unavailable(exc: redis.RedisError) -> None:
    """Record a throttle store that could not be reached.

    ERROR, not WARNING, for the reason the login throttle's own record is: nothing else
    marks the outage, and a lower level would let the cap stay on its weaker per-process
    count for as long as Redis is down without anyone seeing it.

    :param exc: The Redis error that caused the fallback.
    """
    logger.error(
        "Assistant throttle store unavailable, hourly cap counted per process",
        extra={"event": "assistant_throttle_unavailable"},
        exc_info=exc,
    )


@runtime_checkable
class AssistantThrottle(Protocol):
    """Backend counting how many assistant messages a user, or one fixed key, has sent this hour."""

    def hit(self, user_id: UUID) -> bool: ...

    def retry_after(self, user_id: UUID) -> int: ...

    def hit_key(self, key: str) -> bool: ...

    def retry_after_key(self, key: str) -> int: ...


class InMemoryAssistantThrottle:
    """Process-local throttle for dev and tests (not shared across processes).

    Safe to call from a thread pool: one lock guards the table.

    :param max_per_hour: Messages allowed per user within one window; 0 means no limit.
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
        return self.hit_key(_digest(user_id))

    def hit_key(self, key: str) -> bool:
        """Record one message under a key and report whether it is still within budget.

        :param key: What the message is counted under: a user's digest, or
            :data:`GLOBAL_KEY`.
        :return: True when this message is allowed, False when this window's budget
            is already spent.
        """
        if self._max == 0:
            return True
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
            count += 1
            self._counts[key] = (count, opened)
        return count <= self._max

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
    """Redis-backed throttle shared across processes; counts per process on a store outage.

    :param client: Redis client for the shared store.
    :param max_per_hour: Messages allowed per user within one window; 0 means no limit.
    :param window_seconds: Length of the window, in seconds.
    """

    def __init__(
        self, client: redis.Redis, *, max_per_hour: int, window_seconds: int = WINDOW_SECONDS
    ) -> None:
        self._client = client
        self._max = max_per_hour
        self._window = window_seconds
        # Counts in place of the store while it is down: same budget, this process only.
        self._fallback = InMemoryAssistantThrottle(max_per_hour, window_seconds)

    def hit(self, user_id: UUID) -> bool:
        """Count one message and report whether the user is within budget.

        :param user_id: The user sending the message.
        :return: True when this message is allowed, False when the budget is spent. While
            the store is down, the answer comes from this process's own count.
        """
        return self.hit_key(_digest(user_id))

    def hit_key(self, key: str) -> bool:
        """Count one message under a key and report whether it is within budget.

        :param key: What the message is counted under: a user's digest, or
            :data:`GLOBAL_KEY`.
        :return: True when this message is allowed, False when the budget is spent. While
            the store is down, the answer comes from this process's own count.
        """
        if self._max == 0:
            return True
        redis_key = f"{KEY_PREFIX}:{key}"
        try:
            pipe = self._client.pipeline(transaction=True)
            pipe.set(redis_key, 0, ex=self._window, nx=True)
            pipe.incr(redis_key)
            results = pipe.execute()
        except redis.RedisError as e:
            _log_store_unavailable(e)
            return self._fallback.hit_key(key)
        return int(results[1]) <= self._max

    def retry_after(self, user_id: UUID) -> int:
        """Report how long until the user's window closes; call it after a refusal.

        A key that is gone means the window closed just now, so the wait is one second.
        A key with no expiry cannot be told apart from a fresh window, so it gets the
        full window. An unreachable store gets the process-local window when this process
        holds one for the key, and the full window otherwise.

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
                exc_info=e,
            )
            remaining = self._fallback.remaining(key)
            return self._window if remaining is None else remaining
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
