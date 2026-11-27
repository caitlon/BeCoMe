"""A project's role levels: members cannot use admin routes, and ownership moves cleanly.

Authorization lives in ``RequireProjectAccess`` (``ProjectMember`` and ``ProjectAdmin``). A
member without admin rights gets 403; someone with no membership gets 404, the same answer
as for a project that does not exist. Every refusal here also reads the project back and
checks that nothing changed.
"""

import pytest
from fastapi import status

from tests.integration.api.conftest import auth_header, create_project
from tests.integration.api.tenant_helpers import (
    ADMIN_ROUTES,
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
    """A project with its admin and two ordinary members who have each given an opinion."""
    return make_team(client, "alpha", "AlphaProject")


@pytest.fixture
def invitee(client) -> Account:
    """A registered, verified account that belongs to no project."""
    return register_account(client, "alpha-invitee@example.com")


class TestOrdinaryMemberIsRefused:
    """An expert is a member, so admin routes answer 403 and change nothing."""

    def test_member_cannot_update_project(self, client, team):
        """A member's PATCH is refused and the name and description stay as they were."""
        # GIVEN a project and an expert who is a member of it
        before = capture_state(client, team.admin, team.project_id)

        # WHEN the expert tries to rename it
        response = send_route(client, "update_project", team.expert.token, team.project_id)

        # THEN the request is forbidden and the project is untouched
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert capture_state(client, team.admin, team.project_id) == before
        assert before["project"]["name"] == "AlphaProject"

    def test_member_cannot_invite(self, client, team, invitee):
        """A member's invitation is refused for a valid, verified target, so it is the role."""
        # GIVEN a registered, verified account that is not a member
        before = capture_state(client, team.admin, team.project_id)

        # WHEN the expert invites it
        response = send_route(
            client,
            "invite",
            team.expert.token,
            team.project_id,
            invitee_email=invitee.email,
        )

        # THEN the request is forbidden and no invitation row exists for the target
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert capture_state(client, team.admin, team.project_id) == before
        mine = client.get("/api/v1/invitations", headers=auth_header(invitee.token))
        assert mine.json() == []

    def test_member_cannot_delete_project(self, client, team):
        """A member's DELETE is refused and the project survives with all its data."""
        # GIVEN a project with two members who have submitted opinions
        before = capture_state(client, team.admin, team.project_id)

        # WHEN the expert tries to delete the project
        response = send_route(client, "delete_project", team.expert.token, team.project_id)

        # THEN the request is forbidden and the project is still there for its admin
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert capture_state(client, team.admin, team.project_id) == before
        assert team.project_id in before["admin_project_ids"]

    @pytest.mark.parametrize("target", ["other_expert", "admin", "expert"])
    def test_member_cannot_remove_a_member(self, client, team, target):
        """A member cannot remove another expert, the admin or themselves via the admin route."""
        # GIVEN a project with an admin and two experts
        victim = getattr(team, target)
        before = capture_state(client, team.admin, team.project_id)

        # WHEN the expert sends the admin-only removal for the target
        response = send_route(
            client,
            "remove_member",
            team.expert.token,
            team.project_id,
            target_id=victim.user_id,
        )

        # THEN the request is forbidden and the target is still a member with the same role
        assert response.status_code == status.HTTP_403_FORBIDDEN
        after = capture_state(client, team.admin, team.project_id)
        assert after == before
        assert victim.user_id in after["roles"]

    def test_member_cannot_take_ownership(self, client, team):
        """A member cannot transfer the project to themselves; the admin stays the admin."""
        # GIVEN a project administered by someone else
        before = capture_state(client, team.admin, team.project_id)

        # WHEN the expert names themselves as the new admin
        response = send_route(
            client,
            "transfer_ownership",
            team.expert.token,
            team.project_id,
            actor_id=team.expert.user_id,
        )

        # THEN the request is forbidden and the admin is unchanged
        assert response.status_code == status.HTTP_403_FORBIDDEN
        after = capture_state(client, team.admin, team.project_id)
        assert after == before
        assert after["project"]["admin_id"] == team.admin.user_id


class TestAdminOfAnotherProjectIsOnlyAMemberHere:
    """Being admin of project P2 gives no admin rights on P1, where the caller is an expert."""

    @pytest.mark.parametrize("route", sorted(ADMIN_ROUTES))
    def test_admin_of_their_own_project_is_refused_on_this_one(self, client, team, invitee, route):
        """An expert of P1 who administers P2 still gets 403 on each admin route of P1."""
        # GIVEN an expert of P1 who also owns a project of their own, and a real invitation
        create_project(client, team.expert.token, "GammaProject")
        pending = invite(client, team.admin, team.project_id, invitee.email)
        before = capture_state(client, team.admin, team.project_id)

        # WHEN they send the admin route to P1
        response = send_route(
            client,
            route,
            team.expert.token,
            team.project_id,
            target_id=team.other_expert.user_id,
            actor_id=team.expert.user_id,
            invitee_email=team.admin.email,
            invitation_id=pending["id"],
        )

        # THEN it is forbidden as a role problem, and P1 is unchanged
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert capture_state(client, team.admin, team.project_id) == before


class TestOutsiderIsRefused:
    """Someone with no membership gets 404 and cannot change or remove anything."""

    @pytest.mark.parametrize("route", ["update_project", "delete_project"])
    def test_outsider_cannot_change_or_delete_project(self, client, team, invitee, route):
        """An outsider's PATCH or DELETE answers 404 and leaves the project listed and intact."""
        # GIVEN a project and a user who is not a member
        before = capture_state(client, team.admin, team.project_id)

        # WHEN the outsider sends the write
        response = send_route(client, route, invitee.token, team.project_id)

        # THEN it looks like a missing project and nothing happened
        assert response.status_code == status.HTTP_404_NOT_FOUND
        after = capture_state(client, team.admin, team.project_id)
        assert after == before
        assert team.project_id in after["admin_project_ids"]
        assert after["project"]["name"] == "AlphaProject"

    @pytest.mark.parametrize("aim", ["outsider", "expert"])
    def test_outsider_cannot_transfer_ownership(self, client, team, invitee, aim):
        """An outsider's transfer answers 404; the admin id and every role stay as they were."""
        # GIVEN a project and an outsider, who aims the transfer at themselves or at a member
        new_admin = invitee if aim == "outsider" else team.expert
        before = capture_state(client, team.admin, team.project_id)

        # WHEN the outsider asks for ownership to move
        response = send_route(
            client,
            "transfer_ownership",
            invitee.token,
            team.project_id,
            actor_id=new_admin.user_id,
        )

        # THEN the project is reported missing, and admin and roles are unchanged
        assert response.status_code == status.HTTP_404_NOT_FOUND
        after = capture_state(client, team.admin, team.project_id)
        assert after == before
        assert after["project"]["admin_id"] == team.admin.user_id
        assert after["roles"][team.admin.user_id] == "admin"
        assert invitee.user_id not in after["roles"]


class TestRightsFollowTheRole:
    """Rights move with the role: a former admin or a removed member loses access."""

    @pytest.mark.parametrize("route", ["update_project", "delete_project", "invite"])
    def test_former_admin_is_refused_after_a_transfer(self, client, team, invitee, route):
        """After handing the project over, the previous admin gets 403 on the admin routes."""
        # GIVEN the admin has transferred ownership to an expert
        handover = send_route(
            client,
            "transfer_ownership",
            team.admin.token,
            team.project_id,
            actor_id=team.expert.user_id,
        )
        assert handover.status_code == status.HTTP_200_OK
        before = capture_state(client, team.expert, team.project_id)
        assert before["roles"][team.admin.user_id] == "expert"
        assert before["roles"][team.expert.user_id] == "admin"

        # WHEN the former admin uses an admin route
        response = send_route(
            client,
            route,
            team.admin.token,
            team.project_id,
            invitee_email=invitee.email,
        )

        # THEN it is forbidden and the project is unchanged for its new admin
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert capture_state(client, team.expert, team.project_id) == before

    @pytest.mark.parametrize("route", ["remove_member", "transfer_ownership"])
    def test_former_admin_cannot_move_people_after_a_transfer(self, client, team, route):
        """The previous admin can neither remove a member nor take the project back."""
        # GIVEN the admin has transferred ownership to an expert
        handover = send_route(
            client,
            "transfer_ownership",
            team.admin.token,
            team.project_id,
            actor_id=team.expert.user_id,
        )
        assert handover.status_code == status.HTTP_200_OK
        before = capture_state(client, team.expert, team.project_id)

        # WHEN the former admin removes the other expert or names themselves admin again
        response = send_route(
            client,
            route,
            team.admin.token,
            team.project_id,
            target_id=team.other_expert.user_id,
            actor_id=team.admin.user_id,
        )

        # THEN it is forbidden and nobody's role or membership changed
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert capture_state(client, team.expert, team.project_id) == before

    @pytest.mark.parametrize(
        "route", ["get_project", "list_members", "list_opinions", "get_result"]
    )
    def test_removed_member_loses_access(self, client, team, route):
        """After the admin removes a member, that member gets 404 on the project's read routes."""
        # GIVEN an expert who could read the project and was then removed by the admin
        assert send_route(client, route, team.expert.token, team.project_id).status_code == 200
        self._remove_expert(client, team)
        before = capture_state(client, team.admin, team.project_id)

        # WHEN the removed member reads the project again
        response = send_route(client, route, team.expert.token, team.project_id)

        # THEN the project looks missing to them, and no longer lists them
        assert response.status_code == status.HTTP_404_NOT_FOUND
        projects = client.get("/api/v1/projects", headers=auth_header(team.expert.token))
        assert projects.json() == []
        assert team.expert.user_id not in before["roles"]
        assert capture_state(client, team.admin, team.project_id) == before

    @pytest.mark.parametrize("route", ["submit_opinion", "delete_opinion", "leave_project"])
    def test_removed_member_cannot_write(self, client, team, route):
        """A removed member can neither submit nor delete an opinion, and cannot leave again."""
        # GIVEN an expert who was removed from the project
        self._remove_expert(client, team)
        before = capture_state(client, team.admin, team.project_id)

        # WHEN they send the write
        response = send_route(client, route, team.expert.token, team.project_id)

        # THEN the access check reports the project missing, and nothing changed
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"detail": "Project not found"}
        assert capture_state(client, team.admin, team.project_id) == before

    @staticmethod
    def _remove_expert(client, team: Team) -> None:
        """Remove the team's first expert as the admin and check the removal worked.

        :param client: Test client instance
        :param team: Team whose ``expert`` is removed
        """
        removal = send_route(
            client,
            "remove_member",
            team.admin.token,
            team.project_id,
            target_id=team.expert.user_id,
        )
        assert removal.status_code == status.HTTP_204_NO_CONTENT
