"""The application's route table, read from the real app, for the structural guards.

Shared by ``test_route_access_levels.py``, ``schemas/test_route_bodies_forbid_extra.py``
and the anonymous-request test in the integration tier: the route walk, and the one
decision they share, the list of routes a caller may reach without signing in.
"""

import os
import tempfile
from collections.abc import Iterable, Iterator
from functools import lru_cache
from unittest import mock

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from api.auth.dependencies import (
    get_current_token_payload,
    get_current_user,
    get_current_user_fresh,
)
from api.dependencies import RequireProjectAccess, require_project_admin, require_project_member

# Routes that answer without an access token, each with the reason that is acceptable.
# Adding a line is a decision, not a formality: the route must hold nothing a stranger
# may not see.
PUBLIC_ROUTES: dict[str, str] = {
    "GET /api/v1/health": "Liveness probe: a fixed status, no data.",
    "POST /api/v1/auth/register": "Creates an account; guarded by the bot check and limits.",
    "POST /api/v1/auth/login": "Trades credentials for a token; guarded by the login throttle.",
    "POST /api/v1/auth/verify-email": "The single-use token mailed to the address is the credential.",
    "POST /api/v1/auth/resend-verification": "Answers the same for any address; throttled.",
    "POST /api/v1/auth/refresh": (
        "Authenticated by its own credential, the refresh token (cookie, else body), which "
        "the handler decodes and rotates; 401 without a valid one. The access token has "
        "expired by the time it is called, so it takes none."
    ),
    "POST /api/v1/auth/forgot-password": "Answers 202 for any address; guarded and throttled.",
    "POST /api/v1/auth/reset-password": "The single-use token mailed to the address is the credential.",
    "GET /api/v1/users/{user_id}/photo": (
        "An <img> tag cannot send a header and members render each other's avatars; serves "
        "only the avatar bytes and 404s without one."
    ),
}

# The ``assistant`` settings the build needs: the router is mounted only when the flag is on.
_BUILD_ENV = {
    "APP_ENV": "dev",
    "SECRET_KEY": "a-sufficiently-strong-secret-value",
    "ASSISTANT_ENABLED": "true",
}


def iter_api_routes(routes: Iterable[object]) -> Iterator[APIRoute]:
    """Walk a route list and yield every ``APIRoute``, descending into sub-routers.

    FastAPI wraps an included router in a container that keeps the real router under
    ``original_router``; both shapes are handled so the walk does not depend on that.

    :param routes: Routes or route containers to walk.
    :return: Iterator over the concrete API routes found.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
            continue
        nested = getattr(route, "routes", None)
        if nested is None:
            nested = getattr(getattr(route, "original_router", None), "routes", None)
        if nested is not None:
            yield from iter_api_routes(nested)


def route_key(route: APIRoute) -> str:
    """Render a route as the ``METHOD /path`` key the pinned tables use.

    :param route: The route to render.
    :return: Its stable identifier.
    """
    return f"{','.join(sorted(route.methods))} {route.path}"


def iter_dependants(dependant: Dependant) -> Iterator[Dependant]:
    """Yield every dependency below a route, at any depth.

    :param dependant: The route's resolved dependency tree.
    :return: Iterator over the sub-dependencies, the route's own entry excluded.
    """
    for sub in dependant.dependencies:
        yield sub
        yield from iter_dependants(sub)


def declares_authentication(route: APIRoute) -> bool:
    """Report whether a dependency in the route's tree refuses an anonymous caller.

    ``RequireProjectAccess`` is not listed because it takes ``CurrentUser``, so its
    routes already hold ``get_current_user``; ``_get_access_token`` only reads the token.
    The assistant chat calls ``get_current_user`` as a function from
    ``get_assistant_user``, so that wrapper is listed instead. It is imported here so
    importing this module does not load the assistant package.

    :param route: The route to inspect.
    :return: True when an authentication dependency sits anywhere in its tree.
    """
    from api.assistant.deps import get_assistant_user

    known = (
        get_current_user,
        get_current_user_fresh,
        get_current_token_payload,
        get_assistant_user,
    )
    return any(sub.call in known for sub in iter_dependants(route.dependant))


def project_access_levels(route: APIRoute) -> set[str]:
    """Collect the project access levels a route requires.

    The shared member and admin instances are told apart by identity, so no private
    attribute is read.

    :param route: The route to inspect.
    :return: The levels found: ``member``, ``admin``, both, or none.
    :raises AssertionError: If the route carries a ``RequireProjectAccess`` that is
        neither shared instance.
    """
    levels: set[str] = set()
    for sub in iter_dependants(route.dependant):
        if not isinstance(sub.call, RequireProjectAccess):
            continue
        if sub.call is require_project_member:
            levels.add("member")
        elif sub.call is require_project_admin:
            levels.add("admin")
        else:
            raise AssertionError(f"{route_key(route)} uses an unnamed RequireProjectAccess")
    return levels


@lru_cache(maxsize=1)
def api_routes() -> tuple[APIRoute, ...]:
    """Build the real application once, assistant router included, and list its routes.

    The flag is raised for the build only, in a scratch working directory so a
    developer's ``.env`` is not read, and the settings cache is cleared on both sides.
    No lifespan starts, so no database is opened and nothing reaches the network.

    :return: Every API route the application exposes with the assistant switched on.
    """
    from api.config import get_settings
    from api.main import create_app

    with tempfile.TemporaryDirectory() as scratch:
        cwd = os.getcwd()
        os.chdir(scratch)
        try:
            with mock.patch.dict(os.environ, _BUILD_ENV):
                os.environ.pop("RAILWAY_ENVIRONMENT_NAME", None)
                get_settings.cache_clear()
                try:
                    return tuple(iter_api_routes(create_app().routes))
                finally:
                    get_settings.cache_clear()
        finally:
            os.chdir(cwd)
