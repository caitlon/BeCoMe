"""Activation hands the account its example project, and never fails because of it.

The seed is demo content. An account that could not be logged into because its example
project failed to write would be a far worse outcome than an account without one, so
the route swallows the failure -- and this module holds it to that.
"""

from unittest.mock import patch

from sqlmodel import col, select

from api.db.models import Project


class TestActivationSeedsTheExample:
    """The happy path."""

    def test_activated_account_gets_an_example_project(self, client, session, pending_account):
        """One example project, owned by the account that just activated."""
        # GIVEN
        token, password = pending_account

        # WHEN
        response = client.post(
            "/api/v1/auth/verify-email",
            json={"token": token, "password": password},
        )
        projects = session.exec(select(Project).where(col(Project.is_example).is_(True))).all()

        # THEN
        assert response.status_code == 200
        assert len(projects) == 1

    def test_language_reaches_the_seed(self, client, session, pending_account):
        """Activating from the Czech UI stores Czech text."""
        # GIVEN
        token, password = pending_account

        # WHEN
        client.post(
            "/api/v1/auth/verify-email",
            json={"token": token, "password": password, "language": "cs"},
        )
        project = session.exec(select(Project).where(col(Project.is_example).is_(True))).first()

        # THEN
        assert project.name == "Plánování protipovodňové ochrany"


class TestSeedFailureIsContained:
    """The promise that demo content cannot lock anyone out."""

    def test_activation_succeeds_when_seeding_raises(self, client, session, pending_account):
        """The account is verified and no example project is left half-written."""
        # GIVEN
        token, password = pending_account

        # WHEN
        with patch(
            "api.services.example_project_service.ExampleProjectService.seed_for",
            side_effect=RuntimeError("seeding is broken"),
        ):
            response = client.post(
                "/api/v1/auth/verify-email",
                json={"token": token, "password": password},
            )
        projects = session.exec(select(Project)).all()

        # THEN
        assert response.status_code == 200
        assert projects == []
