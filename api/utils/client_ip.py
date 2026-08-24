"""Shared client-IP extraction for middleware and security logging."""

import hmac

from starlette.requests import Request

from api.config import get_settings

# Rate-limit / log key for any request whose client address the origin cannot vouch
# for: one that should have transited Cloudflare but carried no matching origin-verify
# secret, and one arriving at a deployed service that has no secret configured at all.
# Bucketing all such traffic under one constant stops a direct *.up.railway.app caller
# from spoofing an arbitrary client IP: it can neither mint fresh rate-limit buckets
# nor poison logs with a chosen address.
_UNVERIFIED_ORIGIN = "unverified-origin"


def get_client_ip(request: Request | None) -> str:
    """Resolve the client IP used for rate limiting and security logging.

    The trust model depends on whether a Cloudflare origin secret is configured
    (``CLOUDFLARE_ORIGIN_SECRET``, set on every deployed service):

    - **Secret configured**: a request is trusted only when it carries the matching
      ``X-Origin-Verify`` header that Cloudflare injects via a Transform Rule.
      Trusted requests use ``CF-Connecting-IP`` (the real client, which Cloudflare sets
      and a client cannot forge). A request without the secret reached the bare origin
      directly, bypassing Cloudflare, so its client-supplied headers are untrusted and
      it is keyed under a single constant instead of a spoofable address.
    - **No secret on a deployed service**: the same constant. The invariants in
      :meth:`api.config.Settings._validate_deploy_invariants` refuse to boot a deploy
      without the secret, so this branch should be unreachable -- but the app runs
      behind a proxy chain it cannot authenticate, and ``request.client.host`` is
      whatever that chain put in ``X-Forwarded-For`` (uvicorn runs with
      ``--forwarded-allow-ips='*'``). Falling back to a constant keeps a missing
      variable from quietly turning an unauthenticated header into the rate-limit key.
    - **No secret, not deployed** (local development, CI): there is no proxy in front,
      so the transport peer really is the client. ``X-Forwarded-For`` stays untrusted.

    :param request: Incoming request, or ``None`` when unavailable.
    :return: Client IP, the unverified-origin sentinel, or ``"unknown"``.
    """
    if request is None:
        return "unknown"
    settings = get_settings()
    secret = settings.cloudflare_origin_secret
    if secret:
        verify = request.headers.get("X-Origin-Verify")
        # Compare as bytes: compare_digest raises TypeError on a non-ASCII str, which
        # would turn a junk header into a 500 instead of the unverified-origin path.
        if verify and hmac.compare_digest(verify.encode(), secret.encode()):
            cloudflare_ip = request.headers.get("CF-Connecting-IP")
            if cloudflare_ip:
                return cloudflare_ip.strip()
            return request.client.host if request.client else "unknown"
        return _UNVERIFIED_ORIGIN
    if settings.is_deploy:
        return _UNVERIFIED_ORIGIN
    # Local development: no proxy in front, so the transport peer is the real client.
    # X-Forwarded-For is attacker-controlled, so it must never seed the rate-limit
    # key or the log IP.
    return request.client.host if request.client else "unknown"
