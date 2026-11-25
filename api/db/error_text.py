"""Reduce the text of database errors to what may leave the process.

PostgreSQL's own error text can quote row values: the ``DETAIL`` line of a unique, NOT NULL or
check violation does, and the first line of a type error does (``invalid input syntax for type
uuid: "..."``). SQLAlchemy's wrapper repeats the driver's text and adds the statement. The Sentry
filter and the log formatters call the functions here so that only the exception type, the
first line of the message cut at its first quote mark, the SQLSTATE and the schema identifiers
(constraint, table and column names) are sent.
"""

import traceback
from types import TracebackType

from sqlalchemy.exc import StatementError

# The logging tuple ``(type, value, traceback)``; each member is None outside an exception.
ExcInfo = tuple[type[BaseException] | None, BaseException | None, TracebackType | None]

# ``psycopg`` also matches ``psycopg2``.
_DATABASE_MODULE_PREFIXES = ("sqlalchemy", "psycopg")

_QUOTES = "\"'"
_MASK = "***"

_CAUSE_SEPARATOR = "\nThe above exception was the direct cause of the following exception:\n\n"
_CONTEXT_SEPARATOR = "\nDuring handling of the above exception, another exception occurred:\n\n"


def is_database_module(module: object) -> bool:
    """Tell whether a module name belongs to SQLAlchemy or a PostgreSQL driver.

    :param module: A module name, as in ``type(exc).__module__``.
    :return: True for a string starting with ``sqlalchemy`` or ``psycopg``.
    """
    return isinstance(module, str) and module.startswith(_DATABASE_MODULE_PREFIXES)


def safe_message_text(text: str) -> str:
    """Keep the first line of an error message, cut at its first quote mark.

    PostgreSQL does not escape a quote mark inside a value, so a value can hold either mark or
    an odd number of them. Cutting at the first mark and dropping the rest is the only rule that
    never keeps part of a value; the SQLSTATE and schema names that
    :func:`safe_error_text` appends keep the error identifiable.

    A client-side error, such as a failed connection, has no SQLSTATE, so it keeps only the text
    before the first quote mark.

    :param text: The message of a database error.
    :return: The first line up to and including its first quote mark, followed by ``***``; the
        line unchanged when it has no quote mark.
    """
    lines = text.splitlines()
    line = lines[0] if lines else ""
    marks = [i for i in (line.find(mark) for mark in _QUOTES) if i != -1]
    if not marks:
        return line
    first = min(marks)
    return f"{line[: first + 1]}{_MASK}"


def _driver_error(exc: BaseException) -> BaseException | None:
    """Return the driver's own error: ``exc`` itself, or what SQLAlchemy wrapped."""
    if type(exc).__module__.startswith("psycopg"):
        return exc
    if isinstance(exc, StatementError):
        return exc.orig
    return None


def _identifier_suffix(exc: BaseException) -> str:
    """Describe the SQLSTATE and the schema identifiers a driver error carries.

    :param exc: Any exception.
    :return: ``" (SQLSTATE ...; constraint ...; table ...; column ...)"`` with the known parts
        only, or an empty string when the exception is no driver error or none is known.
    """
    err = _driver_error(exc)
    if err is None:
        return ""
    diag = getattr(err, "diag", None)
    parts: list[str] = []
    # ``sqlstate`` is psycopg 3, ``pgcode`` psycopg2.
    state = getattr(err, "sqlstate", None) or getattr(err, "pgcode", None)
    if isinstance(state, str) and state:
        parts.append(f"SQLSTATE {state}")
    for label, attribute in (
        ("constraint", "constraint_name"),
        ("table", "table_name"),
        ("column", "column_name"),
    ):
        name = getattr(diag, attribute, None)
        if isinstance(name, str) and name:
            parts.append(f"{label} {name}")
    return f" ({'; '.join(parts)})" if parts else ""


def safe_error_text(exc: BaseException) -> str:
    """Return the text of a database error that may leave the process.

    :param exc: A driver error, or a SQLAlchemy error wrapping one.
    :return: The first line of its message cut at the first quote mark, followed by the SQLSTATE
        and the constraint, table and column names when the driver reports them. Never raises.
    """
    try:
        text = str(exc)
    except Exception:
        text = type(exc).__name__
    try:
        return safe_message_text(text) + _identifier_suffix(exc)
    except Exception:
        return type(exc).__name__


