"""A project's result export holds that project's data and nobody's e-mail address.

The export prints every expert's name and estimate into a file that leaves the app. Two
projects are built, each with its own admin and experts, and the first project's CSV and
PDF are read back: its own markers must be there, so that an absent marker means
something, and no address and nothing of the second project may be. The projects differ in
expert count and in every opinion value, so the aggregate figures and the expert count
printed in a report say which project's calculated result it was drawn from.
"""

import re
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
# One (lower, peak, upper) per expert. The projects share no value and no expert count.
ALPHA_OPINIONS = [(10.0, 20.0, 30.0), (11.0, 21.0, 31.0), (15.0, 25.0, 35.0)]
BETA_OPINIONS = [(60.0, 70.0, 80.0), (64.0, 74.0, 84.0)]
AGGREGATES = ("best_compromise", "arithmetic_mean", "median")
PLACES = {"csv": 4, "pdf": 2}


def _build_project(client, tag: str, opinions: list[tuple[float, float, float]]) -> dict:
    """Create a project with an admin and experts, one opinion each.

    Every name and position carries ``tag`` and is alphanumeric, so no marker depends on
    how a character is escaped. Addresses are lower case, as the account stores them.
    Experts join through a direct row; opinions go through the API so the result is
    calculated as in use.

    :param client: Test client.
    :param tag: Letters that make this project's markers unique.
    :param opinions: ``(lower, peak, upper)`` for the admin and each expert in turn.
    :return: ``project`` (the name and id), ``people`` (one dict per account), and
        ``figures``: its calculated aggregates as the result endpoint reports them.
    """
    people = []
    for role in ROLES[: len(opinions)]:
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
    for person, (lower, peak, upper) in zip(people, opinions, strict=True):
        submit_opinion(
            client,
            person["token"],
            project["id"],
            lower_bound=lower,
            peak=peak,
            upper_bound=upper,
            position=person["markers"][2],
        )
    result = client.get(
        f"/api/v1/projects/{project['id']}/result", headers=auth_header(people[0]["token"])
    ).json()
    figures = [result[name][bound] for name in AGGREGATES for bound in ("lower", "peak", "upper")]
    return {"project": project, "people": people, "figures": figures, "experts": len(people)}


@pytest.fixture
def projects(client) -> dict:
    """Build two unrelated projects, with different opinions and expert counts.

    :param client: Test client.
    :return: ``alpha`` and ``beta`` as built by :func:`_build_project`.
    """
    # The other project is built first so that an unfiltered result lookup would return it.
    beta = _build_project(client, "Beta", BETA_OPINIONS)
    alpha = _build_project(client, "Alpha", ALPHA_OPINIONS)
    return {"alpha": alpha, "beta": beta}


def _export(client, built: dict, export_format: str) -> tuple[bytes, str]:
    """Export a project's result as its admin and read it back.

    :param client: Test client.
    :param built: The project, as built by :func:`_build_project`.
    :param export_format: ``csv`` or ``pdf``.
    :return: The file's bytes and its text with all whitespace removed (the PDF breaks a
        long word wherever the column ends).
    """
    response = client.get(
        f"/api/v1/projects/{built['project']['id']}/result/export?format={export_format}",
        headers=auth_header(built["people"][0]["token"]),
    )
    assert response.status_code == 200
    if export_format == "csv":
        text = response.content.decode("utf-8-sig")
    else:
        text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
    return response.content, "".join(text.split())


def _figures(built: dict, export_format: str) -> set[str]:
    """Format a project's aggregate figures the way the given export prints them.

    :param built: The project, as built by :func:`_build_project`.
    :param export_format: ``csv`` (four decimals) or ``pdf`` (two).
    :return: The distinct figures as text.
    """
    return {f"{value:.{PLACES[export_format]}f}" for value in built["figures"]}


@pytest.mark.parametrize("export_format", ["csv", "pdf"])
class TestResultExportContents:
    """The export holds its own project's data and leaves out addresses and other projects."""

    def test_export_holds_its_own_markers(self, client, projects, export_format):
        """
        GIVEN two projects, each with an admin and experts
        WHEN the first project's result is exported
        THEN every expert's name and position appear, and the project name in the PDF
            (the CSV carries none), so the absence checks below are meaningful
        """
        # GIVEN
        alpha = projects["alpha"]

        # WHEN
        _, text = _export(client, alpha, export_format)

        # THEN
        if export_format == "pdf":
            assert alpha["project"]["name"] in text
        for person in alpha["people"]:
            assert all(marker in text for marker in person["markers"])

    def test_export_is_drawn_from_its_own_result(self, client, projects, export_format):
        """
        GIVEN two projects with different expert counts and no opinion value in common
        WHEN the first project's result is exported
        THEN its own expert count and aggregate figures are printed, and the second
            project's count and figures are not
        """
        # GIVEN
        alpha, beta = projects["alpha"], projects["beta"]
        assert alpha["experts"] != beta["experts"]

        # WHEN
        _, text = _export(client, alpha, export_format)

        # THEN
        assert re.search(rf"Experts[,:]{alpha['experts']}(?!\d)", text)
        assert not re.search(rf"Experts[,:]{beta['experts']}(?!\d)", text)
        assert all(figure in text for figure in _figures(alpha, export_format))
        assert not [figure for figure in _figures(beta, export_format) if figure in text]

    def test_export_holds_no_address_of_anyone(self, client, projects, export_format):
        """
        GIVEN two projects whose people have registered addresses
        WHEN the first project's result is exported
        THEN no address of either project's people appears, and no '@' sign in the text
        """
        # GIVEN
        alpha, beta = projects["alpha"], projects["beta"]

        # WHEN
        content, text = _export(client, alpha, export_format)

        # THEN
        assert "@" not in text
        for person in (*alpha["people"], *beta["people"]):
            assert person["email"].encode() not in content
            assert person["email"] not in text

    def test_export_holds_nothing_of_another_project(self, client, projects, export_format):
        """
        GIVEN two projects with distinct names, experts and positions
        WHEN the first project's result is exported
        THEN none of the second project's name, names or positions appears
        """
        # GIVEN
        beta = projects["beta"]

        # WHEN
        _, text = _export(client, projects["alpha"], export_format)

        # THEN
        assert beta["project"]["name"] not in text
        for person in beta["people"]:
            assert not any(marker in text for marker in person["markers"])
