"""Tests for database infrastructure (engine, session, lifespan)."""

from contextlib import suppress
from unittest.mock import MagicMock, patch

from sqlalchemy import Engine
from sqlmodel import Session

from api.db.engine import create_db_and_tables, get_engine, warm_up_connection_pool
from api.db.session import get_session


def _dispose_and_clear_engine() -> None:
    """Dispose the cached engine and clear the lru_cache."""
    if get_engine.cache_info().currsize:
        with suppress(Exception):
            get_engine().dispose()
    get_engine.cache_clear()


class TestDatabaseEngine:
    """Tests for database engine creation."""

    @patch("api.db.engine.get_settings")
    def test_get_engine_returns_engine(self, mock_get_settings: MagicMock) -> None:
        """get_engine should return an Engine instance (lazy initialization)."""
        # GIVEN: mock settings to use in-memory SQLite
        mock_get_settings.return_value.database_url = "sqlite:///:memory:"
        mock_get_settings.return_value.debug = False
        get_engine.cache_clear()

        try:
            # WHEN
            result = get_engine()

            # THEN
            assert isinstance(result, Engine)
        finally:
            _dispose_and_clear_engine()

    @patch("api.db.engine.get_settings")
    def test_get_engine_returns_same_instance(self, mock_get_settings: MagicMock) -> None:
        """get_engine should return cached singleton instance."""
        # GIVEN: mock settings to use in-memory SQLite
        mock_get_settings.return_value.database_url = "sqlite:///:memory:"
        mock_get_settings.return_value.debug = False
        get_engine.cache_clear()

        try:
            # WHEN
            engine1 = get_engine()
            engine2 = get_engine()

            # THEN: same instance (cached)
            assert engine1 is engine2
        finally:
            _dispose_and_clear_engine()

    @patch("api.db.engine.get_settings")
    def test_get_engine_returns_sqlite_engine(self, mock_get_settings: MagicMock) -> None:
        """get_engine should return SQLite engine when configured."""
        # GIVEN: mock settings to use in-memory SQLite
        mock_get_settings.return_value.database_url = "sqlite:///:memory:"
        mock_get_settings.return_value.debug = False
        get_engine.cache_clear()

        try:
            # WHEN
            test_engine = get_engine()

            # THEN: engine URL should be SQLite
            assert "sqlite" in str(test_engine.url)
        finally:
            _dispose_and_clear_engine()


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

        try:
            # WHEN/THEN: should not raise
            create_db_and_tables()
        finally:
            _dispose_and_clear_engine()

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

        try:
            # WHEN
            create_db_and_tables()

            # THEN
            mock_create_all.assert_called_once()
        finally:
            _dispose_and_clear_engine()

    @patch("api.db.engine.get_settings")
    @patch("api.db.engine.SQLModel.metadata.create_all")
    def test_create_db_and_tables_skips_create_all_on_postgres(
        self, mock_create_all: MagicMock, mock_get_settings: MagicMock
    ) -> None:
        """create_db_and_tables should be a no-op on deployed PostgreSQL."""
        # GIVEN: deployed PostgreSQL, not a test run
        mock_get_settings.return_value.database_url = "postgresql://u:p@h:5432/db"
        mock_get_settings.return_value.debug = False
        mock_get_settings.return_value.testing = False
        get_engine.cache_clear()

        try:
            # WHEN
            create_db_and_tables()

            # THEN: create_all must not run -- migrations manage the Postgres schema
            mock_create_all.assert_not_called()
        finally:
            _dispose_and_clear_engine()

    @patch("api.db.engine.get_settings")
    @patch("api.db.engine.SQLModel.metadata.create_all")
    def test_create_db_and_tables_runs_create_all_on_test_postgres(
        self, mock_create_all: MagicMock, mock_get_settings: MagicMock
    ) -> None:
        """create_db_and_tables should call create_all on PostgreSQL under TESTING=1."""
        # GIVEN: an ephemeral PostgreSQL test database (e.g. the e2e service container)
        mock_get_settings.return_value.database_url = "postgresql://u:p@h:5432/db"
        mock_get_settings.return_value.debug = False
        mock_get_settings.return_value.testing = True
        get_engine.cache_clear()

        try:
            # WHEN
            create_db_and_tables()

            # THEN: create_all runs so the ephemeral test schema exists
            mock_create_all.assert_called_once()
        finally:
            _dispose_and_clear_engine()


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

        # GIVEN: create_db_and_tables is mocked to isolate lifespan behavior
        try:
            # WHEN: app is created and started
            app = create_app()
            with TestClient(app):
                pass

            # THEN: create_db_and_tables should have been called
            mock_create.assert_called()
        finally:
            _dispose_and_clear_engine()

    @patch("api.main.warm_up_connection_pool")
    @patch("api.main.create_db_and_tables")
    def test_lifespan_warms_up_connection_pool(
        self, mock_create: MagicMock, mock_warmup: MagicMock
    ) -> None:
        """Lifespan should warm up the connection pool on startup."""
        from fastapi.testclient import TestClient

        from api.main import create_app

        # GIVEN: create_db_and_tables and warm-up are mocked to isolate lifespan wiring
        try:
            # WHEN: app is created and started
            app = create_app()
            with TestClient(app):
                pass

            # THEN: warm-up should have run during startup
            mock_warmup.assert_called_once()
        finally:
            _dispose_and_clear_engine()


