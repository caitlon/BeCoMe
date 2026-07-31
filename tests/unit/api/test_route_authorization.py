"""Structural guard: every project-scoped route declares an access check.

Migration ``c83186b79ad7`` deliberately dropped row-level security, so tenant
isolation rests entirely on ``RequireProjectAccess`` being wired into each route that
takes a ``project_id``. Nothing in the framework enforces that. A route added without
the dependency would read and write another tenant's data with no second line of
defence, and it would look perfectly ordinary in review -- hence this test.
"""

from collections.abc import Iterable, Iterator

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from api.dependencies import RequireProjectAccess
from api.main import create_app

PROJECT_ID_PARAM = "{project_id}"


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


def _project_scoped_routes() -> list[APIRoute]:
    """Collect every route whose path carries a ``project_id`` segment.

    :return: The project-scoped API routes of the application.
    """
    return [
        route for route in _iter_api_routes(create_app().routes) if PROJECT_ID_PARAM in route.path
    ]


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
            f"{sorted(route.methods)} {route.path}"
            for route in _project_scoped_routes()
            if not _declares_project_access(route.dependant)
        ]

        # THEN
        assert not unguarded, f"project-scoped routes without an access check: {unguarded}"
