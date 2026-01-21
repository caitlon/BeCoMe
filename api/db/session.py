"""Database session management for FastAPI dependency injection."""

from collections.abc import Generator

from sqlalchemy import Engine
from sqlmodel import Session


def get_engine() -> Engine:
    """Get database engine instance.

    Lazy import to avoid circular dependencies.
    """
    from api.db.engine import engine

    return engine


def get_session() -> Generator[Session]:
    """Yield a database session for request handling.

    :yields: SQLModel Session instance
    """
    engine = get_engine()
    with Session(engine) as session:
        yield session