class TestEngineHardening:
    """Tests for PostgreSQL connection-pool and connect-arg hardening."""

    @patch("api.db.engine.create_engine")
    @patch("api.db.engine.get_settings")
    def test_postgres_engine_sets_pool_timeout_and_keepalives(
        self, mock_get_settings: MagicMock, mock_create_engine: MagicMock
    ) -> None:
        """PostgreSQL engines get an explicit pool_timeout and TCP keepalives."""
        # GIVEN: a deployed PostgreSQL profile
        mock_get_settings.return_value.database_url = "postgresql://u:p@h:5432/db"
        mock_get_settings.return_value.debug = False
        mock_get_settings.return_value.testing = False
        mock_get_settings.return_value.environment.value = "production"
        get_engine.cache_clear()

        try:
            # WHEN
            get_engine()

            # THEN: pool_timeout is explicit and keepalives are configured
            _, kwargs = mock_create_engine.call_args
            assert kwargs["pool_timeout"] == 10
            connect_args = kwargs["connect_args"]
            assert connect_args["keepalives"] == 1
            assert connect_args["keepalives_idle"] == 30
            assert connect_args["keepalives_interval"] == 10
            assert connect_args["keepalives_count"] == 5
        finally:
            get_engine.cache_clear()

    @patch("api.db.engine.create_engine")
    @patch("api.db.engine.get_settings")
    def test_sqlite_engine_has_no_pool_tuning(
        self, mock_get_settings: MagicMock, mock_create_engine: MagicMock
    ) -> None:
        """SQLite engines get neither pool tuning nor libpq keepalives."""
        # GIVEN: an in-memory SQLite profile
        mock_get_settings.return_value.database_url = "sqlite:///:memory:"
        mock_get_settings.return_value.debug = False
        get_engine.cache_clear()

        try:
            # WHEN
            get_engine()

            # THEN: only check_same_thread is passed, no pool_timeout
            _, kwargs = mock_create_engine.call_args
            assert "pool_timeout" not in kwargs
            assert kwargs["connect_args"] == {"check_same_thread": False}
        finally:
            get_engine.cache_clear()


class TestWarmUpConnectionPool:
    """Tests for startup connection-pool warm-up."""

    @patch("api.db.engine.get_engine")
    @patch("api.db.engine.get_settings")
    def test_warmup_skipped_for_sqlite(
        self, mock_get_settings: MagicMock, mock_get_engine: MagicMock
    ) -> None:
        """Warm-up is a no-op for SQLite (no meaningful connection latency)."""
        # GIVEN: SQLite
        mock_get_settings.return_value.database_url = "sqlite:///:memory:"
        mock_get_settings.return_value.testing = False

        # WHEN
        warm_up_connection_pool()

        # THEN: no connection is opened
        mock_get_engine.assert_not_called()

    @patch("api.db.engine.get_engine")
    @patch("api.db.engine.get_settings")
    def test_warmup_skipped_when_testing(
        self, mock_get_settings: MagicMock, mock_get_engine: MagicMock
    ) -> None:
        """Warm-up is a no-op under TESTING=1 even on PostgreSQL."""
        # GIVEN: PostgreSQL but a test run
        mock_get_settings.return_value.database_url = "postgresql://u:p@h:5432/db"
        mock_get_settings.return_value.testing = True

        # WHEN
        warm_up_connection_pool()

        # THEN
        mock_get_engine.assert_not_called()

    @patch("api.db.engine.get_engine")
    @patch("api.db.engine.get_settings")
    def test_warmup_executes_select_1_on_postgres(
        self, mock_get_settings: MagicMock, mock_get_engine: MagicMock
    ) -> None:
        """Warm-up opens a connection and runs SELECT 1 on deployed PostgreSQL."""
        # GIVEN: deployed PostgreSQL
        mock_get_settings.return_value.database_url = "postgresql://u:p@h:5432/db"
        mock_get_settings.return_value.testing = False
        connection = MagicMock()
        mock_get_engine.return_value.connect.return_value.__enter__.return_value = connection

        # WHEN
        warm_up_connection_pool()

        # THEN: a query was executed to establish the connection
        connection.execute.assert_called_once()

    @patch("api.db.engine.get_engine")
    @patch("api.db.engine.get_settings")
    def test_warmup_swallows_connection_errors(
        self, mock_get_settings: MagicMock, mock_get_engine: MagicMock
    ) -> None:
        """A failed warm-up must not raise -- startup should continue."""
        # GIVEN: connecting raises
        mock_get_settings.return_value.database_url = "postgresql://u:p@h:5432/db"
        mock_get_settings.return_value.testing = False
        mock_get_engine.return_value.connect.side_effect = OSError("boom")

        # WHEN/THEN: does not raise
        warm_up_connection_pool()
