"""Structural guard: who may call each route, and at which project level.

Two properties are pinned against the real application, built with the assistant router
mounted (``route_table.api_routes``): every route either needs a signed-in caller or is
listed as public with a reason, and every project route demands the access level the
table below records. FastAPI's own documentation routes are not ``APIRoute`` entries;
they are pinned separately and are off in production.
"""

import pytest

from api.dependencies import AccessLevel, require_project_admin, require_project_member
from tests.unit.api.route_table import (
    FRAMEWORK_ROUTES,
    PUBLIC_ROUTES,
    api_routes,
    app_routes,
    declares_authentication,
    project_access_levels,
    route_key,
    unaccounted_routes,
)

# Every route that carries RequireProjectAccess, with the level it demands. An added or
# removed route, or a changed level, fails below until this table is edited.
PROJECT_ACCESS_LEVELS: dict[str, str] = {
    "GET /api/v1/projects/{project_id}": "member",
    "PATCH /api/v1/projects/{project_id}": "admin",
    "DELETE /api/v1/projects/{project_id}": "admin",
    "POST /api/v1/projects/{project_id}/transfer-ownership": "admin",
    "GET /api/v1/projects/{project_id}/members": "member",
    "DELETE /api/v1/projects/{project_id}/members/me": "member",
    "DELETE /api/v1/projects/{project_id}/members/{user_id}": "admin",
    "POST /api/v1/projects/{project_id}/invite": "admin",
    "GET /api/v1/projects/{project_id}/invitations": "admin",
    "DELETE /api/v1/projects/{project_id}/invitations/{invitation_id}": "admin",
    "GET /api/v1/projects/{project_id}/opinions": "member",
    "POST /api/v1/projects/{project_id}/opinions": "member",
    "DELETE /api/v1/projects/{project_id}/opinions": "member",
    "GET /api/v1/projects/{project_id}/result": "member",
    "GET /api/v1/projects/{project_id}/result/export": "member",
}


def _all_keys() -> set[str]:
    """Collect every route of the application.

    :return: The ``METHOD /path`` keys.
    """
    return {route_key(route) for route in api_routes()}


def _unauthenticated_keys() -> set[str]:
    """Collect the routes with no authentication dependency in their tree.

    :return: The ``METHOD /path`` keys an anonymous caller can reach.
    """
    return {route_key(route) for route in api_routes() if not declares_authentication(route)}


def _live_levels() -> dict[str, str]:
    """Read the level each project route demands from the application.

    :return: ``METHOD /path`` mapped to ``member`` or ``admin``.
    :raises AssertionError: If a route carries both levels, which no pinned entry can name.
    """
    found: dict[str, str] = {}
    for route in api_routes():
        levels = project_access_levels(route)
        assert len(levels) <= 1, f"{route_key(route)} requires more than one level: {levels}"
        if levels:
            found[route_key(route)] = next(iter(levels))
    return found


