"""Database utility functions and constants."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone (handle SQLite naive datetimes).

    :param dt: datetime object (may be naive or aware)
    :return: timezone-aware datetime with UTC
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
