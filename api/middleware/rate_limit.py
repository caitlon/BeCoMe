"""Rate limiting configuration for API endpoints."""

import logging

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.responses import Response

from api.config import Settings, get_settings
from api.utils.client_ip import get_client_ip

logger = logging.getLogger("api.ratelimit")

# Global per-client ceilings applied to every route by SlowAPIMiddleware, so no
# endpoint is ever left completely unthrottled. Stricter per-route limits still
# apply on top of these.
LIMIT_DEFAULT = "300/minute"
LIMIT_DEFAULT_BURST = "20/second"
# Limits used when the Redis store is unreachable: the limiter degrades to
# per-instance in-memory limiting instead of letting requests through unthrottled.
LIMIT_FALLBACK = "60/minute"


def build_limiter(settings: Settings) -> Limiter:
    """Create the slowapi Limiter, backed by Redis when configured.

    Uses ``settings.redis_url`` as the storage backend so counters are shared across
    replicas (M6); without it slowapi falls back to in-memory. ``default_limits`` plus
    ``SlowAPIMiddleware`` (wired in ``create_app``) cap every route, so an endpoint
    without an explicit decorator is still bounded. ``in_memory_fallback`` keeps limiting
    working during a Redis outage -- it is checked before ``swallow_errors``, so a store
    failure degrades to per-instance in-memory limits rather than disabling limiting
    entirely. ``swallow_errors`` remains a last-resort guard so a store hiccup cannot turn
    into a 500. Limiting is disabled only under the TESTING flag.

    :param settings: Application settings.
    :return: A configured slowapi Limiter.
    """
    return Limiter(
        key_func=get_client_ip,
        enabled=not settings.testing,
        storage_uri=settings.redis_url or None,
        default_limits=[LIMIT_DEFAULT, LIMIT_DEFAULT_BURST],
        in_memory_fallback_enabled=True,
        in_memory_fallback=[LIMIT_FALLBACK],
        swallow_errors=True,
    )


# Rate limiting is disabled only while the automated test suite runs (TESTING flag).
# Deployed profiles, including staging, keep limiting enabled.
limiter = build_limiter(get_settings())

# Rate limit constants for different endpoint types
LIMIT_AUTH_ENDPOINTS = "5/minute"  # Login, register - strict to prevent brute-force
LIMIT_PWD_RESET = "3/minute"  # noqa: S105 -- password-reset rate window, not a credential
LIMIT_STANDARD = "60/minute"  # Normal API endpoints
LIMIT_WRITE = "30/minute"  # Writes that also trigger a DB write plus recalculation
LIMIT_UPLOAD = "10/minute"  # File uploads - prevent abuse
LIMIT_PHOTO = "120/minute"  # Public photo proxy reads (browser-cached avatars)


def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Log a rate-limit violation, then delegate to the slowapi handler.

    Wraps slowapi's built-in ``_rate_limit_exceeded_handler`` so throttling
    events leave a trace. The dependency on slowapi's private handler is
    deliberate: the library documents this exact composition pattern.

    :param request: The throttled request
    :param exc: The rate-limit exception
    :return: The slowapi 429 response
    """
    logger.warning(
        "Rate limit exceeded",
        extra={
            "event": "rate_limit_exceeded",
            "ip": get_client_ip(request),
            "path": request.url.path,
            "request_id": getattr(request.state, "request_id", None),
        },
    )
    return _rate_limit_exceeded_handler(request, exc)
