"""Rate limiting configuration for API endpoints."""

import logging

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.responses import Response

from api.config import get_settings
from api.utils.client_ip import get_client_ip

logger = logging.getLogger("api.ratelimit")

# Disable rate limiting only while the automated test suite runs (TESTING flag).
# Deployed profiles, including staging, keep limiting enabled.
limiter = Limiter(key_func=get_client_ip, enabled=not get_settings().testing)

# Rate limit constants for different endpoint types
LIMIT_AUTH_ENDPOINTS = "5/minute"  # Login, register - strict to prevent brute-force
LIMIT_PWD_RESET = "3/minute"  # noqa: S105 -- password-reset rate window, not a credential
LIMIT_STANDARD = "60/minute"  # Normal API endpoints
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
