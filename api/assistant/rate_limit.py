"""Per-user hourly cap on assistant chat messages.

Modeled on ``api/auth/login_throttle.py``: Redis-backed when a store is configured,
keyed on a hash of the identifier so no raw id sits in the store, and open when Redis
errors. Unlike the login throttle this is a plain fixed-window counter, not a lockout:
the window opens with a user's first message and closes an hour later however many
messages follow, because a later message never moves the expiry.

The Redis backend runs ``SET key 0 EX <ttl> NX`` and ``INCR key`` in one transaction, so
a counter is created with its TTL in the same step that first increments it. A crash or
a lost connection between two separate calls could otherwise leave a counter with no
expiry, and that user would stay locked out for good.

A limit of zero switches the cap off; both backends then allow everything without
touching their store.

Failing open on a Redis error is deliberate. The assistant runs only on a developer's
own machine (``Settings._validate_assistant_local_only`` refuses to start any deployed
profile with it on), and deployed profiles refuse to start without Redis anyway, so a
store outage here costs one developer an unenforced local cap, not a public endpoint its
protection.

The Redis key holds an unkeyed digest of the user id. Never log it: anyone holding the
logs could hash a known id and confirm it appears.
"""

import hashlib
import logging
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


def _digest(user_id: UUID) -> str:
    """Return the SHA-256 hex digest of a user id, so no raw id is stored.

    Never log this value; see the module docstring.

    :param user_id: The user id to hash.
    :return: Hex digest, safe to use as a Redis key component.
    """
    return hashlib.sha256(str(user_id).encode()).hexdigest()


def _log_store_unavailable(exc: redis.RedisError) -> None:
    """Record a throttle store that could not be reached.

    ERROR, not WARNING, for the reason the login throttle's own record is: the message
    this happens during still goes through, so nothing else marks the outage, and a
    lower level would let the cap stay silently off for as long as Redis is down.

    :param exc: The Redis error that caused the fallback.
    """
    logger.error(
        "Assistant throttle store unavailable, hourly cap not enforced",
        extra={"event": "assistant_throttle_unavailable"},
        exc_info=exc,
    )


@runtime_checkable
class AssistantThrottle(Protocol):
    """Backend counting how many assistant messages a user has sent this hour."""

    def hit(self, user_id: UUID) -> bool: ...


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
        if self._max == 0:
            return True
        now = time.monotonic()
        key = _digest(user_id)
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


class RedisAssistantThrottle:
    """Redis-backed throttle shared across processes; fails open on a store outage.

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

    def hit(self, user_id: UUID) -> bool:
        """Count one message and report whether the user is within budget.

        :param user_id: The user sending the message.
        :return: True when this message is allowed, False when the budget is spent.
        """
        if self._max == 0:
            return True
        key = f"{KEY_PREFIX}:{_digest(user_id)}"
        try:
            pipe = self._client.pipeline(transaction=True)
            pipe.set(key, 0, ex=self._window, nx=True)
            pipe.incr(key)
            results = pipe.execute()
        except redis.RedisError as e:
            _log_store_unavailable(e)
            return True
        return int(results[1]) <= self._max


@lru_cache
def get_assistant_throttle() -> AssistantThrottle:
    """Return the process-wide assistant throttle, Redis-backed when configured.

    :return: The throttle backend.
    """
    settings = get_settings()
    if settings.redis_url:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        return RedisAssistantThrottle(client, max_per_hour=settings.assistant_rate_limit_per_hour)
    return InMemoryAssistantThrottle(max_per_hour=settings.assistant_rate_limit_per_hour)
