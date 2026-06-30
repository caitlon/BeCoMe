"""Shared client-IP extraction for middleware and security logging."""

import hmac

from starlette.requests import Request

from api.config import get_settings

# Rate-limit / log key for any request that should have transited Cloudflare but did
# not carry the origin-verify secret. Bucketing all such traffic under one constant
# stops a direct *.up.railway.app caller from spoofing an arbitrary client IP: it can
# neither mint fresh rate-limit buckets nor poison logs with a chosen address.
_UNVERIFIED_ORIGIN = "unverified-origin"


def get_client_ip(request: Request | None) -> str:
    """Resolve the client IP used for rate limiting and security logging.

    The trust model depends on whether a Cloudflare origin secret is configured
    (``CLOUDFLARE_ORIGIN_SECRET``, set only where Cloudflare fronts the service):

    - **Secret configured** (production): a request is trusted only when it carries the
      matching ``X-Origin-Verify`` header that Cloudflare injects via a Transform Rule.
      Trusted requests use ``CF-Connecting-IP`` (the real client, which Cloudflare sets
      and a client cannot forge). A request without the secret reached the bare origin
      directly, bypassing Cloudflare, so its client-supplied headers are untrusted and
      it is keyed under a single constant instead of a spoofable address.
    - **No secret** (local/dev/staging, no Cloudflare in front): use the first
      ``X-Forwarded-For`` entry, then the direct peer.

    :param request: Incoming request, or ``None`` when unavailable.
    :return: Client IP, the unverified-origin sentinel, or ``"unknown"``.
    """
    if request is None:
        return "unknown"
    secret = get_settings().cloudflare_origin_secret
    if secret:
        verify = request.headers.get("X-Origin-Verify")
        if verify and hmac.compare_digest(verify, secret):
            cloudflare_ip = request.headers.get("CF-Connecting-IP")
            if cloudflare_ip:
                return cloudflare_ip.strip()
            return request.client.host if request.client else "unknown"
        return _UNVERIFIED_ORIGIN
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