def exception_chain(exc: BaseException) -> list[BaseException]:
    """List ``exc`` and every exception reachable from it.

    Reachable means through ``__cause__``, ``__context__`` and the members of an exception group.

    :param exc: The exception to start from.
    :return: The exceptions in depth-first order, each once.
    """
    chain: list[BaseException] = []
    seen: set[int] = set()
    pending = [exc]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        chain.append(current)
        links = [link for link in (current.__cause__, current.__context__) if link is not None]
        if isinstance(current, BaseExceptionGroup):
            links.extend(current.exceptions)
        pending.extend(reversed(links))
    return chain


def database_error_chain(exc: BaseException) -> list[BaseException]:
    """List the exceptions of a chain whose text has to be reduced.

    That is every exception whose type comes from SQLAlchemy or a PostgreSQL driver, and the
    ``orig`` of every SQLAlchemy statement error, which can be a builtin error such as the
    ``TypeError`` of a bind processor.

    :param exc: The exception to start from.
    :return: The exceptions to reduce, each once; empty when the chain holds no database error.
    """
    members: list[BaseException] = []
    seen: set[int] = set()
    for link in exception_chain(exc):
        candidates = [link] if is_database_module(type(link).__module__) else []
        if isinstance(link, StatementError) and link.orig is not None:
            candidates.append(link.orig)
        for candidate in candidates:
            if id(candidate) not in seen:
                seen.add(id(candidate))
                members.append(candidate)
    return members


def _last_line(exc: BaseException, reduced: bool) -> list[str]:
    """Return the closing line of one exception in a printed traceback."""
    if not reduced:
        return traceback.format_exception_only(exc)
    name = type(exc).__qualname__
    module = type(exc).__module__
    if module not in ("builtins", "__main__"):
        name = f"{module}.{name}"
    text = safe_error_text(exc)
    return [f"{name}: {text}\n" if text else f"{name}\n"]


def _render(
    exc: BaseException,
    tb: TracebackType | None,
    reduced: set[int],
    printed: set[int],
    parts: list[str],
) -> None:
    """Append the printed form of ``exc`` and of what it links to, root cause first.

    The members of an exception group follow the group, each as a section of its own; the standard
    library nests them in a tree instead.
    """
    printed.add(id(exc))
    if exc.__cause__ is not None:
        earlier, separator = exc.__cause__, _CAUSE_SEPARATOR
    elif exc.__context__ is not None and not exc.__suppress_context__:
        earlier, separator = exc.__context__, _CONTEXT_SEPARATOR
    else:
        earlier, separator = None, ""
    if earlier is not None and id(earlier) not in printed:
        _render(earlier, earlier.__traceback__, reduced, printed, parts)
        parts.append(separator)
    if tb is not None:
        parts.append("Traceback (most recent call last):\n")
        parts.extend(traceback.format_tb(tb))
    parts.extend(_last_line(exc, id(exc) in reduced))
    if isinstance(exc, BaseExceptionGroup):
        for number, member in enumerate(exc.exceptions, start=1):
            if id(member) not in printed:
                parts.append(f"\nSub-exception {number} of {len(exc.exceptions)}:\n\n")
                _render(member, member.__traceback__, reduced, printed, parts)


def format_exception_safely(exc_info: ExcInfo) -> str | None:
    """Format an exception chain like ``traceback`` does, reducing database error text.

    :param exc_info: The logging tuple ``(type, value, traceback)``.
    :return: The traceback text without a trailing newline, with the closing line of every
        database error reduced by :func:`safe_error_text`; None when the chain holds no
        database error, so the caller keeps its default formatting.
    """
    value = exc_info[1]
    if value is None:
        return None
    members = database_error_chain(value)
    if not members:
        return None
    parts: list[str] = []
    tb = exc_info[2] if exc_info[2] is not None else value.__traceback__
    _render(value, tb, {id(member) for member in members}, set(), parts)
    return "".join(parts).removesuffix("\n")
