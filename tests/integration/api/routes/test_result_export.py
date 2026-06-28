"""Tests for GET /api/v1/projects/{id}/result/export (PDF/CSV export)."""

from fastapi import status

from tests.integration.api.conftest import (
    auth_header,
    create_project,
    register_and_login,
    submit_opinion,
)


def _project_with_result(client, email: str, name: str = "Budget Case") -> tuple[str, str]:
    """Register a user, create a project, and submit one opinion to compute a result.

    :param client: Test client.
    :param email: Email to register the owner under.
    :param name: Project name.
    :return: The owner's token and the project id.
    """
    token = register_and_login(client, email)
    project = create_project(client, token, name)
    submit_opinion(client, token, project["id"], 20.0, 50.0, 80.0, "Lead")
    return token, project["id"]


class TestResultExport:
    """Tests for the per-project result export endpoint."""

    def test_csv_export_returns_attachment(self, client):
        """CSV export streams text/csv as a named attachment with the data."""
        token, project_id = _project_with_result(client, "csv@example.com")

        response = client.get(
            f"/api/v1/projects/{project_id}/result/export?format=csv",
            headers=auth_header(token),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"].startswith("text/csv")
        disposition = response.headers["content-disposition"]
        assert "attachment" in disposition
        assert "budget-case-results.csv" in disposition
        text = response.content.decode("utf-8-sig")
        assert "Expert" in text
        assert "Lead" in text

    def test_pdf_export_returns_pdf(self, client):
        """PDF export streams application/pdf with the PDF magic header."""
        token, project_id = _project_with_result(client, "pdf@example.com")

        response = client.get(
            f"/api/v1/projects/{project_id}/result/export?format=pdf",
            headers=auth_header(token),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"].startswith("application/pdf")
        assert response.content.startswith(b"%PDF")
        assert "attachment" in response.headers["content-disposition"]

    def test_czech_csv_uses_localized_labels(self, client):
        """Requesting lang=cs localizes the CSV column headers."""
        token, project_id = _project_with_result(client, "czech@example.com")

        response = client.get(
            f"/api/v1/projects/{project_id}/result/export?format=csv&lang=cs",
            headers=auth_header(token),
        )

        assert response.status_code == status.HTTP_200_OK
        assert "Pozice" in response.content.decode("utf-8-sig")

    def test_export_requires_authentication(self, client):
        """An unauthenticated export request is rejected."""
        _, project_id = _project_with_result(client, "auth@example.com")

        response = client.get(f"/api/v1/projects/{project_id}/result/export?format=csv")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_member_cannot_export(self, client):
        """A user who is not a project member cannot export its result."""
        _, project_id = _project_with_result(client, "owner@example.com")
        outsider = register_and_login(client, "outsider@example.com")

        response = client.get(
            f"/api/v1/projects/{project_id}/result/export?format=csv",
            headers=auth_header(outsider),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_export_without_result_returns_404(self, client):
        """Exporting a project that has no computed result returns 404."""
        token = register_and_login(client, "noresult@example.com")
        project = create_project(client, token, "Empty Project")

        response = client.get(
            f"/api/v1/projects/{project['id']}/result/export?format=csv",
            headers=auth_header(token),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_invalid_format_is_rejected(self, client):
        """An unsupported format value fails request validation."""
        token, project_id = _project_with_result(client, "badformat@example.com")

        response = client.get(
            f"/api/v1/projects/{project_id}/result/export?format=xml",
            headers=auth_header(token),
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
