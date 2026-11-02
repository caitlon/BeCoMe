"""ASGI middleware that refuses a request lacking the Cloudflare origin secret.

Cloudflare injects the shared secret as the ``X-Origin-Verify`` request header through a
Transform Rule. A deployed service answers 403 to any request that does not carry it (the
current value, or the previous one during a rotation), on every path and every host name.
Without a verified secret the client address cannot be trusted either, so
:func:`api.utils.client_ip.get_client_ip` keys such a request under one constant.

One request passes without the secret: ``GET /api/v1/health`` addressed to a platform
probe's host name. Railway probes a new deploy with the host name ``healthcheck.railway.app``
and gates the switch to it on the answer, and the image's own ``HEALTHCHECK`` calls the
route on ``localhost``. The route returns only a status and the version.

The refusal is sent directly and the body is never read. ``RequestLoggingMiddleware`` runs
outside this middleware, so its access line records the 403 and the unverified address, and
its ``X-Request-ID`` header is set on it.
"""

import logging

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from api.utils.client_ip import UNVERIFIED_ORIGIN, origin_secret_matches

logger = logging.getLogger("api.request")

ORIGIN_VERIFY_HEADER = "x-origin-verify"

# The route a platform probe may call without the secret.
_PROBE_METHOD = "GET"
_PROBE_PATH = "/api/v1/health"

# Host names a platform probe addresses the route by. Railway sends
# ``healthcheck.railway.app`` when it probes a deploy; ``localhost`` is the image's own
# HEALTHCHECK (docker/Dockerfile, docker/docker-compose.yml).
_PROBE_HOSTS = frozenset({"healthcheck.railway.app", "localhost"})


class OriginLockMiddleware:
    """Answer 403 to a request that does not carry the Cloudflare origin secret.

    :param app: The wrapped ASGI application.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass a verified request or a platform probe through and refuse the rest."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        verify = headers.get(ORIGIN_VERIFY_HEADER)
        if origin_secret_matches(verify) or self._is_platform_probe(scope, headers):
            await self._app(scope, receive, send)
            return

        logger.warning(
            "Request refused: origin not verified",
            extra={
                "event": "origin_refused",
                "reason": "missing_header" if verify is None else "secret_mismatch",
                "request_id": scope.get("state", {}).get("request_id"),
                "method": scope.get("method"),
                "path": scope.get("path"),
                "ip": UNVERIFIED_ORIGIN,
            },
        )
        await self._send_forbidden(send)

    @staticmethod
    def _is_platform_probe(scope: Scope, headers: Headers) -> bool:
        """Return whether the request is a platform health probe.

        :param scope: The ASGI connection scope.
        :param headers: The request headers.
        :return: True for ``GET /api/v1/health`` addressed to a probe's host name.
        """
        if scope.get("method") != _PROBE_METHOD or scope.get("path") != _PROBE_PATH:
            return False
        host = headers.get("host", "").lower().partition(":")[0]
        return host in _PROBE_HOSTS

    @staticmethod
    async def _send_forbidden(send: Send) -> None:
        """Emit a 403 response directly, without running the downstream app.

        ``no-store`` keeps Cloudflare from caching the refusal on a cacheable path.

        :param send: The ASGI send callable.
        """
        body = b'{"detail":"Forbidden"}'
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"),
        ]
        await send({"type": "http.response.start", "status": 403, "headers": headers})
        await send({"type": "http.response.body", "body": body})
