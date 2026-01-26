"""Base class for API services."""

from typing import TypeVar

from sqlmodel import Session, SQLModel

T = TypeVar("T", bound=SQLModel)


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

    def _save_and_refresh(self, obj: T) -> T:
        """Save object to database and refresh from DB.

        :param obj: SQLModel instance to save
        :return: Refreshed object with updated fields from database
        """
        self._session.add(obj)
        self._session.commit()
        self._session.refresh(obj)
        return obj

    def _delete_and_commit(self, obj: SQLModel) -> None:
        """Delete object from database.

        :param obj: SQLModel instance to delete
        """
        self._session.delete(obj)
        self._session.commit()
