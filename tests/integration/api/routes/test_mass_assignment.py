"""A request body carrying a field the schema does not name is refused and changes nothing.

The request models forbid extra fields, so a forged ``admin_id`` or ``user_id`` must reach
neither the model nor the database. Each case posts the forged field through the real
route next to otherwise valid data, then compares every row of the users, projects,
memberships, opinions and invitations tables with a snapshot taken before: no project
created, none changed, no opinion or invitation stored, the admin and every role as they
were. A 422 alone would not show that nothing was written before the refusal.
"""

from uuid import UUID

import pytest
from fastapi import status

from api.db.models import ProjectMember
from tests.integration.api.conftest import (
    DEFAULT_TEST_PASSWORD,
    app_session,
    auth_header,
    create_project,
    register_and_login,
    stored_accounts,
)
from tests.integration.api.state_snapshot import snapshot

# Fixed, not random, so the parametrised test ids are the same in every xdist worker.
FORGED_ID = "11111111-2222-4333-8444-555555555555"
SERVER_OWNED = [
    ("admin_id", FORGED_ID),
    ("id", FORGED_ID),
    ("is_example", True),
    ("created_at", "2000-01-01T00:00:00Z"),
]
OPINION = {"position": "Forger", "lower_bound": 10.0, "peak": 20.0, "upper_bound": 30.0}

# (method, path template, valid body, forged field, forged value). ``{victim}`` in a value
# is the other member's id, ``{project}`` in the path the project's id.
CASES = (
    [
        pytest.param(
            "POST", "/api/v1/projects", {"name": "Forged"}, field, value, id=f"create-{field}"
        )
        for field, value in SERVER_OWNED
    ]
    + [
        pytest.param(
            "PATCH",
            "/api/v1/projects/{project}",
            {"name": "Renamed"},
            field,
            value,
            id=f"patch-{field}",
        )
        for field, value in SERVER_OWNED
    ]
    + [
        pytest.param(
            "POST",
            "/api/v1/projects/{project}/opinions",
            OPINION,
            "user_id",
            "{victim}",
            id="opinion-user",
        ),
        pytest.param(
            "POST",
            "/api/v1/projects/{project}/opinions",
            OPINION,
            "project_id",
            FORGED_ID,
            id="opinion-project",
        ),
    ]
    + [
        pytest.param(
            "POST",
            "/api/v1/projects/{project}/invite",
            {"email": "spare@example.com"},
            field,
            value,
            id=f"invite-{field}",
        )
        for field, value in [
            ("inviter_id", "{victim}"),
            ("invitee_id", "{victim}"),
            ("project_id", FORGED_ID),
        ]
    ]
    + [
        pytest.param(
            "POST",
            "/api/v1/projects/{project}/transfer-ownership",
            {"new_admin_id": "{victim}"},
            field,
            "{victim}",
            id=f"transfer-{field}",
        )
        for field in ("admin_id", "role", "unexpected")
    ]
    + [
        pytest.param(
            "PUT", "/api/v1/users/me", {"first_name": "Renamed"}, field, value, id=f"me-{field}"
        )
        for field, value in [("email", "taken-over@example.com"), ("is_demo", True)]
    ]
)


def _assert_extra_forbidden(response, field: str) -> None:
    """Check a response is a 422 whose validator names ``field`` as an extra input.

    :param response: The route's response.
    :param field: The forged field, found at the end of an error's location, so a field
        nested inside a list item counts too.
    """
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert any(
        error["type"] == "extra_forbidden" and error["loc"][-1] == field
        for error in response.json()["detail"]
    ), response.json()


@pytest.mark.parametrize(("method", "path", "body", "field", "value"), CASES)
def test_forged_field_is_refused_and_nothing_changes(client, method, path, body, field, value):
    """
    GIVEN a project with its admin and a second member (and a spare account to invite, for
        the invite cases)
    WHEN the admin sends a valid body together with a field the server owns
    THEN the validator names that field as extra, with a 422, and no row of any tenant
        table differs from before the request
    """
    # GIVEN
    token = register_and_login(client, "owner@example.com")
    register_and_login(client, "victim@example.com")
    if path.endswith("/invite"):
        register_and_login(client, "spare@example.com")
    project = create_project(client, token, "Original Name")
    victim = stored_accounts(client, "victim@example.com")[0]["id"]
    with app_session(client) as session:
        session.add(ProjectMember(project_id=UUID(project["id"]), user_id=victim))
        session.commit()
        before = snapshot(session)

    # WHEN
    sent = {**body, field: value}
    sent = {key: str(victim) if val == "{victim}" else val for key, val in sent.items()}
    response = client.request(
        method, path.format(project=project["id"]), json=sent, headers=auth_header(token)
    )

    # THEN
    _assert_extra_forbidden(response, field)
    with app_session(client) as session:
        assert snapshot(session) == before


@pytest.mark.parametrize(
    ("field", "value"),
    [("is_demo", True), ("email_verified_at", "2000-01-01T00:00:00Z")],
)
def test_registration_refuses_forged_account_flags(client, field, value):
    """
    GIVEN no account for an address
    WHEN it is registered with a valid body plus a flag the server alone sets
    THEN the validator names the flag as extra, with a 422, and no account is created
    """
    # GIVEN
    email = "newcomer@example.com"
    with app_session(client) as session:
        before = snapshot(session)

    # WHEN
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": DEFAULT_TEST_PASSWORD,
            "first_name": "New",
            "last_name": "Comer",
            field: value,
        },
    )

    # THEN
    _assert_extra_forbidden(response, field)
    assert stored_accounts(client, email) == []
    with app_session(client) as session:
        assert snapshot(session) == before


@pytest.mark.parametrize("nested", [False, True], ids=["body", "disposition-item"])
def test_account_deletion_refuses_extra_keys(client, nested):
    """
    GIVEN a signed-in user who owns a project
    WHEN the account is deleted with an extra key in the body, or inside a disposition item
    THEN the validator names the key as extra, with a 422, and the account and its
        project are as they were
    """
    # GIVEN
    token = register_and_login(client, "leaver@example.com")
    project = create_project(client, token, "Owned Project")
    with app_session(client) as session:
        before = snapshot(session)
    body = {"current_password": DEFAULT_TEST_PASSWORD, "project_dispositions": []}
    if nested:
        body["project_dispositions"] = [
            {"project_id": project["id"], "action": "delete", "forged": True}
        ]
    else:
        body["forged"] = True

    # WHEN
    response = client.request("DELETE", "/api/v1/users/me", json=body, headers=auth_header(token))

    # THEN
    _assert_extra_forbidden(response, "forged")
    assert nested == (response.json()["detail"][0]["loc"][1:2] == ["project_dispositions"])
    assert client.get("/api/v1/auth/me", headers=auth_header(token)).status_code == 200
    with app_session(client) as session:
        assert snapshot(session) == before
