"""Checks of the backends the application depends on, made once when the process starts.

Until now a backend was first touched by the first user who needed it, so a Redis that
refused the service's password was found when someone could not log in, while ``/health``
answered 200. These checks reach each backend once at startup and log a failure at ERROR,
the level Sentry turns into an event and Better Stack alerts on. They only log: a provider
outage must not stop a deploy or a wake from App Sleep, and the app is serving before they
finish, because the lifespan runs them as a background task.
"""

import asyncio
import logging

import redis

from api.config import Settings

logger = logging.getLogger("api.startup_checks")


def _ping_redis(url: str) -> None:
    """Connect to Redis, send ``PING`` and close the client.

    The timeouts are those of the app's own Redis clients, so the check waits as long as a
    request would.

    :param url: The Redis URL.
    :raises redis.RedisError: If the server cannot be reached or refuses the credentials.
    """
    client = redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
    try:
        client.ping()
    finally:
        client.close()


async def check_redis(settings: Settings) -> None:
    """Ping the Redis the app uses for login state, and log an ERROR if it does not answer.

    The same Redis holds the token revocation list, the user cache and the throttles, so a
    server that cannot be reached or that refuses the password breaks login whether the
    assistant is enabled or not. Nothing is checked when ``REDIS_URL`` is not set. The record
    carries the class of the error as ``reason`` and never its text, which can hold the URL.

    :param settings: Application settings.
    """
    if not settings.redis_url:
        return
    try:
        await asyncio.to_thread(_ping_redis, settings.redis_url)
    except Exception as exc:
        logger.error(
            "Redis check failed at startup",
            extra={"event": "redis_check_failed", "reason": type(exc).__name__},
        )
        return
    logger.info("Redis answered at startup", extra={"event": "redis_checked"})


async def run_startup_checks(settings: Settings) -> None:
    """Check every backend of this process at once, never raising.

    A failure is logged by the check that met it; a fault in a check itself is logged here,
    and does not stop the other checks, so the background task that runs this ends quietly
    whatever happens.

    :param settings: Application settings.
    """
    checks = [check_redis(settings)]
    for outcome in await asyncio.gather(*checks, return_exceptions=True):
        if isinstance(outcome, Exception):
            logger.error(
                "Startup checks crashed",
                extra={"event": "startup_checks_crashed", "reason": type(outcome).__name__},
            )
