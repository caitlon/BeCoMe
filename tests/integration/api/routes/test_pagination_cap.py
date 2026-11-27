"""A list endpoint never returns more than MAX_PAGE_SIZE rows, whatever limit is asked for.

``PaginationParams`` clamps an oversized limit rather than rejecting it. Each list route
is asked for a thousand rows from a database seeded with more than the cap, so a route that
bypassed the shared parameters, or a service that ignored the limit, returns the whole
table and fails here. Rows are inserted directly: registering over a hundred users through
the API would spend the time on password hashing.
"""

from uuid import UUID

import pytest
from sqlmodel import Session, func, select

from api.db.models import ExpertOpinion, Invitation, MemberRole, Project, ProjectMember, User
from api.pagination import MAX_PAGE_SIZE
from tests.integration.api.conftest import (
    app_session,
    auth_header,
    register_and_login,
    stored_accounts,
)

OVER_THE_CAP = MAX_PAGE_SIZE + 5
OWNER_EMAIL = "owner@example.com"


def _users(session: Session, prefix: str, count: int) -> list[User]:
    """Insert ``count`` users with distinct addresses and flush them.

    :param session: Session to add to.
    :param prefix: Local part prefix of the addresses.
    :param count: How many users to add.
    :return: The added users, with ids.
    """
    users = [
        User(
            email=f"{prefix}{index}@example.com",
            hashed_password="x",
            first_name=f"First{index}",
            last_name=f"Last{index}",
        )
        for index in range(count)
    ]
    session.add_all(users)
    session.flush()
    return users


def _seed_over_the_cap(session: Session, owner_id: UUID) -> dict[str, str]:
    """Seed more rows than one page for each list the tests read.

    The owner administers one crowded project (members, opinions and pending invitations
    over the cap) and, in addition, administers over the cap of other projects. A second
    admin has invited the owner to over the cap of projects.

    :param session: Session to add to; the function commits.
    :param owner_id: The signed-in user's id.
    :return: ``{"project_id": ...}`` of the crowded project.
    """
    crowded = Project(name="Crowded", admin_id=owner_id)
    session.add(crowded)
    session.flush()
    session.add(ProjectMember(project_id=crowded.id, user_id=owner_id, role=MemberRole.ADMIN))
    for expert in _users(session, "expert", OVER_THE_CAP):
        session.add(ProjectMember(project_id=crowded.id, user_id=expert.id))
        session.add(
            ExpertOpinion(
                project_id=crowded.id,
                user_id=expert.id,
                position=f"Position{expert.first_name}",
                lower_bound=10.0,
                peak=20.0,
                upper_bound=30.0,
            )
        )
    for invitee in _users(session, "invitee", OVER_THE_CAP):
        session.add(Invitation(project_id=crowded.id, invitee_id=invitee.id, inviter_id=owner_id))
    for index in range(OVER_THE_CAP):
        own = Project(name=f"Owned{index}", admin_id=owner_id)
        session.add(own)
        session.flush()
        session.add(ProjectMember(project_id=own.id, user_id=owner_id, role=MemberRole.ADMIN))
    (other_admin,) = _users(session, "otheradmin", 1)
    for index in range(OVER_THE_CAP):
        offered = Project(name=f"Offered{index}", admin_id=other_admin.id)
        session.add(offered)
        session.flush()
        session.add(
            ProjectMember(project_id=offered.id, user_id=other_admin.id, role=MemberRole.ADMIN)
        )
        session.add(
            Invitation(project_id=offered.id, invitee_id=owner_id, inviter_id=other_admin.id)
        )
    session.commit()
    return {"project_id": str(crowded.id)}


@pytest.fixture
def crowded(client):
    """Sign an owner in and seed every list past the cap.

    :param client: Test client with the integration app.
    :return: The owner's headers and the crowded project's id.
    """
    token = register_and_login(client, OWNER_EMAIL)
    owner_id = stored_accounts(client, OWNER_EMAIL)[0]["id"]
    with app_session(client) as session:
        seeded = _seed_over_the_cap(session, owner_id)
    return auth_header(token), seeded["project_id"]


LIST_ROUTES = [
    pytest.param("/api/v1/projects", id="projects"),
    pytest.param("/api/v1/projects/{project_id}/opinions", id="opinions"),
    pytest.param("/api/v1/projects/{project_id}/members", id="members"),
    pytest.param("/api/v1/projects/{project_id}/invitations", id="project-invitations"),
    pytest.param("/api/v1/invitations", id="my-invitations"),
]


class TestListLimitIsCapped:
    """An oversized limit is clamped to the page cap on every list route."""

    @pytest.mark.parametrize("path", LIST_ROUTES)
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            pytest.param("?limit=1000", MAX_PAGE_SIZE, id="limit-1000"),
            pytest.param("", MAX_PAGE_SIZE, id="no-limit"),
            pytest.param("?limit=7", 7, id="limit-7"),
        ],
    )
    def test_page_size_never_exceeds_the_cap(self, client, crowded, path, query, expected):
        """
        GIVEN a list holding more rows than MAX_PAGE_SIZE
        WHEN it is requested with limit=1000, with no limit, and with limit=7
        THEN exactly the cap, the cap, and seven rows come back: the cap is a ceiling,
            also the default, and does not replace a smaller limit
        """
        # GIVEN
        headers, project_id = crowded

        # WHEN
        response = client.get(path.format(project_id=project_id) + query, headers=headers)

        # THEN
        assert response.status_code == 200
        assert len(response.json()) == expected

    def test_the_seeded_lists_really_exceed_the_cap(self, client, crowded):
        """
        GIVEN the seeded database
        WHEN the rows behind each list are counted
        THEN each holds more than MAX_PAGE_SIZE, so the cap tests above are not vacuous
        """
        # GIVEN
        crowded_id = UUID(crowded[1])
        owner_id = stored_accounts(client, OWNER_EMAIL)[0]["id"]
        wanted = {
            "projects": (ProjectMember, ProjectMember.user_id == owner_id),
            "members": (ProjectMember, ProjectMember.project_id == crowded_id),
            "opinions": (ExpertOpinion, ExpertOpinion.project_id == crowded_id),
            "project invitations": (Invitation, Invitation.project_id == crowded_id),
            "my invitations": (Invitation, Invitation.invitee_id == owner_id),
        }

        # WHEN
        with app_session(client) as session:
            counts = {
                name: session.exec(select(func.count()).select_from(model).where(clause)).one()
                for name, (model, clause) in wanted.items()
            }

        # THEN
        assert {name for name, count in counts.items() if count <= MAX_PAGE_SIZE} == set()
