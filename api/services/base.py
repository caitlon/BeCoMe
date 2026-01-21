"""Base class for API services."""

from sqlmodel import Session


class BaseService:
    """Base class for database-backed services.

    Provides common session management for all services.
    Subclasses implement their own business logic methods.

    :param session: SQLModel session for database operations
    """

    def __init__(self, session: Session) -> None:
        """Initialize with database session.

        :param session: SQLModel session for database operations
        """
        self._session = session

    @property
    def session(self) -> Session:
        """Get the database session (read-only access).

        :return: SQLModel session instance
        """
        return self._session
