"""Structural guard: every route that names someone else's object declares a check.

Migration ``c83186b79ad7`` deliberately dropped row-level security, so tenant
isolation rests entirely on the application layer. Nothing in the framework enforces
that. A route added without an access check would read and write another tenant's data
with no second line of defence, and it would look perfectly ordinary in review -- hence
this test.

Two guards live here. The first requires ``RequireProjectAccess`` on every route that
takes a ``project_id``. The second is wider and catches what the first cannot: a route
naming any other identifier -- an invitation, a user -- is equally able to cross tenants,
and such a route carries no ``project_id`` for the first guard to notice. Those are
enumerated below with the check that stands in for the dependency, so a new one fails
until somebody makes that argument explicitly.
"""

from collections.abc import Iterable, Iterator
from functools import lru_cache

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from api.dependencies import RequireProjectAccess
from api.main import create_app

PROJECT_ID_PARAM = "{project_id}"

# Routes that take an identifier but deliberately do not use RequireProjectAccess. Each
# entry names what enforces access instead; the behaviour itself is covered by the
# integration tests named alongside it. Adding a line here is a decision, not a
# formality: it says this route cannot be reached for somebody else's data.
UNGUARDED_BY_DESIGN: dict[str, str] = {
    "GET /api/v1/users/{user_id}/photo": (
        "Public by design -- an <img> tag cannot send an Authorization header, and every "
        "project member renders every other member's avatar. Serves nothing but the "
        "avatar bytes, and answers 404 for a user without one."
    ),
    "POST /api/v1/invitations/{invitation_id}/accept": (
        "InvitationService.accept_invitation refuses unless invitation.invitee_id is the "
        "caller, with the same 404 an unknown id gets "
        "(test_accept_invitation_not_for_user). There is no project membership to check "
        "yet -- accepting is what creates it."
    ),
    "POST /api/v1/invitations/{invitation_id}/decline": (
        "InvitationService.decline_invitation applies the same invitee_id check "
        "(test_decline_invitation_not_for_user)."
    ),
}


def _declares_project_access(dependant: Dependant) -> bool:
    """Report whether a route's dependency tree contains a project access check.

    :param dependant: The route's resolved dependency tree.
    :return: True when ``RequireProjectAccess`` appears anywhere in the tree.
    """
    if isinstance(dependant.call, RequireProjectAccess):
        return True
    return any(_declares_project_access(sub) for sub in dependant.dependencies)


def _iter_api_routes(routes: Iterable[object]) -> Iterator[APIRoute]:
    """Walk a route list and yield every ``APIRoute``, descending into sub-routers.

    ``app.routes`` does not necessarily hold the endpoints directly: FastAPI wraps an
    included router in a container that keeps the real router under
    ``original_router``. Both shapes are handled so the walk does not depend on that
    internal layout.

    :param routes: Routes or route containers to walk.
    :return: Iterator over the concrete API routes found.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
            continue
        nested = getattr(route, "routes", None)
        if nested is None:
            inner_router = getattr(route, "original_router", None)
            nested = getattr(inner_router, "routes", None)
        if nested is not None:
            yield from _iter_api_routes(nested)


@lru_cache(maxsize=1)
def _api_routes() -> tuple[APIRoute, ...]:
    """Build the application once and return its concrete routes.

    Cached because every guard below walks the same table, and ``create_app`` is not
    free: it reconfigures logging and initialises Sentry on each call.

    :return: Every API route the application exposes.
    """
    return tuple(_iter_api_routes(create_app().routes))


def _project_scoped_routes() -> list[APIRoute]:
    """Collect every route whose path carries a ``project_id`` segment.

    :return: The project-scoped API routes of the application.
    """
    return [route for route in _api_routes() if PROJECT_ID_PARAM in route.path]


def _route_key(route: APIRoute) -> str:
    """Render a route as the ``METHOD /path`` key used by :data:`UNGUARDED_BY_DESIGN`.

    :param route: The route to render.
    :return: Its stable identifier.
    """
    return f"{','.join(sorted(route.methods))} {route.path}"


def _parameterised_routes() -> list[APIRoute]:
    """Collect every route whose path names an identifier.

    A path parameter is what lets a caller point at a specific record, so it is the
    signal that a route could reach data belonging to somebody else.

    :return: The API routes taking at least one path parameter.
    """
    return [route for route in _api_routes() if "{" in route.path]


class TestProjectScopedRoutesAreGuarded:
    """Tenant isolation is enforced on the routes that can cross tenants."""

    def test_there_are_project_scoped_routes_to_check(self):
        """
        GIVEN the application factory
        WHEN project-scoped routes are collected
        THEN some are found, so the guard below is not vacuously true
        """
        # WHEN
        routes = _project_scoped_routes()

        # THEN
        assert routes, "no {project_id} routes found -- the guard below would pass vacuously"

    def test_every_project_scoped_route_requires_project_access(self):
        """
        GIVEN every route that takes a project_id
        WHEN its dependency tree is inspected
        THEN RequireProjectAccess is part of it

        Add the ProjectMember or ProjectAdmin dependency to a failing route rather
        than relaxing this test: without it, any authenticated caller reaches another
        tenant's project.
        """
        # WHEN
        unguarded = [
            _route_key(route)
            for route in _project_scoped_routes()
            if not _declares_project_access(route.dependant)
        ]

        # THEN
        assert not unguarded, f"project-scoped routes without an access check: {unguarded}"


class TestRoutesNamingOtherObjectsAreAccountedFor:
    """Every route taking an identifier is either guarded or argued for by name."""

    def test_there_are_parameterised_routes_to_check(self):
        """
        GIVEN the application factory
        WHEN routes taking a path parameter are collected
        THEN some are found, so the guard below is not vacuously true

        Without this, a route walk that silently returned nothing -- a FastAPI internal
        the walker no longer recognises, say -- would read as "every route is fine".
        """
        # WHEN
        routes = _parameterised_routes()

        # THEN
        assert routes, "no parameterised routes found -- the guard below would pass vacuously"

    def test_the_exemption_list_has_no_stale_entries(self):
        """
        GIVEN the exemptions declared above
        WHEN they are matched against the application's routes
        THEN each one still names a real, still-unguarded route

        A stale entry is worse than no entry: it reads as a reviewed decision while
        covering a route that has since been renamed, removed, or guarded properly.
        """
        # WHEN
        live = {
            _route_key(route)
            for route in _parameterised_routes()
            if not _declares_project_access(route.dependant)
        }

        # THEN
        stale = sorted(UNGUARDED_BY_DESIGN.keys() - live)
        assert not stale, f"exemptions naming routes that no longer need them: {stale}"

    def test_no_route_names_an_object_without_an_accounted_check(self):
        """
        GIVEN every route that takes a path parameter
        WHEN the ones without RequireProjectAccess are collected
        THEN each is listed in UNGUARDED_BY_DESIGN with its reason

        A path parameter is how a caller points at one specific record, so a route with
        one can serve somebody else's. With row-level security off there is no database
        backstop: if the route does not check, nothing does.

        Do not silence a failure by pasting the route into the list. Either wire in
        ProjectMember/ProjectAdmin, or write down what enforces access instead and the
        test that proves it -- the way the existing entries do.
        """
        # WHEN
        unaccounted = sorted(
            _route_key(route)
            for route in _parameterised_routes()
            if not _declares_project_access(route.dependant)
            and _route_key(route) not in UNGUARDED_BY_DESIGN
        )

        # THEN
        assert not unaccounted, (
            "routes naming an object with neither a project access check nor a recorded "
            f"reason: {unaccounted}"
        )
