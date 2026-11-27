"""Reduce the text of database errors to what may leave the process.

PostgreSQL's own error text can quote row values: the ``DETAIL`` line of a unique, NOT NULL or
check violation does, and the first line of a type error does (``invalid input syntax for type
uuid: "..."``). SQLAlchemy's wrapper repeats the driver's text and adds the statement. The Sentry
filter and the log formatters call the functions here so that only the exception type, the
first line of the message cut at its first quote mark, the SQLSTATE and the schema identifiers
(constraint, table and column names) are sent. A failed connection also carries one fixed reason
label, because the cut leaves only "connection to server at"; its host, address, port, user and
database name never leave.
"""

import re
import traceback
from types import TracebackType

import psycopg2  # type: ignore[import-untyped]  # no stubs ship with psycopg2
from sqlalchemy.exc import StatementError

# The logging tuple ``(type, value, traceback)``; each member is None outside an exception.
ExcInfo = tuple[type[BaseException] | None, BaseException | None, TracebackType | None]

# The driver errors a failed connection can raise. psycopg 3 belongs to the ``assistant`` extra,
# so an API image built without it must still import this module.
_OPERATIONAL_ERRORS: tuple[type[BaseException], ...] = (psycopg2.OperationalError,)
_CONNECTION_TIMEOUTS: tuple[type[BaseException], ...] = ()
try:
    import psycopg
    from psycopg.errors import ConnectionTimeout
except ImportError:
    pass
else:
    _OPERATIONAL_ERRORS += (psycopg.OperationalError,)
    _CONNECTION_TIMEOUTS += (ConnectionTimeout,)

# ``psycopg`` also matches ``psycopg2``.
_DATABASE_MODULE_PREFIXES = ("sqlalchemy", "psycopg")

_QUOTES = "\"'"
_MASK = "***"

# The first line of a failed connection starts with one of these, in lower case. Anything else
# (``server closed the connection unexpectedly`` in a query) keeps the plain reduced text.
_CONNECT_FAILURE_PREFIXES = (
    "connection to server at ",
    "connection to server on socket ",
    "could not connect to server",
    "could not translate host name",
    "connection failed:",
    "connection is bad:",
    "failed to resolve host",
)

# A quoted span of the first line (host, address, user, role and database names); an unclosed
# one runs to the end of the line.
_QUOTED_SPAN = re.compile(r"\"[^\"]*\"?|'[^']*'?")


def _any_of(*phrases: str) -> re.Pattern[str]:
    return re.compile("|".join(re.escape(phrase) for phrase in phrases))


# The server messages that end with a quoted name. PostgreSQL does not escape a quote mark inside
# a name, so blanking the spans would leave ``database ""ssl"`` for a database ``a"ssl``. These
# are matched on the raw line first, with a greedy name that runs to the closing mark at the
# end of the line, so an embedded mark cannot end the name early.
_NAME_LAST_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("authentication", re.compile(r'fatal:\s+role ".*" does not exist$')),
    ("unknown_database", re.compile(r'fatal:\s+database ".*" does not exist$')),
    ("authentication", re.compile(r'password authentication failed for user ".*"$')),
    ("too_many_connections", re.compile(r'too many connections for (?:role|database) ".*"$')),
)

# The first match wins. ``authentication`` precedes ``ssl`` because a pg_hba rejection ends with
# "SSL encryption"; ``ssl`` precedes ``closed`` because of "SSL connection has been closed
# unexpectedly". Names are blanked first (:func:`_classify`), so a host ``ssl-db`` or a role
# ``timed out`` cannot pick the label.
_CONNECTION_FAILURE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "authentication",
        _any_of(
            "authentication failed",
            "no pg_hba.conf entry",
            "pg_hba.conf rejects connection",
            "fe_sendauth",
            'role "" does not exist',
        ),
    ),
    ("unknown_database", _any_of('database "" does not exist')),
    (
        "too_many_connections",
        _any_of(
            "too many clients", "too many connections", "remaining connection slots are reserved"
        ),
    ),
    (
        "unavailable",
        _any_of(
            "the database system is starting up",
            "the database system is shutting down",
            "the database system is in recovery mode",
            "the database system is not yet accepting connections",
            "the database system is not accepting connections",
            "terminating connection due to administrator command",
        ),
    ),
    ("ssl", re.compile(r"\bssl\b|certificate")),
    ("refused", _any_of("connection refused")),
    ("timeout", _any_of("timeout expired", "timed out")),
    ("dns", _any_of("could not translate host name", "failed to resolve host")),
    ("unreachable", _any_of("network is unreachable", "no route to host")),
    (
        "closed",
        _any_of(
            "server closed the connection unexpectedly",
            "connection reset by peer",
            "connection socket closed",
        ),
    ),
)

# Every value ``connection_failure_label`` can return.
CONNECTION_FAILURE_LABELS = (*(label for label, _ in _CONNECTION_FAILURE_RULES), "other")

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


def _blank_span(span: re.Match[str]) -> str:
    """Turn a closed quoted span into an empty pair of its marks and drop an unclosed one."""
    text = span.group()
    return text[0] * 2 if len(text) > 1 and text[-1] == text[0] else ""


def _classify(line: str) -> str:
    """Pick the reason label for the first line of a connect failure message."""
    for label, pattern in _NAME_LAST_RULES:
        if pattern.search(line.rstrip().lower()):
            return label
    lowered = _QUOTED_SPAN.sub(_blank_span, line).lower()
    for label, pattern in _CONNECTION_FAILURE_RULES:
        if pattern.search(lowered):
            return label
    return "other"


def connection_failure_label(exc: BaseException) -> str | None:
    """Name the reason a database connection could not be made, from a fixed set of labels.

    The message of a failed connection names the host, address, port, user and database, so only
    the label leaves the process. A server error with a SQLSTATE, and a client error that does
    not start like a connect failure (a connection dropped mid-query), get no label. Only the
    first line is read: for libpq trying several addresses that is the first attempt, for
    psycopg 3's multi-attempt text the last one.

    :param exc: A driver error, or a SQLAlchemy error wrapping one.
    :return: One of :data:`CONNECTION_FAILURE_LABELS`, or None when ``exc`` is no connect
        failure. Never raises.
    """
    try:
        err = _driver_error(exc)
        if not isinstance(err, _OPERATIONAL_ERRORS):
            return None
        if getattr(err, "pgcode", None) or getattr(err, "sqlstate", None):
            return None
        lines = str(err).splitlines()
        line = lines[0] if lines else ""
        if not (
            isinstance(err, _CONNECTION_TIMEOUTS)
            or line.strip().lower().startswith(_CONNECT_FAILURE_PREFIXES)
        ):
            return None
        return _classify(line)
    except Exception:
        return None


def safe_error_text(exc: BaseException) -> str:
    """Return the text of a database error that may leave the process.

    :param exc: A driver error, or a SQLAlchemy error wrapping one.
    :return: The first line of its message cut at the first quote mark, followed by the SQLSTATE
        and the constraint, table and column names when the driver reports them, and
        ``(connection failure: <label>)`` when the connection could not be made (see
        :func:`connection_failure_label`). Never raises.
    """
    try:
        text = str(exc)
    except Exception:
        text = type(exc).__name__
    try:
        reduced = safe_message_text(text) + _identifier_suffix(exc)
        label = connection_failure_label(exc)
        return reduced if label is None else f"{reduced} (connection failure: {label})"
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
