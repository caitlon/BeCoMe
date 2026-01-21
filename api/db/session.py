"""Database session management for FastAPI dependency injection.

This module provides session factory for dependency injection,
following the Dependency Inversion Principle (DIP).
"""

from collections.abc import Generator

from sqlmodel import Session

from api.db.engine import get_engine


def get_session() -> Generator[Session]:
    """Yield a database session for request handling.

    Uses lazy-loaded engine from engine module.

    :yields: SQLModel Session instance
    """
    with Session(get_engine()) as session:
        yield session
