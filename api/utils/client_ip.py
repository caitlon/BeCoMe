"""Shared client-IP extraction for middleware and security logging."""

import hmac

from starlette.requests import Request

from api.config import get_settings

# Rate-limit / log key for any request whose client address the origin cannot vouch
# for. A deployed service refuses a request without the origin-verify secret in
# ``OriginLockMiddleware``, so the constant is the key for what still reaches this
# function unverified: the platform health probe, and a deploy that has no secret
# configured. Bucketing all of it under one constant means a caller can neither mint
# fresh rate-limit buckets nor poison logs with a chosen address.
UNVERIFIED_ORIGIN = "unverified-origin"


def origin_secret_matches(verify: str | None) -> bool:
    """Check an ``X-Origin-Verify`` value against the configured origin secrets.

    The current secret and, during a rotation, the previous one both count. An unset
    secret never matches, so an empty header cannot pass for one.

    :param verify: Value of the ``X-Origin-Verify`` header, or ``None`` when absent.
    :return: True when the value equals a configured, non-empty secret.
    """
    if not verify:
        return False
    settings = get_settings()
    # Compare as bytes: compare_digest raises TypeError on a non-ASCII str, which
    # would turn a junk header into a 500 instead of a refusal.
    candidate = verify.encode()
    matched = False
    for secret in (settings.cloudflare_origin_secret, settings.cloudflare_origin_secret_previous):
        if secret and hmac.compare_digest(candidate, secret.encode()):
            matched = True
    return matched


def get_client_ip(request: Request | None) -> str:
    """Resolve the client IP used for rate limiting and security logging.

    The trust model depends on whether a Cloudflare origin secret is configured
    (``CLOUDFLARE_ORIGIN_SECRET``, set on every deployed service):

    - **Secret configured**: a request is trusted only when it carries a matching
      ``X-Origin-Verify`` header, which Cloudflare injects via a Transform Rule.
      Trusted requests use ``CF-Connecting-IP`` (the real client, which Cloudflare sets
      and a client cannot forge). A deployed service refuses any other request in
      :class:`api.middleware.origin_lock.OriginLockMiddleware`, apart from the platform
      health probe. What still reaches this function without the secret has
      client-supplied headers that are untrusted, so it is keyed under a single
      constant instead of a spoofable address.
    - **No secret on a deployed service**: the same constant. The invariants in
      :meth:`api.config.Settings._validate_deploy_invariants` refuse to boot a deploy
      without the secret, so this branch should be unreachable. Even so, the app runs
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
    if settings.cloudflare_origin_secret:
        if origin_secret_matches(request.headers.get("X-Origin-Verify")):
            cloudflare_ip = request.headers.get("CF-Connecting-IP")
            if cloudflare_ip:
                return cloudflare_ip.strip()
            return request.client.host if request.client else "unknown"
        return UNVERIFIED_ORIGIN
    if settings.is_deploy:
        return UNVERIFIED_ORIGIN
    # Local development: no proxy in front, so the transport peer is the real client.
    # X-Forwarded-For is attacker-controlled, so it must never seed the rate-limit
    # key or the log IP.
    return request.client.host if request.client else "unknown"
