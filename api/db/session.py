"""Database session dependency for FastAPI."""

from collections.abc import Generator

from sqlmodel import Session

from api.db.engine import engine


def get_session() -> Generator[Session]:
    """Yield a database session for request handling.

    Usage in FastAPI endpoints:
        @app.get("/items")
        def get_items(session: Session = Depends(get_session)):
            ...
    """
    with Session(engine) as session:
        yield session
