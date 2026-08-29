"""Activation hands the account its example project, and never fails because of it.

The seed is demo content. An account that could not be logged into because its example
project failed to write would be a far worse outcome than an account without one, so
the route swallows the failure, and this module holds it to that.
"""

from unittest.mock import patch

from sqlmodel import col, select

from api.db.models import CalculationResult, ExpertOpinion, Project, User

# Matches the fixed address the ``pending_account`` fixture registers.
_PENDING_EMAIL = "pending@example.com"


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
        """The account is verified and usable, and no example project is half-written."""
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
        user = session.exec(select(User).where(User.email == _PENDING_EMAIL)).first()
        assert user is not None, "the pending account itself must still exist"
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": _PENDING_EMAIL, "password": password},
        )
        projects = session.exec(select(Project)).all()

        # THEN
        assert response.status_code == 200
        assert user.email_verified_at is not None
        assert login_response.status_code == 200
        assert projects == []

    def test_activation_succeeds_when_seeding_poisons_the_session(
        self, client, session, pending_account
    ):
        """A commit failure inside seeding must not turn a completed activation into a 500.

        Unlike the two tests above, this reproduces the actual production failure shape
        instead of a side_effect that never touches the database. seed_for's own commit
        expires every attribute the shared request session holds for ``user``; a later
        commit inside the seeding path (CalculationService.recalculate, standing in for
        it here) then fails and leaves that session needing rollback. Reading an expired
        attribute off ``user`` afterwards, as the route's except block used to via
        ``user.id``, issues a refresh SELECT into the poisoned session and raises
        PendingRollbackError instead of the plain id the route now captures up front.
        """
        # GIVEN
        token, password = pending_account

        def poison_the_session(self, user_id, language="en"):
            # Mirrors seed_for's own commit of the project rows, which is what expires
            # every attribute on `user` in production.
            self._session.add(
                User(
                    email="seed-marker@example.com",
                    hashed_password="x",
                    first_name="Seed",
                    last_name="Marker",
                )
            )
            self._session.commit()
            # And a second commit that actually fails, standing in for the commit
            # inside CalculationService.recalculate, leaving the session needing
            # rollback rather than merely raising in Python before touching the database.
            self._session.add(
                User(
                    email="seed-marker@example.com",
                    hashed_password="x",
                    first_name="Seed",
                    last_name="Marker",
                )
            )
            self._session.commit()

        # WHEN
        with patch(
            "api.services.example_project_service.ExampleProjectService.seed_for",
            autospec=True,
            side_effect=poison_the_session,
        ):
            response = client.post(
                "/api/v1/auth/verify-email",
                json={"token": token, "password": password},
            )
        user = session.exec(select(User).where(User.email == _PENDING_EMAIL)).first()
        assert user is not None, "the pending account itself must still exist"
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": _PENDING_EMAIL, "password": password},
        )

        # THEN
        assert response.status_code == 200
        assert user.email_verified_at is not None
        assert login_response.status_code == 200

    def test_activation_succeeds_when_recalculation_raises(self, client, session, pending_account):
        """A crash after seed_for's own commit leaves a self-healing partial write.

        recalculate runs once the project, its memberships, and all 13 opinions are
        already committed, so this is a different failure shape than one inside
        seed_for itself: the project is real and usable, only its cached result is
        missing. GET /projects/{id}/result already serves None for that state, and
        POST /opinions recalculates unconditionally, so the owner's own first opinion
        repairs it without anyone having to notice.
        """
        # GIVEN
        token, password = pending_account

        # WHEN
        with patch(
            "api.services.calculation_service.CalculationService.recalculate",
            side_effect=RuntimeError("recalculation is broken"),
        ):
            response = client.post(
                "/api/v1/auth/verify-email",
                json={"token": token, "password": password},
            )
        user = session.exec(select(User).where(User.email == _PENDING_EMAIL)).first()
        assert user is not None, "the pending account itself must still exist"
        project = session.exec(select(Project).where(col(Project.is_example).is_(True))).first()
        assert project is not None, "the project must survive a post-commit failure"
        opinions = session.exec(
            select(ExpertOpinion).where(ExpertOpinion.project_id == project.id)
        ).all()
        results = session.exec(
            select(CalculationResult).where(CalculationResult.project_id == project.id)
        ).all()

        # THEN
        assert response.status_code == 200
        assert user.email_verified_at is not None
        assert len(opinions) == 13
        assert results == []
