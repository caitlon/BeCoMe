"""Database errors built the way the engine raises them, for tests of error-text handling."""

import sys

import psycopg
import psycopg.errors
import psycopg2
import psycopg2.errors
from sqlalchemy.exc import DBAPIError, StatementError

from api.db.error_text import ExcInfo

# A value that must never reach the error tracker or a log handler.
SENTINEL = "SENTINEL-db-value-7f3a"


def unique_violation_message() -> str:
    """Return the message PostgreSQL gives a unique violation on the e-mail column."""
    return (
        'duplicate key value violates unique constraint "users_email_key"\n'
        f"DETAIL:  Key (email)=({SENTINEL}) already exists.\n"
    )


def invalid_uuid_message() -> str:
    """Return the message PostgreSQL gives for a value that is not a UUID."""
    return (
        f'invalid input syntax for type uuid: "{SENTINEL}"\n'
        f"LINE 1: SELECT CAST('{SENTINEL}' AS UUID)\n                    ^\n"
    )


def wrap(orig: BaseException, dbapi_base: type[Exception]) -> DBAPIError:
    """Wrap a driver error in SQLAlchemy's exception, as the engine does.

    :param orig: The driver's error.
    :param dbapi_base: The driver's base error class, which SQLAlchemy uses to pick the wrapper.
    :return: The SQLAlchemy error, not yet raised.
    """
    wrapped = DBAPIError.instance(
        "INSERT INTO users (email) VALUES (%(email)s)",
        {"email": SENTINEL},
        orig,
        dbapi_base,
        hide_parameters=True,
    )
    assert isinstance(wrapped, DBAPIError)
    return wrapped


def raised(wrapped: BaseException, orig: BaseException) -> ExcInfo:
    """Raise ``wrapped`` from ``orig``, as the engine does, and return ``sys.exc_info()``.

    :param wrapped: The error to raise.
    :param orig: The error it was caused by; it is raised first so that it has a traceback.
    :return: The logging tuple ``(type, value, traceback)``.
    """
    try:
        try:
            raise orig
        except BaseException as cause:
            raise wrapped from cause
    except BaseException:
        return sys.exc_info()
    raise AssertionError("unreachable")


def psycopg2_unique_violation() -> tuple[DBAPIError, BaseException]:
    """Return an ``IntegrityError`` wrapping a psycopg2 unique violation, and the driver error."""
    orig = psycopg2.errors.UniqueViolation(unique_violation_message())
    return wrap(orig, psycopg2.Error), orig


def psycopg2_invalid_uuid() -> tuple[DBAPIError, BaseException]:
    """Return a ``DataError`` wrapping a psycopg2 type error, and the driver error."""
    orig = psycopg2.errors.InvalidTextRepresentation(invalid_uuid_message())
    return wrap(orig, psycopg2.Error), orig


def psycopg3_unique_violation() -> tuple[DBAPIError, BaseException]:
    """Return an ``IntegrityError`` wrapping a psycopg 3 unique violation, and the driver error."""
    orig = psycopg.errors.UniqueViolation(unique_violation_message())
    return wrap(orig, psycopg.Error), orig


def bind_processor_error() -> tuple[StatementError, BaseException]:
    """Return a ``StatementError`` around the ``TypeError`` of a bind processor."""
    orig = TypeError(f"Not a boolean value: '{SENTINEL}'")
    wrapped = StatementError(
        f"(builtins.TypeError) {orig}", "SELECT 1", {"flag": SENTINEL}, orig, hide_parameters=True
    )
    return wrapped, orig
