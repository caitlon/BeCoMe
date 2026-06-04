"""Shared client-IP extraction for middleware and security logging."""

from starlette.requests import Request


def get_client_ip(request: Request | None) -> str:
    """Extract the client IP, honouring a reverse-proxy forwarded header.

    Prefers the first entry of ``X-Forwarded-For`` (the original client behind a
    reverse proxy), then the direct peer address.

    :param request: Incoming request, or ``None`` when unavailable.
    :return: Client IP address, or ``"unknown"`` when it cannot be determined.
    """
    if request is None:
        return "unknown"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
