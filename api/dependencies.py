"""FastAPI dependencies for dependency injection."""

from collections.abc import Generator

from sqlalchemy import Engine
from sqlmodel import Session

from src.calculators.become_calculator import BeCoMeCalculator


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


def get_calculator() -> BeCoMeCalculator:
    """Get BeCoMe calculator instance.

    :return: Calculator for fuzzy aggregation
    """
    return BeCoMeCalculator()
