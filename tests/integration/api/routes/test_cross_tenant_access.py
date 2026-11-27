"""Tenant isolation: one tenant's projects, opinions and invitations stay out of another's.

Two users who each own a project are separate tenants. Owning project P2 must not grant
anything on project P1, a deletion of one account must not reach the other's data, and the
personal-data export and the invitation list show only what belongs to the caller.
"""

import json
import re
from uuid import uuid4

import pytest
from fastapi import status

from tests.integration.api.conftest import (
    auth_header,
    create_project,
    create_test_app,
    delete_account,
    submit_opinion,
)
from tests.integration.api.tenant_helpers import (
    ALL_ROUTES,
    Account,
    Team,
    capture_state,
    invite,
    make_team,
    register_account,
    send_route,
)


@pytest.fixture
def team(client) -> Team:
    """Tenant one: a project with an admin and two experts who have each given an opinion."""
    return make_team(client, "alpha", "AlphaProject")


@pytest.fixture
def rival(client) -> Account:
    """Tenant two: a user who is not a member of tenant one's project."""
    return register_account(client, "beta-owner@example.com")


@pytest.fixture
def rival_project(client, rival) -> dict:
    """The project that tenant two owns."""
    return create_project(client, rival.token, "BetaProject")


class TestAnotherTenantsProject:
    """A user who owns a project of their own still gets 404 on someone else's."""

    @pytest.mark.parametrize("route", sorted(ALL_ROUTES))
    def test_owning_a_project_grants_nothing_on_another(
        self, client, team, rival, rival_project, route
    ):
        """Every project-scoped route answers 404 and leaves both projects as they were."""
        # GIVEN two tenants, each the admin of their own project
        invitee = register_account(client, "alpha-invitee@example.com")
        register_account(client, "alpha-third@example.com")
        pending = invite(client, team.admin, team.project_id, "alpha-third@example.com")
        before_one = capture_state(client, team.admin, team.project_id)
        before_two = capture_state(client, rival, rival_project["id"])

        # WHEN tenant two sends tenant one's project id to the route
        response = send_route(
            client,
            route,
            rival.token,
            team.project_id,
            target_id=team.admin.user_id,
            actor_id=rival.user_id,
            invitee_email=invitee.email,
            invitation_id=pending["id"],
        )

        # THEN the dependency reports the project missing, and neither project changed
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"detail": "Project not found"}
        assert capture_state(client, team.admin, team.project_id) == before_one
        assert capture_state(client, rival, rival_project["id"]) == before_two
        assert rival.user_id not in before_one["roles"]

    def test_the_other_tenant_still_owns_their_own_project(
        self, client, team, rival, rival_project
    ):
        """The refusal is about project one only: tenant two keeps full rights on their own."""
        # GIVEN tenant two was just refused on tenant one's project
        refused = send_route(client, "update_project", rival.token, team.project_id)
        assert refused.status_code == status.HTTP_404_NOT_FOUND

        # WHEN tenant two edits their own project
        response = client.patch(
            f"/api/v1/projects/{rival_project['id']}",
            json={"name": "BetaRenamed"},
            headers=auth_header(rival.token),
        )

        # THEN it works, and tenant one's project kept its name
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "BetaRenamed"
        assert capture_state(client, team.admin, team.project_id)["project"]["name"] == (
            "AlphaProject"
        )


class TestRouteTable:
    """The route table the tenant tests iterate over covers every project-scoped route."""

    def test_table_matches_the_routes_of_the_app(self):
        """Each route with ``{project_id}`` in its path is in the table, and nothing else is."""

        def shape(path: str) -> str:
            """Reduce a path to its static parts, so ``{user_id}`` and ``{target_id}`` match."""
            return re.sub(r"\{(?!project_id\})[^}]+\}", "{}", path.split("?")[0])

        # GIVEN the (method, path) pairs of the app the tests run against, read from its
        # OpenAPI schema because included routers are not listed flat in ``app.routes``
        paths = create_test_app().openapi()["paths"]
        in_app = {
            (method.upper(), shape(path))
            for path, operations in paths.items()
            if "{project_id}" in path
            for method in operations
        }

        # WHEN they are compared with the table
        in_table = {(method, shape(path)) for method, path, _ in ALL_ROUTES.values()}

        # THEN the two sets are equal
        assert in_table == in_app


class TestMissingAndForeignProjectLookAlike:
    """A project the caller cannot see answers exactly like one that does not exist."""

    @pytest.mark.parametrize(
        "route",
        ["get_project", "update_project", "list_members", "list_opinions", "get_result", "invite"],
    )
    def test_not_a_member_and_not_found_have_the_same_body(
        self, client, team, rival, rival_project, route
    ):
        """The 404 for someone else's project is byte-for-byte the 404 for a random id."""
        # GIVEN a project the caller is no member of and an id that is no project at all
        invitee = register_account(client, "alpha-invitee@example.com")
        context = {"invitee_email": invitee.email, "actor_id": rival.user_id}

        # WHEN the same request is sent for each
        foreign = send_route(client, route, rival.token, team.project_id, **context)
        missing = send_route(client, route, rival.token, str(uuid4()), **context)

        # THEN both are 404 with identical bodies
        assert foreign.status_code == status.HTTP_404_NOT_FOUND
        assert missing.status_code == status.HTTP_404_NOT_FOUND
        assert foreign.content == missing.content


