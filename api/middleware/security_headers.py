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

        # Explicitly off. The legacy auditor this enables is unreliable, browsers have
        # dropped it, and its blocking mode has itself been an information-leak vector.
        # The Content-Security-Policy below is what actually constrains injection.
        response.headers["X-XSS-Protection"] = "0"

        # HTTP Strict Transport Security - only for HTTPS requests
        # Sending HSTS on HTTP can cause issues in dev/staging
        if request.url.scheme == "https":
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
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "upgrade-insecure-requests"
        )

        return response
