"""Rate limiting configuration for API endpoints."""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.config import get_settings


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


# Disable rate limiting only while the automated test suite runs (TESTING flag).
# Deployed profiles, including staging, keep limiting enabled.
limiter = Limiter(key_func=_get_client_ip, enabled=not get_settings().testing)

# Rate limit constants for different endpoint types
LIMIT_AUTH_ENDPOINTS = "5/minute"  # Login, register - strict to prevent brute-force
LIMIT_PWD_RESET = "3/minute"  # Password reset/change - very strict
LIMIT_STANDARD = "60/minute"  # Normal API endpoints
LIMIT_UPLOAD = "10/minute"  # File uploads - prevent abuse
LIMIT_PHOTO = "120/minute"  # Public photo proxy reads (browser-cached avatars)
