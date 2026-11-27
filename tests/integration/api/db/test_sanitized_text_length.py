"""PostgreSQL tests: sanitized text never outgrows its column.

``&``, ``<`` and ``>`` used to leave the sanitizer as ``&amp;``, ``&lt;`` and ``&gt;``, so a
name at the schema's own 255-character cap grew past the VARCHAR(255) column and the insert
failed with an unhandled 500 on PostgreSQL. SQLite does not enforce VARCHAR lengths, so only
this tier can see it. Each test runs the HTTP routes against a throwaway PostgreSQL.

These tests need PostgreSQL and are skipped when pg_ctl is not on PATH.

Run with: uv run pytest tests/integration/api/db/test_sanitized_text_length.py -n 0
"""

import shutil

import pytest
from sqlalchemy import create_engine
from sqlmodel import SQLModel

from tests.integration.api.conftest import create_project, register_and_login
from tests.shared.helpers import auth_header

pytestmark = pytest.mark.skipif(
    not shutil.which("pg_ctl"),
    reason="PostgreSQL not installed (pg_ctl not found in PATH)",
)


def load_schema(**kwargs):
    """Initialize the throwaway database with the SQLModel schema."""
    connection = (
        f"postgresql+psycopg2://{kwargs['user']}:"
        f"@{kwargs['host']}:{kwargs['port']}/{kwargs['dbname']}"
    )
    engine = create_engine(connection)
    SQLModel.metadata.create_all(engine)
    engine.dispose()


try:
    from pytest_postgresql import factories

    postgresql_proc = factories.postgresql_proc(load=[load_schema])
    postgresql = factories.postgresql("postgresql_proc")
except ImportError:
    postgresql_proc = None
    postgresql = None


@pytest.fixture
def test_engine(postgresql):
    """Point the shared ``client`` fixture at PostgreSQL instead of in-memory SQLite."""
    connection = (
        f"postgresql+psycopg2://{postgresql.info.user}:"
        f"@{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"
    )
    engine = create_engine(connection)
    yield engine
    engine.dispose()


SPECIAL_CHARS = ["&", "<", ">"]


class TestProjectTextAtColumnWidth:
    """Project text at the schema cap is stored whole on PostgreSQL."""

    @pytest.mark.parametrize("char", SPECIAL_CHARS)
    def test_create_project_with_every_text_field_at_its_cap(self, client, char):
        """
        GIVEN a name of 255, a unit of 50 and a description of 2000 special characters
        WHEN the project is created
        THEN it is stored and returned exactly as sent
        """
        # GIVEN
        token = register_and_login(client)
        payload = {
            "name": char * 255,
            "scale_unit": char * 50,
            "description": char * 2000,
        }

        # WHEN
        response = client.post("/api/v1/projects", json=payload, headers=auth_header(token))

        # THEN
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == payload["name"]
        assert body["scale_unit"] == payload["scale_unit"]
        assert body["description"] == payload["description"]

    @pytest.mark.parametrize("char", SPECIAL_CHARS)
    def test_update_project_with_every_text_field_at_its_cap(self, client, char):
        """
        GIVEN an existing project
        WHEN it is updated with a name of 255, a unit of 50 and a description of 2000
            special characters
        THEN the new values are stored and returned exactly as sent
        """
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)
        payload = {
            "name": char * 255,
            "scale_unit": char * 50,
            "description": char * 2000,
        }

        # WHEN
        response = client.patch(
            f"/api/v1/projects/{project['id']}", json=payload, headers=auth_header(token)
        )

        # THEN
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == payload["name"]
        assert body["scale_unit"] == payload["scale_unit"]
        assert body["description"] == payload["description"]

        # AND a fresh read returns the stored row, not the update response
        stored = client.get(f"/api/v1/projects/{project['id']}", headers=auth_header(token))
        assert stored.json()["name"] == payload["name"]


class TestOpinionPositionAtColumnWidth:
    """An opinion position at the schema cap is stored whole on PostgreSQL."""

    @pytest.mark.parametrize("char", SPECIAL_CHARS)
    def test_submit_opinion_with_position_at_its_cap(self, client, char):
        """
        GIVEN a position of 255 special characters
        WHEN the opinion is submitted
        THEN it is stored and listed exactly as sent
        """
        # GIVEN
        token = register_and_login(client)
        project = create_project(client, token)
        position = char * 255

        # WHEN
        response = client.post(
            f"/api/v1/projects/{project['id']}/opinions",
            json={"position": position, "lower_bound": 40.0, "peak": 60.0, "upper_bound": 80.0},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 201
        assert response.json()["position"] == position
        listed = client.get(
            f"/api/v1/projects/{project['id']}/opinions", headers=auth_header(token)
        ).json()
        assert [row["position"] for row in listed] == [position]