class TestAccountDeletionStaysInsideTheCallersTenant:
    """Account deletion with a disposition for a project the caller does not own."""

    @pytest.mark.parametrize(
        ("owns_a_project", "dispositions"),
        [
            pytest.param(False, ["foreign"], id="owns-nothing-foreign-delete"),
            pytest.param(False, ["foreign-transfer"], id="owns-nothing-foreign-transfer"),
            pytest.param(True, ["own", "foreign"], id="own-plus-foreign-delete"),
            pytest.param(True, ["foreign"], id="own-project-left-out"),
        ],
    )
    def test_foreign_disposition_blocks_the_deletion(
        self, client, team, rival, owns_a_project, dispositions
    ):
        """A disposition naming another tenant's project is refused and nothing is deleted."""
        # GIVEN a caller (who may own a project) and tenant one's project with its data
        own = create_project(client, rival.token, "BetaProject") if owns_a_project else None
        before_one = capture_state(client, team.admin, team.project_id)
        before_two = capture_state(client, rival, own["id"]) if own else None
        named = {
            "own": {"project_id": own["id"] if own else "", "action": "delete"},
            "foreign": {"project_id": team.project_id, "action": "delete"},
            "foreign-transfer": {
                "project_id": team.project_id,
                "action": "transfer",
                "new_admin_id": team.expert.user_id,
            },
        }

        # WHEN the caller asks to delete their account with those dispositions
        response = delete_account(client, rival.token, [named[name] for name in dispositions])

        # THEN it is refused, the caller still exists and tenant one is untouched
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["code"] == "account_has_owned_projects"
        profile = client.get("/api/v1/users/me", headers=auth_header(rival.token))
        assert profile.status_code == status.HTTP_200_OK
        assert profile.json()["id"] == rival.user_id
        assert capture_state(client, team.admin, team.project_id) == before_one
        if own:
            assert capture_state(client, rival, own["id"]) == before_two


class TestPersonalDataStaysPrivate:
    """The data export and the invitation list show the caller's own rows only."""

    def test_export_holds_nothing_of_another_tenant(self, client, team, rival, rival_project):
        """One tenant's export contains none of the other tenant's ids, names or addresses."""
        # GIVEN tenant one has members, opinions and a pending invitation
        third = register_account(client, "alpha-third@example.com")
        invited = client.post(
            f"/api/v1/projects/{team.project_id}/invite",
            json={"email": third.email},
            headers=auth_header(team.admin.token),
        )
        assert invited.status_code == status.HTTP_201_CREATED
        opinions = client.get(
            f"/api/v1/projects/{team.project_id}/opinions", headers=auth_header(team.admin.token)
        ).json()
        assert len(opinions) == 2
        submit_opinion(client, rival.token, rival_project["id"], position="betapos")
        own_opinions = client.get(
            f"/api/v1/projects/{rival_project['id']}/opinions", headers=auth_header(rival.token)
        ).json()
        assert len(own_opinions) == 1

        # WHEN tenant two exports their personal data
        response = client.get("/api/v1/users/me/export", headers=auth_header(rival.token))

        # THEN their own rows are present
        assert response.status_code == status.HTTP_200_OK
        text = json.dumps(response.json())
        for own in (rival.email, rival_project["id"], "BetaProject", own_opinions[0]["id"]):
            assert own in text

        # AND nothing of tenant one is
        foreign = [
            team.project_id,
            "AlphaProject",
            team.admin.email,
            team.expert.email,
            team.other_expert.email,
            third.email,
            invited.json()["id"],
            team.admin.user_id,
            team.expert.user_id,
            *(opinion["id"] for opinion in opinions),
        ]
        for value in foreign:
            assert value not in text

    def test_invitations_list_only_the_callers_own(self, client, team, rival):
        """A user sees invitations addressed to them, never those addressed to someone else."""
        # GIVEN tenant one invites two different users into two different projects
        second_project = create_project(client, team.admin.token, "AlphaSecond")
        third = register_account(client, "alpha-third@example.com")
        to_rival = client.post(
            f"/api/v1/projects/{team.project_id}/invite",
            json={"email": rival.email},
            headers=auth_header(team.admin.token),
        ).json()
        to_third = client.post(
            f"/api/v1/projects/{second_project['id']}/invite",
            json={"email": third.email},
            headers=auth_header(team.admin.token),
        ).json()

        # WHEN each of them lists their invitations
        mine = client.get("/api/v1/invitations", headers=auth_header(rival.token))
        theirs = client.get("/api/v1/invitations", headers=auth_header(third.token))

        # THEN each sees exactly their own
        assert [item["id"] for item in mine.json()] == [to_rival["id"]]
        assert [item["id"] for item in theirs.json()] == [to_third["id"]]
        assert to_third["id"] not in mine.text
        assert second_project["id"] not in mine.text
        assert to_rival["id"] not in theirs.text
        assert team.project_id not in theirs.text

    def test_a_user_without_invitations_sees_none(self, client, team, rival):
        """Pending invitations of other users never show up in an empty list."""
        # GIVEN pending invitations for others, and a user nobody has invited
        third = register_account(client, "alpha-third@example.com")
        invite(client, team.admin, team.project_id, third.email)

        # WHEN the uninvited user lists their invitations
        response = client.get("/api/v1/invitations", headers=auth_header(rival.token))

        # THEN the list is empty
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_another_users_invitation_cannot_be_answered(self, client, team, rival):
        """Accepting someone else's invitation fails and does not make the caller a member."""
        # GIVEN an invitation addressed to a third user
        third = register_account(client, "alpha-third@example.com")
        invitation = client.post(
            f"/api/v1/projects/{team.project_id}/invite",
            json={"email": third.email},
            headers=auth_header(team.admin.token),
        ).json()
        before = capture_state(client, team.admin, team.project_id)

        # WHEN another user accepts it
        response = client.post(
            f"/api/v1/invitations/{invitation['id']}/accept", headers=auth_header(rival.token)
        )

        # THEN it is refused and the invitation row and the roles are unchanged
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert capture_state(client, team.admin, team.project_id) == before
