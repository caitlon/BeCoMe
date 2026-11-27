"""Every route outside the public list refuses a caller who sends no credential.

The public list is the one the structural guard pins (``tests/unit/api/route_table.py``).
Here the routes are called for real: no ``Authorization`` header and no cookie, against
rows that exist, so a route that served an anonymous caller would read or change data
that is really there. Every refusal must be the authentication layer's own 401, and the
database must be as it was.
"""

from uuid import uuid4

import pytest

from api.config import get_settings
from api.db.models import ExpertOpinion, Invitation, ProjectMember, User
from tests.integration.api.conftest import app_session, create_test_app
from tests.integration.api.state_snapshot import snapshot
from tests.shared.helpers import add_project
from tests.unit.api.route_table import PUBLIC_ROUTES, iter_api_routes


def _non_public(app) -> list[tuple[str, str]]:
    """List ``(method, path template)`` for the routes of an app that are not public.

    :param app: The application to read.
    :return: The routes whose ``METHOD /path`` key is not in ``PUBLIC_ROUTES``.
    """
    return [
        (method, route.path)
        for route in iter_api_routes(app.routes)
        for method in sorted(route.methods)
        if f"{method} {route.path}" not in PUBLIC_ROUTES
    ]


def _collect_from_the_test_app() -> list[tuple[str, str]]:
    """Read the non-public routes from a throwaway build of the integration app.

    Built at collection time to parametrise the test below; the settings cache is cleared
    afterwards so no test inherits what collection read.

    :return: The non-public ``(method, path template)`` pairs.
    """
    try:
        return _non_public(create_test_app())
    finally:
        get_settings.cache_clear()


NON_PUBLIC_ROUTES = _collect_from_the_test_app()


def _seed(client) -> dict[str, str]:
    """Insert a project with an admin, an expert, an opinion and an invitation.

    The rows are real, so a route that skipped authentication would find its target.

    :param client: Test client whose app writes through the session ``app_session`` opens.
    :return: The ids a path template may name, keyed by the parameter's name.
    """
    with app_session(client) as session:
        people = [
            User(email=f"{name}@example.com", hashed_password="x", first_name=name, last_name="X")
            for name in ("admin", "expert", "invitee")
        ]
        session.add_all(people)
        session.flush()
        admin, expert, invitee = people
        project = add_project(session, admin, name="Anonymous Target")
        session.add(ProjectMember(project_id=project.id, user_id=expert.id))
        session.add(
            ExpertOpinion(
                project_id=project.id,
                user_id=expert.id,
                position="Analyst",
                lower_bound=10.0,
                peak=20.0,
                upper_bound=30.0,
            )
        )
        invitation = Invitation(project_id=project.id, invitee_id=invitee.id, inviter_id=admin.id)
        session.add(invitation)
        session.commit()
        return {
            "project_id": str(project.id),
            "user_id": str(expert.id),
            "invitation_id": str(invitation.id),
        }


def _assert_refused_and_untouched(client, ids: dict[str, str], method: str, path: str) -> None:
    """Call a route with no credential and check it was refused and wrote nothing.

    Path parameters take the seeded id of that name, else a random UUID.

    :param client: Test client with the integration app and the seeded rows.
    :param ids: The seeded ids a path template may name.
    :param method: HTTP method of the route.
    :param path: Route path template.
    """
    # GIVEN
    url = path
    for name in [part.strip("{}") for part in path.split("/") if part.startswith("{")]:
        url = url.replace("{" + name + "}", ids.get(name, str(uuid4())))
    with app_session(client) as session:
        before = snapshot(session)

    # WHEN
    response = client.request(method, url)

    # THEN: the authentication layer answered, not CSRF and not body validation
    assert response.status_code == 401, f"{method} {path} answered {response.status_code}"
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"
    with app_session(client) as session:
        assert snapshot(session) == before


class TestAnonymousCallersAreRefused:
    """No route outside the public list answers a request with no credential."""

    def test_the_route_list_is_not_empty(self):
        """
        GIVEN the routes of the integration app outside the public list
        WHEN the list is read
        THEN it holds every method and known routes of each kind, so the sweep is not vacuous
        """
        # WHEN
        routes = {f"{method} {path}" for method, path in NON_PUBLIC_ROUTES}

        # THEN
        assert {"GET", "POST", "PUT", "PATCH", "DELETE"} <= {key.split()[0] for key in routes}
        assert {
            "POST /api/v1/projects",
            "DELETE /api/v1/projects/{project_id}/members/{user_id}",
            "POST /api/v1/invitations/{invitation_id}/accept",
            "POST /api/v1/auth/logout",
        } <= routes
        assert len(routes) > len(PUBLIC_ROUTES)
        assert not routes & PUBLIC_ROUTES.keys()

    @pytest.mark.parametrize(("method", "path"), NON_PUBLIC_ROUTES, ids=lambda v: v)
    def test_anonymous_request_is_refused(self, client, method, path):
        """
        GIVEN a route outside the public list and a database holding the rows it names
        WHEN it is called with no Authorization header and no cookie
        THEN it answers 401 "Not authenticated" and no row changes
        """
        _assert_refused_and_untouched(client, _seed(client), method, path)

    def test_assistant_routes_are_refused_too(self, assistant_settings, client):
        """
        GIVEN the app built with the assistant router mounted
        WHEN each assistant route is called with no credential
        THEN each answers 401 and nothing changes
        """
        # GIVEN
        routes = [r for r in _non_public(client.app) if r[1].startswith("/api/v1/assistant")]
        assert routes, "the assistant router was not mounted, so nothing was checked"
        ids = _seed(client)

        # THEN
        for method, path in routes:
            _assert_refused_and_untouched(client, ids, method, path)

    def test_refresh_without_its_token_is_refused(self, client):
        """
        GIVEN the refresh route, public because its credential is the refresh token
        WHEN it is called with no refresh token in a cookie or in the body
        THEN it answers 401
        """
        # THEN
        assert client.post("/api/v1/auth/refresh").status_code == 401
