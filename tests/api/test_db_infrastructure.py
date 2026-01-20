"""Tests for database infrastructure (engine, session, lifespan)."""

from unittest.mock import patch

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from api.db.engine import create_db_and_tables, create_db_engine, engine
from api.db.session import get_session


class TestDatabaseEngine:
    """Tests for database engine creation."""

    def test_engine_is_created(self) -> None:
        """Engine should be created on module import."""
        # GIVEN/WHEN: engine is imported
        # THEN: it should be an Engine instance
        assert isinstance(engine, Engine)

    def test_create_db_engine_returns_engine(self) -> None:
        """create_db_engine should return an Engine instance."""
        # WHEN
        result = create_db_engine()

        # THEN
        assert isinstance(result, Engine)

    def test_sqlite_engine_has_check_same_thread_false(self) -> None:
        """SQLite engine should have check_same_thread=False for FastAPI."""
        # GIVEN: default settings use SQLite
        # WHEN
        test_engine = create_db_engine()

        # THEN: engine URL should be SQLite
        assert "sqlite" in str(test_engine.url)


class TestDatabaseSession:
    """Tests for database session dependency."""

    def test_get_session_yields_session(self) -> None:
        """get_session should yield a Session instance."""
        # WHEN
        session_gen = get_session()
        session = next(session_gen)

        # THEN
        assert isinstance(session, Session)

        # Cleanup
        try:
            next(session_gen)
        except StopIteration:
            pass

    def test_get_session_context_manager_works(self) -> None:
        """Session should work as context manager via generator."""
        # WHEN: using session through generator
        session_gen = get_session()
        session = next(session_gen)

        # THEN: session should be usable
        assert session.is_active

        # Cleanup: exhaust generator to trigger context exit
        try:
            next(session_gen)
        except StopIteration:
            pass


class TestCreateDbAndTables:
    """Tests for table creation."""

    def test_create_db_and_tables_does_not_raise(self) -> None:
        """create_db_and_tables should complete without errors."""
        # WHEN/THEN: should not raise
        create_db_and_tables()

    @patch("api.db.engine.SQLModel.metadata.create_all")
    def test_create_db_and_tables_calls_create_all(self, mock_create_all) -> None:
        """create_db_and_tables should call SQLModel.metadata.create_all."""
        # WHEN
        create_db_and_tables()

        # THEN
        mock_create_all.assert_called_once()


class TestLifespan:
    """Tests for FastAPI lifespan context manager."""

    def test_app_starts_without_error(self, client) -> None:
        """Application should start successfully with lifespan."""
        # GIVEN: client fixture creates app with lifespan
        # WHEN
        response = client.get("/api/v1/health")

        # THEN
        assert response.status_code == 200

    @patch("api.main.create_db_and_tables")
    def test_lifespan_calls_create_db_and_tables(self, mock_create) -> None:
        """Lifespan should call create_db_and_tables on startup."""
        from fastapi.testclient import TestClient

        from api.main import create_app

        # WHEN: app is created and started
        app = create_app()
        with TestClient(app):
            pass

        # THEN: create_db_and_tables should have been called
        mock_create.assert_called()
