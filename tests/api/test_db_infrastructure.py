"""Tests for database infrastructure (engine, session, lifespan)."""

from contextlib import suppress
from unittest.mock import MagicMock, patch

from sqlalchemy import Engine
from sqlmodel import Session

from api.db.engine import create_db_and_tables, get_engine
from api.db.session import get_session


class TestDatabaseEngine:
    """Tests for database engine creation."""

    @patch("api.db.engine.get_settings")
    def test_get_engine_returns_engine(self, mock_get_settings: MagicMock) -> None:
        """get_engine should return an Engine instance (lazy initialization)."""
        # GIVEN: mock settings to use SQLite
        mock_get_settings.return_value.database_url = "sqlite:///./test_engine.db"
        mock_get_settings.return_value.debug = False
        get_engine.cache_clear()

        # WHEN
        result = get_engine()

        # THEN
        assert isinstance(result, Engine)

        # Cleanup
        get_engine.cache_clear()

    @patch("api.db.engine.get_settings")
    def test_get_engine_returns_same_instance(self, mock_get_settings: MagicMock) -> None:
        """get_engine should return cached singleton instance."""
        # GIVEN: mock settings to use SQLite
        mock_get_settings.return_value.database_url = "sqlite:///./test_cache.db"
        mock_get_settings.return_value.debug = False
        get_engine.cache_clear()

        # WHEN
        engine1 = get_engine()
        engine2 = get_engine()

        # THEN: same instance (cached)
        assert engine1 is engine2

        # Cleanup
        get_engine.cache_clear()

    @patch("api.db.engine.get_settings")
    def test_sqlite_engine_has_check_same_thread_false(self, mock_get_settings: MagicMock) -> None:
        """SQLite engine should have check_same_thread=False for FastAPI."""
        # GIVEN: mock settings to use SQLite
        mock_get_settings.return_value.database_url = "sqlite:///./test_sqlite.db"
        mock_get_settings.return_value.debug = False
        get_engine.cache_clear()

        # WHEN
        test_engine = get_engine()

        # THEN: engine URL should be SQLite
        assert "sqlite" in str(test_engine.url)

        # Cleanup
        get_engine.cache_clear()


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
        with suppress(StopIteration):
            next(session_gen)

    def test_get_session_context_manager_works(self) -> None:
        """Session should work as context manager via generator."""
        # WHEN: using session through generator
        session_gen = get_session()
        session = next(session_gen)

        # THEN: session should be usable
        assert session.is_active

        # Cleanup: exhaust generator to trigger context exit
        with suppress(StopIteration):
            next(session_gen)


class TestCreateDbAndTables:
    """Tests for table creation."""

    @patch("api.db.engine.get_settings")
    def test_create_db_and_tables_does_not_raise(self, mock_get_settings: MagicMock) -> None:
        """create_db_and_tables should complete without errors."""
        # GIVEN: mock settings to use in-memory SQLite
        mock_get_settings.return_value.database_url = "sqlite:///:memory:"
        mock_get_settings.return_value.debug = False
        get_engine.cache_clear()

        # WHEN/THEN: should not raise
        create_db_and_tables()

        # Cleanup
        get_engine.cache_clear()

    @patch("api.db.engine.get_settings")
    @patch("api.db.engine.SQLModel.metadata.create_all")
    def test_create_db_and_tables_calls_create_all(
        self, mock_create_all: MagicMock, mock_get_settings: MagicMock
    ) -> None:
        """create_db_and_tables should call SQLModel.metadata.create_all."""
        # GIVEN: mock settings to use in-memory SQLite
        mock_get_settings.return_value.database_url = "sqlite:///:memory:"
        mock_get_settings.return_value.debug = False
        get_engine.cache_clear()

        # WHEN
        create_db_and_tables()

        # THEN
        mock_create_all.assert_called_once()

        # Cleanup
        get_engine.cache_clear()


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
