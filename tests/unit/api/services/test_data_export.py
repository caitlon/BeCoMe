"""Unit tests for DataExportService."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from api.db.models import (
    CalculationResult,
    ExpertOpinion,
    Invitation,
    MemberRole,
    Project,
    ProjectMember,
    User,
)
from api.schemas.data_export import EXPORT_FORMAT_VERSION
from api.services.data_export_service import DataExportService


@pytest.fixture
def user() -> User:
    """An account holder with a password hash that must never be exported."""
    return User(
        id=uuid4(),
        email="alice@example.com",
        hashed_password="super-secret-hash",
        first_name="Alice",
        last_name="Smith",
    )


@pytest.fixture
def project(user: User) -> Project:
    """A project owned by the account holder."""
    return Project(
        id=uuid4(),
        name="Budget 2026",
        admin_id=user.id,
        scale_min=0.0,
        scale_max=100.0,
        scale_unit="%",
    )


@pytest.fixture
def result(project: Project) -> CalculationResult:
    """A cached calculation result for the owned project."""
    return CalculationResult(
        id=uuid4(),
        project_id=project.id,
        best_compromise_lower=10.0,
        best_compromise_peak=20.0,
        best_compromise_upper=30.0,
        arithmetic_mean_lower=10.0,
        arithmetic_mean_peak=20.0,
        arithmetic_mean_upper=30.0,
        median_lower=10.0,
        median_peak=20.0,
        median_upper=30.0,
        max_error=1.5,
        num_experts=5,
    )


@pytest.fixture
def membership(user: User, project: Project) -> ProjectMember:
    """The account holder's membership in the project."""
    return ProjectMember(
        id=uuid4(),
        project_id=project.id,
        user_id=user.id,
        role=MemberRole.EXPERT,
    )


@pytest.fixture
def opinion(user: User, project: Project) -> ExpertOpinion:
    """An opinion the account holder submitted to the project."""
    return ExpertOpinion(
        id=uuid4(),
        project_id=project.id,
        user_id=user.id,
        position="Analyst",
        lower_bound=10.0,
        peak=20.0,
        upper_bound=30.0,
    )


@pytest.fixture
def inviter() -> User:
    """A different user who invited the account holder."""
    return User(
        id=uuid4(),
        email="bob@example.com",
        hashed_password="another-hash",
        first_name="Bob",
        last_name="Jones",
    )


@pytest.fixture
def invitation(user: User, project: Project, inviter: User) -> Invitation:
    """A pending invitation addressed to the account holder."""
    return Invitation(
        id=uuid4(),
        project_id=project.id,
        invitee_id=user.id,
        inviter_id=inviter.id,
    )


def _exec_returning(rows: list[object]) -> MagicMock:
    """Build a mock matching ``session.exec(...).all()`` for one query.

    :param rows: The rows the query should yield.
    :return: A mock whose ``.all()`` returns the given rows.
    """
    mock = MagicMock()
    mock.all.return_value = rows
    return mock


class TestDataExportServiceBuildExport:
    """Tests for DataExportService.build_export."""

    def test_assembles_all_sections(
        self,
        user: User,
        project: Project,
        result: CalculationResult,
        membership: ProjectMember,
        opinion: ExpertOpinion,
        invitation: Invitation,
        inviter: User,
    ):
        """Every category of user data lands in the export document."""
        # GIVEN - the four collection queries each return one row
        session = MagicMock()
        session.exec.side_effect = [
            _exec_returning([(project, result)]),
            _exec_returning([(membership, project)]),
            _exec_returning([(opinion, project)]),
            _exec_returning([(invitation, project, inviter)]),
        ]
        service = DataExportService(session)

        # WHEN
        export = service.build_export(user)

        # THEN
        assert export.export_metadata.format_version == EXPORT_FORMAT_VERSION
        assert export.profile.email == "alice@example.com"

        assert len(export.owned_projects) == 1
        assert export.owned_projects[0].name == "Budget 2026"
        assert export.owned_projects[0].result is not None
        assert export.owned_projects[0].result.num_experts == 5

        assert len(export.memberships) == 1
        assert export.memberships[0].project_name == "Budget 2026"
        assert export.memberships[0].role == "expert"

        assert len(export.opinions) == 1
        assert export.opinions[0].position == "Analyst"
        assert export.opinions[0].project_name == "Budget 2026"

        assert len(export.received_invitations) == 1
        assert export.received_invitations[0].inviter_email == "bob@example.com"

    def test_owned_project_without_result_is_none(self, user: User, project: Project):
        """A project with no cached result exports a null result, not an error."""
        # GIVEN - the outer join yields the project with a None result
        session = MagicMock()
        session.exec.side_effect = [
            _exec_returning([(project, None)]),
            _exec_returning([]),
            _exec_returning([]),
            _exec_returning([]),
        ]
        service = DataExportService(session)

        # WHEN
        export = service.build_export(user)

        # THEN
        assert export.owned_projects[0].result is None

    def test_export_never_contains_password_material(self, user: User):
        """The serialized export leaks neither the hash value nor its field name."""
        # GIVEN - a user with no related data
        session = MagicMock()
        session.exec.side_effect = [
            _exec_returning([]),
            _exec_returning([]),
            _exec_returning([]),
            _exec_returning([]),
        ]
        service = DataExportService(session)

        # WHEN
        dumped = service.build_export(user).model_dump_json()

        # THEN
        assert "super-secret-hash" not in dumped
        assert "hashed_password" not in dumped

    def test_empty_account_has_empty_collections(self, user: User):
        """A user with no projects/opinions exports empty lists, never None."""
        # GIVEN
        session = MagicMock()
        session.exec.side_effect = [
            _exec_returning([]),
            _exec_returning([]),
            _exec_returning([]),
            _exec_returning([]),
        ]
        service = DataExportService(session)

        # WHEN
        export = service.build_export(user)

        # THEN
        assert export.owned_projects == []
        assert export.memberships == []
        assert export.opinions == []
        assert export.received_invitations == []
        assert export.profile.email == user.email

    def test_logs_generation_event(self, user: User):
        """A business log records that an export was generated, tagged with its event."""
        # GIVEN
        session = MagicMock()
        session.exec.side_effect = [
            _exec_returning([]),
            _exec_returning([]),
            _exec_returning([]),
            _exec_returning([]),
        ]
        service = DataExportService(session)

        # WHEN
        with patch("api.services.data_export_service.logger") as mock_logger:
            service.build_export(user)

        # THEN
        assert mock_logger.info.call_args[1]["extra"]["event"] == "data_export_generated"
