"""Security headers middleware for HTTP response hardening."""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all HTTP responses.

    Headers protect against:
    - Clickjacking (X-Frame-Options)
    - MIME sniffing (X-Content-Type-Options)
    - XSS in older browsers (X-XSS-Protection)
    - Information leakage (Referrer-Policy, Permissions-Policy)
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request and add security headers to response."""
        response: Response = await call_next(request)

        # Prevent clickjacking - page cannot be embedded in iframe
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS protection for older browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # HTTP Strict Transport Security - force HTTPS for 1 year
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # Control referrer information sent with requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Disable unnecessary browser features
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # Content Security Policy - restrict resource loading
        # Note: 'unsafe-inline' for style-src is required by Tailwind CSS
        # For stricter CSP, configure nonce-based styles in Vite build
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' https://*.blob.core.windows.net data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "upgrade-insecure-requests"
        )

        return response
