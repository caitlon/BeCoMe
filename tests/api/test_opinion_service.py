"""Unit tests for OpinionService."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from api.db.models import ExpertOpinion, User
from api.services.opinion_service import OpinionNotFoundError, OpinionService


class TestOpinionServiceGetOpinionsForProject:
    """Tests for OpinionService.get_opinions_for_project method."""

    def test_returns_empty_list_when_no_opinions(self):
        """Returns empty list for project without opinions."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = []
        service = OpinionService(mock_session)
        project_id = uuid4()

        # WHEN
        result = service.get_opinions_for_project(project_id)

        # THEN
        assert result == []

    def test_returns_opinions_with_users(self):
        """Returns list of (opinion, user) tuples."""
        # GIVEN
        project_id = uuid4()
        user = User(
            id=uuid4(),
            email="expert@example.com",
            first_name="Test",
            password_hash="hash",
        )
        opinion = ExpertOpinion(
            id=uuid4(),
            project_id=project_id,
            user_id=user.id,
            position="Expert",
            lower_bound=20.0,
            peak=50.0,
            upper_bound=80.0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = [(opinion, user)]
        service = OpinionService(mock_session)

        # WHEN
        result = service.get_opinions_for_project(project_id)

        # THEN
        assert len(result) == 1
        assert result[0][0] == opinion
        assert result[0][1] == user


class TestOpinionServiceGetUserOpinion:
    """Tests for OpinionService.get_user_opinion method."""

    def test_returns_opinion_when_found(self):
        """Returns opinion when user has submitted one."""
        # GIVEN
        project_id = uuid4()
        user_id = uuid4()
        expected = ExpertOpinion(
            id=uuid4(),
            project_id=project_id,
            user_id=user_id,
            position="Expert",
            lower_bound=20.0,
            peak=50.0,
            upper_bound=80.0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = expected
        service = OpinionService(mock_session)

        # WHEN
        result = service.get_user_opinion(project_id, user_id)

        # THEN
        assert result == expected

    def test_returns_none_when_not_found(self):
        """Returns None when user has no opinion."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = OpinionService(mock_session)

        # WHEN
        result = service.get_user_opinion(uuid4(), uuid4())

        # THEN
        assert result is None


class TestOpinionServiceUpsertOpinion:
    """Tests for OpinionService.upsert_opinion method."""

    def test_creates_new_opinion(self):
        """Creates new opinion when user has none."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = OpinionService(mock_session)
        project_id = uuid4()
        user_id = uuid4()

        # WHEN
        opinion, is_new = service.upsert_opinion(
            project_id=project_id,
            user_id=user_id,
            position="Chairman",
            lower_bound=30.0,
            peak=60.0,
            upper_bound=90.0,
        )

        # THEN
        assert is_new is True
        assert opinion.project_id == project_id
        assert opinion.user_id == user_id
        assert opinion.position == "Chairman"
        assert opinion.lower_bound == 30.0
        assert opinion.peak == 60.0
        assert opinion.upper_bound == 90.0
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    def test_updates_existing_opinion(self):
        """Updates existing opinion when user already has one."""
        # GIVEN
        project_id = uuid4()
        user_id = uuid4()
        existing = ExpertOpinion(
            id=uuid4(),
            project_id=project_id,
            user_id=user_id,
            position="Expert",
            lower_bound=20.0,
            peak=50.0,
            upper_bound=80.0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = existing
        service = OpinionService(mock_session)

        # WHEN
        opinion, is_new = service.upsert_opinion(
            project_id=project_id,
            user_id=user_id,
            position="Senior Expert",
            lower_bound=40.0,
            peak=70.0,
            upper_bound=95.0,
        )

        # THEN
        assert is_new is False
        assert opinion.position == "Senior Expert"
        assert opinion.lower_bound == 40.0
        assert opinion.peak == 70.0
        assert opinion.upper_bound == 95.0
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


class TestOpinionServiceDeleteOpinion:
    """Tests for OpinionService.delete_opinion method."""

    def test_deletes_existing_opinion(self):
        """Deletes opinion when it exists."""
        # GIVEN
        project_id = uuid4()
        user_id = uuid4()
        existing = ExpertOpinion(
            id=uuid4(),
            project_id=project_id,
            user_id=user_id,
            position="Expert",
            lower_bound=20.0,
            peak=50.0,
            upper_bound=80.0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = existing
        service = OpinionService(mock_session)

        # WHEN
        service.delete_opinion(project_id, user_id)

        # THEN
        mock_session.delete.assert_called_once_with(existing)
        mock_session.commit.assert_called_once()

    def test_raises_when_opinion_not_found(self):
        """Raises OpinionNotFoundError when opinion doesn't exist."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        service = OpinionService(mock_session)

        # WHEN / THEN
        with pytest.raises(OpinionNotFoundError):
            service.delete_opinion(uuid4(), uuid4())


class TestOpinionServiceCountOpinions:
    """Tests for OpinionService.count_opinions method."""

    def test_returns_count(self):
        """Returns number of opinions for project."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.one.return_value = 5
        service = OpinionService(mock_session)

        # WHEN
        result = service.count_opinions(uuid4())

        # THEN
        assert result == 5

    def test_returns_zero_for_empty_project(self):
        """Returns zero when project has no opinions."""
        # GIVEN
        mock_session = MagicMock()
        mock_session.exec.return_value.one.return_value = 0
        service = OpinionService(mock_session)

        # WHEN
        result = service.count_opinions(uuid4())

        # THEN
        assert result == 0