class TestEveryRouteRequiresAuthenticationOrIsPublic:
    """A route answers anonymous callers only when it is pinned as public with a reason."""

    @pytest.mark.parametrize(
        "key",
        [
            "GET /api/v1/auth/me",
            "PUT /api/v1/users/me",
            "POST /api/v1/auth/logout",
            "GET /api/v1/projects/{project_id}",
            "POST /api/v1/assistant/chat/stream",
        ],
    )
    def test_each_authentication_dependency_is_recognised(self, key):
        """
        GIVEN a route for each way of authenticating: the cached user, the fresh user,
            the token payload of logout, a project check, and the assistant's wrapper
        WHEN the routes without an authentication dependency are collected
        THEN the route exists and is not among them, so detection is not vacuous
        """
        # THEN
        assert key in _all_keys()
        assert key not in _unauthenticated_keys()

    def test_the_walk_covers_routes_with_and_without_a_path_parameter(self):
        """
        GIVEN the application built with the assistant router mounted
        WHEN its routes are collected
        THEN parameterless, parameterised and assistant routes are present, and both
            public and authenticated routes exist
        """
        # THEN
        keys = _all_keys()
        assert {
            "GET /api/v1/health",
            "POST /api/v1/projects",
            "POST /api/v1/assistant/chat",
        } <= keys
        assert "DELETE /api/v1/projects/{project_id}" in keys
        assert _unauthenticated_keys()
        assert keys - _unauthenticated_keys()

    def test_every_route_is_authenticated_or_pinned_public(self):
        """
        GIVEN every route of the application
        WHEN the ones without an authentication dependency are collected
        THEN each is listed in PUBLIC_ROUTES with its reason

        Do not paste a route into the list to silence this. Add the user dependency, or
        write down what stands in for it.
        """
        # WHEN
        unaccounted = sorted(_unauthenticated_keys() - PUBLIC_ROUTES.keys())

        # THEN
        assert not unaccounted, f"anonymous callers can reach, with no reason: {unaccounted}"

    def test_public_entries_name_live_unauthenticated_routes(self):
        """
        GIVEN the public routes pinned in PUBLIC_ROUTES
        WHEN they are matched against the application's routes
        THEN each names a route that exists and really has no authentication dependency
        """
        # WHEN
        stale = sorted(PUBLIC_ROUTES.keys() - _unauthenticated_keys())

        # THEN
        assert not stale, f"entries naming routes that are gone or now authenticated: {stale}"


class TestProjectRoutesDemandThePinnedLevel:
    """Each project route demands the level the table pins, and no route drifts silently."""

    def test_the_pinned_routes_are_exactly_the_routes_with_a_project_check(self):
        """
        GIVEN the routes that carry a project access check
        WHEN their keys are compared with PROJECT_ACCESS_LEVELS
        THEN the two sets are equal, so an added or removed route fails here
        """
        # WHEN
        live, pinned = set(_live_levels()), set(PROJECT_ACCESS_LEVELS)

        # THEN
        assert live == pinned, (
            f"in the app, not pinned: {sorted(live - pinned)}; "
            f"pinned, not in the app: {sorted(pinned - live)}"
        )

    def test_both_levels_are_in_use(self):
        """
        GIVEN the live project routes
        WHEN their levels are collected
        THEN member and admin both appear, so the check cannot pass by reading one value
        """
        # THEN
        assert set(_live_levels().values()) == {"member", "admin"}

    @pytest.mark.parametrize(("key", "level"), sorted(PROJECT_ACCESS_LEVELS.items()))
    def test_route_demands_its_pinned_level(self, key, level):
        """
        GIVEN a project route and the level pinned for it
        WHEN the level is read from the route's dependency tree
        THEN it is the pinned one, so an admin action cannot drop to member access
        """
        # THEN
        assert _live_levels().get(key) == level


class TestSharedInstancesStoreTheirLevel:
    """The guard names a route's level by which shared instance it carries, so pin the instances."""

    @pytest.mark.parametrize(
        ("instance", "level"),
        [(require_project_member, AccessLevel.MEMBER), (require_project_admin, AccessLevel.ADMIN)],
        ids=["member", "admin"],
    )
    def test_shared_instance_stores_its_level(self, instance, level):
        """
        GIVEN the shared member and admin access instances
        WHEN the level each one enforces is read
        THEN the member instance stores member and the admin instance stores admin, so
            the level table above cannot be satisfied by a mislabelled instance
        """
        # THEN
        assert instance._access_level is level


class TestEveryRegisteredRouteIsSeen:
    """A route of any kind other than ``APIRoute`` would be invisible to the guards above."""

    def test_every_route_is_an_api_route_or_a_framework_docs_route(self):
        """
        GIVEN the routes the application registers, included routers searched through
        WHEN those that are not an APIRoute are collected
        THEN they are exactly the docs and schema routes FastAPI adds itself

        A plain ``Route``, a ``Mount`` or a WebSocket route would carry no dependency
        tree for the authentication and level guards to read.
        """
        # WHEN
        others = unaccounted_routes(app_routes())

        # THEN
        assert set(others) == FRAMEWORK_ROUTES, sorted(set(others) ^ FRAMEWORK_ROUTES)
