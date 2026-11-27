"""A project's result export holds that project's data and nobody's e-mail address.

The export prints every expert's name and estimate into a file that leaves the app. Two
projects are built, each with its own admin and experts, and the first project's CSV and
PDF are read back: its own markers must be there, so that an absent marker means
something, and no address and nothing of the second project may be.
"""

from io import BytesIO
from uuid import UUID

import pytest
from pypdf import PdfReader

from api.db.models import MemberRole, ProjectMember
from tests.integration.api.conftest import (
    DEFAULT_TEST_PASSWORD,
    app_session,
    auth_header,
    create_project,
    register_verified,
    stored_accounts,
    submit_opinion,
)

ROLES = ("admin", "expertone", "experttwo")


def _build_project(client, tag: str) -> dict:
    """Create a project with an admin and two experts, each with an opinion.

    Every name and position carries ``tag`` and is alphanumeric, so no marker depends on
    how a character is escaped. Addresses are lower case, as the account stores them.
    Experts join through a direct row; opinions go through the API so the result is
    calculated as in use.

    :param client: Test client.
    :param tag: Letters that make this project's markers unique.
    :return: ``project`` (the name and id), and ``people``, one dict per account.
    """
    people = []
    for role in ROLES:
        email = f"{role}.{tag}@example.com".lower()
        register_verified(
            client, email, first_name=f"First{role}{tag}", last_name=f"Last{role}{tag}"
        )
        login = client.post(
            "/api/v1/auth/login", data={"username": email, "password": DEFAULT_TEST_PASSWORD}
        )
        people.append(
            {
                "email": email,
                "token": login.json()["access_token"],
                "markers": (f"First{role}{tag}", f"Last{role}{tag}", f"Position{role}{tag}"),
            }
        )
    project = create_project(client, people[0]["token"], f"Project{tag}")
    with app_session(client) as session:
        for person in people[1:]:
            user_id = stored_accounts(client, person["email"])[0]["id"]
            session.add(
                ProjectMember(
                    project_id=UUID(project["id"]), user_id=user_id, role=MemberRole.EXPERT
                )
            )
        session.commit()
    for offset, person in enumerate(people):
        submit_opinion(
            client,
            person["token"],
            project["id"],
            lower_bound=10.0 + offset,
            peak=20.0 + offset,
            upper_bound=30.0 + offset,
            position=person["markers"][2],
        )
    return {"project": project, "people": people}


@pytest.fixture
def exports(client):
    """Export the first of two unrelated projects, in both formats, as its admin.

    :param client: Test client.
    :return: ``alpha`` and ``beta`` (the projects as built), and ``files``: the
        exported bytes and whitespace-free text of the first, per format.
    """
    alpha, beta = _build_project(client, "Alpha"), _build_project(client, "Beta")
    files = {}
    for export_format in ("csv", "pdf"):
        response = client.get(
            f"/api/v1/projects/{alpha['project']['id']}/result/export?format={export_format}",
            headers=auth_header(alpha["people"][0]["token"]),
        )
        assert response.status_code == 200
        if export_format == "csv":
            text = response.content.decode("utf-8-sig")
        else:
            text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
        # The PDF breaks a long word wherever the column ends, so whitespace is dropped.
        files[export_format] = (response.content, "".join(text.split()))
    return {"alpha": alpha, "beta": beta, "files": files}


@pytest.mark.parametrize("export_format", ["csv", "pdf"])
class TestResultExportContents:
    """The export holds its own project's data and leaves out addresses and other projects."""

    def test_export_holds_its_own_markers(self, exports, export_format):
        """
        GIVEN two projects, each with an admin and two experts
        WHEN the first project's result is exported
        THEN every expert's name and position appear, and the project name in the PDF
            (the CSV carries none), so the absence checks below are meaningful
        """
        # GIVEN
        _, text = exports["files"][export_format]

        # THEN
        if export_format == "pdf":
            assert exports["alpha"]["project"]["name"] in text
        for person in exports["alpha"]["people"]:
            assert all(marker in text for marker in person["markers"])

    def test_export_holds_no_address_of_anyone(self, exports, export_format):
        """
        GIVEN two projects whose people have registered addresses
        WHEN the first project's result is exported
        THEN no address of either project's people appears, and no '@' sign in the text
        """
        # GIVEN
        content, text = exports["files"][export_format]

        # THEN
        assert "@" not in text
        for person in (*exports["alpha"]["people"], *exports["beta"]["people"]):
            assert person["email"].encode() not in content
            assert person["email"] not in text

    def test_export_holds_nothing_of_another_project(self, exports, export_format):
        """
        GIVEN two projects with distinct names, experts and positions
        WHEN the first project's result is exported
        THEN none of the second project's name, names or positions appears
        """
        # GIVEN
        _, text = exports["files"][export_format]

        # THEN
        assert exports["beta"]["project"]["name"] not in text
        for person in exports["beta"]["people"]:
            assert not any(marker in text for marker in person["markers"])
