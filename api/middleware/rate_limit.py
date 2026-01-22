"""Rate limiting configuration for API endpoints."""

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


# Global limiter instance - use in route decorators
limiter = Limiter(key_func=_get_client_ip)

# Rate limit constants for different endpoint types
RATE_LIMIT_AUTH = "5/minute"  # Login, register - strict to prevent brute-force
RATE_LIMIT_PASSWORD = "3/minute"  # Password reset/change - very strict
RATE_LIMIT_STANDARD = "60/minute"  # Normal API endpoints
RATE_LIMIT_UPLOAD = "10/minute"  # File uploads - prevent abuse
