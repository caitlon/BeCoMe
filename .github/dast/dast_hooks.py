"""Schemathesis hooks for the DAST run.

FastAPI documents the session cookies (``__Host-access_token`` and ``__Secure-refresh_token``)
as optional cookie parameters, so Schemathesis fills them with random strings. The API reads
the cookie before the Authorization header, so a generated cookie replaces the valid Bearer
token and the call is refused with 401 before it reaches the route. Dropping the generated
cookies keeps the Bearer identity in force. The cookie transport is therefore not fuzzed.

Load it with ``SCHEMATHESIS_HOOKS=dast_hooks`` and ``PYTHONPATH=.github/dast``.
"""

from typing import Any

import schemathesis


@schemathesis.hook
def before_call(ctx: Any, case: Any, kwargs: dict[str, Any]) -> None:
    """Remove the generated session cookies from the request.

    :param ctx: Hook context supplied by Schemathesis
    :param case: The generated test case
    :param kwargs: Keyword arguments of the outgoing request
    """
    if case.cookies:
        case.cookies = {}
    kwargs.pop("cookies", None)
