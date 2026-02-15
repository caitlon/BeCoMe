"""Rate limiting configuration for API endpoints."""

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxies.

    Checks X-Forwarded-For header first (for reverse proxy setups),
    falls back to direct connection address.

    :param request: FastAPI request object
    :return: Client IP address string
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take first IP (original client) from comma-separated list
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Disable rate limiting during tests (TESTING env var set by pytest)
_is_testing = os.environ.get("TESTING", "").lower() in ("1", "true", "yes")

# Global limiter instance - use in route decorators
limiter = Limiter(key_func=_get_client_ip, enabled=not _is_testing)

# Rate limit constants for different endpoint types
LIMIT_AUTH_ENDPOINTS = "5/minute"  # Login, register - strict to prevent brute-force
LIMIT_PASSWORD_RESET = "3/minute"  # Password reset/change - very strict
LIMIT_STANDARD = "60/minute"  # Normal API endpoints
LIMIT_UPLOAD = "10/minute"  # File uploads - prevent abuse
