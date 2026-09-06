"""Route guard refusing a request that carries no valid Cloudflare Turnstile token.

The token travels in the ``X-Turnstile-Token`` request header rather than in the body.
``POST /login`` takes an OAuth2 form while its three siblings take JSON, so a body field
would mean two mechanisms and a change to three request schemas; one header covers all
four and changes none of them.

The guard decides nothing itself. It reads the header and hands it to whichever verifier
the container supplies, so whether the check runs at all stays a question about
configuration (:func:`api.dependencies.get_turnstile_verifier`) rather than something
each route has to remember to ask. The refusal travels as
:class:`~api.exceptions.TurnstileVerificationError` and the centralized handler turns it
into one 403, identical for every reason the check can refuse.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Header, Request

from api.dependencies import get_turnstile_verifier
from api.services.turnstile_service import TurnstileVerifier
from api.utils.client_ip import get_client_ip

TURNSTILE_HEADER = "X-Turnstile-Token"


def require_human(action: str) -> Callable[..., Awaitable[None]]:
    """Build a route dependency that refuses a request without a valid token.

    :param action: The action this endpoint's widget mints tokens for. A token carrying
        any other action is refused, so one farmed from a different form cannot be
        replayed here.
    :return: A FastAPI dependency that raises ``TurnstileVerificationError`` on refusal.
    """

    async def verify_turnstile_token(
        request: Request,
        verifier: Annotated[TurnstileVerifier, Depends(get_turnstile_verifier)],
        token: Annotated[str | None, Header(alias=TURNSTILE_HEADER)] = None,
    ) -> None:
        """Refuse the request unless its Turnstile token checks out.

        :param request: Incoming request, read for the caller's address.
        :param verifier: The verifier this deployment is configured with.
        :param token: Raw header value; ``None`` on a request that sent none.
        :raises TurnstileVerificationError: If the check refuses the request.
        """
        await verifier.verify(token, action=action, client_ip=get_client_ip(request))

    return verify_turnstile_token
