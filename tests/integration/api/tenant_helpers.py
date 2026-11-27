"""Helpers that build a small multi-user tenant and read its state back through the API.

The tenant tests assert that a refused request changed nothing. ``capture_state`` is the
reading half of that: it records everything a refusal could have touched (the project, its
members and roles, every invitation row, the opinions), so a test compares one value before
and after instead of spot-checking a field.
"""

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import select

from api.db.models import Invitation
from tests.integration.api.conftest import (
    app_session,
    auth_header,
    create_project,
    register_and_login,
    submit_opinion,
)


@dataclass(frozen=True)
class Account:
    """A registered, verified user together with the token that authenticates it."""

    email: str
    token: str
    user_id: str


@dataclass(frozen=True)
class Team:
    """One project with its admin and two ordinary members, each with an opinion."""

    project: dict
    admin: Account
    expert: Account
    other_expert: Account

    @property
    def project_id(self) -> str:
        """Return the project's id as a string."""
        return self.project["id"]


_PROJECT = "/api/v1/projects/{project_id}"

# Every project-scoped route as (method, path, body). Placeholders are filled by
# ``send_route``: ``target_id`` is the user a request is aimed at, ``actor_id`` the caller,
# ``invitee_email`` a registered address and ``missing_id`` a random id. ``ADMIN_ROUTES``
# sit behind ProjectAdmin, ``MEMBER_ROUTES`` behind ProjectMember.
_OPINION = {"position": "Expert", "lower_bound": 40.0, "peak": 60.0, "upper_bound": 80.0}
ADMIN_ROUTES: dict[str, tuple[str, str, dict | None]] = {
    "update_project": ("PATCH", _PROJECT, {"name": "Renamed", "description": "Changed"}),
    "delete_project": ("DELETE", _PROJECT, None),
    "remove_member": ("DELETE", _PROJECT + "/members/{target_id}", None),
    "transfer_ownership": (
        "POST",
        _PROJECT + "/transfer-ownership",
        {"new_admin_id": "{actor_id}"},
    ),
    "invite": ("POST", _PROJECT + "/invite", {"email": "{invitee_email}"}),
    "list_invitations": ("GET", _PROJECT + "/invitations", None),
    "revoke_invitation": ("DELETE", _PROJECT + "/invitations/{missing_id}", None),
}
MEMBER_ROUTES: dict[str, tuple[str, str, dict | None]] = {
    "get_project": ("GET", _PROJECT, None),
    "list_members": ("GET", _PROJECT + "/members", None),
    "list_opinions": ("GET", _PROJECT + "/opinions", None),
    "submit_opinion": ("POST", _PROJECT + "/opinions", _OPINION),
    "delete_opinion": ("DELETE", _PROJECT + "/opinions", None),
    "get_result": ("GET", _PROJECT + "/result", None),
    "export_result": ("GET", _PROJECT + "/result/export?format=csv", None),
}
ALL_ROUTES = {**ADMIN_ROUTES, **MEMBER_ROUTES}


def send_route(
    client: TestClient, name: str, token: str, project_id: str, **context: str
) -> Response:
    """Send one of the project-scoped routes in ``ALL_ROUTES`` as the holder of a token.

    :param client: Test client instance
    :param name: Key of the route in ``ALL_ROUTES``
    :param token: Access token of the caller
    :param project_id: Project UUID string
    :param context: Values for the ``target_id``, ``actor_id``, ``invitee_email`` and
        ``missing_id`` placeholders the route may use
    :return: The raw response
    """
    method, path, body = ALL_ROUTES[name]
    values = {"project_id": project_id, "missing_id": str(uuid4()), **context}
    payload: Any = None
    if body is not None:
        payload = {
            key: value.format(**values) if isinstance(value, str) else value
            for key, value in body.items()
        }
    return client.request(method, path.format(**values), json=payload, headers=auth_header(token))


def register_account(client: TestClient, email: str) -> Account:
    """Register and verify a user, then read their id back from their own profile.

    :param client: Test client instance
    :param email: Address to register
    :return: The account with its access token and user id
    """
    token = register_and_login(client, email)
    profile = client.get("/api/v1/users/me", headers=auth_header(token))
    return Account(email=email, token=token, user_id=profile.json()["id"])


def add_expert(client: TestClient, admin: Account, project_id: str, email: str) -> Account:
    """Register a user and make them an ordinary member of a project (invite, then accept).

    :param client: Test client instance
    :param admin: Admin of the project
    :param project_id: Project UUID string
    :param email: Address of the new member
    :return: The new member's account
    """
    account = register_account(client, email)
    invited = client.post(
        f"/api/v1/projects/{project_id}/invite",
        json={"email": email},
        headers=auth_header(admin.token),
    )
    assert invited.status_code == 201
    accepted = client.post(
        f"/api/v1/invitations/{invited.json()['id']}/accept",
        headers=auth_header(account.token),
    )
    assert accepted.status_code == 201
    return account


def make_team(client: TestClient, tag: str, project_name: str) -> Team:
    """Build a project with an admin and two experts who have each submitted an opinion.

    :param client: Test client instance
    :param tag: Short alphanumeric label that keeps the addresses of two teams apart
    :param project_name: Name of the project (alphanumeric, so storage escaping is moot)
    :return: The project and its three accounts
    """
    admin = register_account(client, f"{tag}-admin@example.com")
    project = create_project(client, admin.token, project_name)
    expert = add_expert(client, admin, project["id"], f"{tag}-expert@example.com")
    other_expert = add_expert(client, admin, project["id"], f"{tag}-second@example.com")
    for member in (expert, other_expert):
        submit_opinion(client, member.token, project["id"], position=f"{tag}pos")
    return Team(project=project, admin=admin, expert=expert, other_expert=other_expert)


def capture_state(client: TestClient, admin: Account, project_id: str) -> dict:
    """Read back everything a refused request on a project could have changed.

    Reads through the API as the project's admin, plus every invitation row in the whole
    database, so an invitation created in any tenant would show up as a difference.

    :param client: Test client instance
    :param admin: Current admin of the project
    :param project_id: Project UUID string
    :return: Project, member roles, opinions, the admin's project ids and all invitation rows
    """
    headers = auth_header(admin.token)
    project = client.get(f"/api/v1/projects/{project_id}", headers=headers)
    members = client.get(f"/api/v1/projects/{project_id}/members", headers=headers)
    opinions = client.get(f"/api/v1/projects/{project_id}/opinions", headers=headers)
    listing = client.get("/api/v1/projects", headers=headers)
    with app_session(client) as session:
        invitations = sorted(
            (str(row.project_id), str(row.invitee_id))
            for row in session.exec(select(Invitation)).all()
        )
    return {
        "project": project.json(),
        "roles": {member["user_id"]: member["role"] for member in members.json()},
        "opinions": sorted((item["id"], item["peak"]) for item in opinions.json()),
        "admin_project_ids": sorted(item["id"] for item in listing.json()),
        "invitations": invitations,
    }
