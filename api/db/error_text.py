"""Reduce the text of database errors to what may leave the process.

PostgreSQL's own error text can quote row values: the ``DETAIL`` line of a unique, NOT NULL or
check violation does, and the first line of a type error does (``invalid input syntax for type
uuid: "..."``). SQLAlchemy's wrapper repeats the driver's text and adds the statement. The Sentry
filter calls the functions here so that only the exception type, the first
line of the message with quoted values masked, the SQLSTATE and the schema identifiers
(constraint, table and column names) are sent.
"""

from sqlalchemy.exc import StatementError

# ``psycopg`` also matches ``psycopg2``.
_DATABASE_MODULE_PREFIXES = ("sqlalchemy", "psycopg")

# Masked in this order. A double-quoted value can hold a single quote, never the reverse once
# the double-quoted span is masked.
_QUOTE_MARKS = ('"', "'")
_MASK = "***"


def is_database_module(module: object) -> bool:
    """Tell whether a module name belongs to SQLAlchemy or a PostgreSQL driver.

    :param module: A module name, as in ``type(exc).__module__``.
    :return: True for a string starting with ``sqlalchemy`` or ``psycopg``.
    """
    return isinstance(module, str) and module.startswith(_DATABASE_MODULE_PREFIXES)


def _mask_quoted(line: str, quote: str) -> str:
    """Mask everything from the first to the last ``quote`` of one line.

    PostgreSQL does not escape a quote mark inside a quoted value, so the value can hold the
    mark itself (``"ab"cd"``). Masking from the first mark to the last one covers it whole, at
    the price of also masking any text between two quoted spans. A lone mark means the value
    went on past the line break, so the rest of the line is masked.
    """
    first = line.find(quote)
    if first == -1:
        return line
    last = line.rfind(quote)
    if last == first:
        return f"{line[:first]}{quote}{_MASK}"
    return f"{line[:first]}{quote}{_MASK}{quote}{line[last + 1 :]}"


def safe_message_text(text: str) -> str:
    """Keep the first line of an error message and mask its quoted spans.

    :param text: The message of a database error.
    :return: The first line, with the quoted part replaced by the quote marks around ``***``.
    """
    lines = text.splitlines()
    line = lines[0] if lines else ""
    for quote in _QUOTE_MARKS:
        line = _mask_quoted(line, quote)
    return line


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
    :return: The first line of its message with quoted values masked, followed by the SQLSTATE
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


def _linked(exc: BaseException) -> list[BaseException]:
    """Return the cause and the context of an exception, when set."""
    return [link for link in (exc.__cause__, exc.__context__) if link is not None]


def exception_chain(exc: BaseException) -> list[BaseException]:
    """List ``exc`` and every exception reachable through ``__cause__`` and ``__context__``.

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
        pending.extend(reversed(_linked(current)))
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
