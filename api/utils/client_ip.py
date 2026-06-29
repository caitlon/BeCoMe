"""Shared client-IP extraction for middleware and security logging."""

from starlette.requests import Request


def get_client_ip(request: Request | None) -> str:
    """Extract the client IP, honouring reverse-proxy headers.

    Resolution order, most trustworthy first:

    1. ``CF-Connecting-IP`` -- set by the Cloudflare proxy to the real client IP.
       Unlike the leftmost ``X-Forwarded-For`` entry (which the client controls and
       can spoof) this header cannot be forged once traffic arrives via Cloudflare.
    2. First entry of ``X-Forwarded-For`` -- the original client behind a plain
       reverse proxy, used when Cloudflare is absent (local runs or the bare
       ``*.up.railway.app`` domain).
    3. The direct peer address.

    :param request: Incoming request, or ``None`` when unavailable.
    :return: Client IP address, or ``"unknown"`` when it cannot be determined.
    """
    if request is None:
        return "unknown"
    cloudflare_ip = request.headers.get("CF-Connecting-IP")
    if cloudflare_ip:
        return cloudflare_ip.strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
