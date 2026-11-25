"""Filter for the request data attached to error events and sampled transactions.

Only the request data listed here reaches the error tracker. Log records the SDK turns into
breadcrumbs or event extras lose their ``ip`` field, which the access, auth, CSRF and
rate-limit records carry. The text of a database error is cut to its first line at the first
quote mark, because PostgreSQL's own message can quote row values.
"""

from typing import TYPE_CHECKING

from api.db.error_text import (
    database_error_chain,
    exception_chain,
    is_database_module,
    safe_error_text,
    safe_message_text,
)

if TYPE_CHECKING:
    from sentry_sdk._types import Event, Hint

# Compared in lower case. Any other header can carry credentials, client addresses or tokens.
ALLOWED_REQUEST_HEADERS = frozenset({"host", "accept", "content-type", "content-length"})

# Request fields the tracker never receives: cookies, the parsed or raw body, the server
# environment (which holds the client address) and the query string.
_DROPPED_REQUEST_KEYS = ("cookies", "data", "env", "query_string")

# Field of a log record's ``extra`` that holds the client address. The SDK copies the
# extra fields of a log record into breadcrumb data and into the extra of an error event.
_LOG_ADDRESS_FIELD = "ip"


def _drop_log_address(fields: object) -> None:
    """Remove the client address from a mapping of log record fields, if it is one."""
    if isinstance(fields, dict):
        fields.pop(_LOG_ADDRESS_FIELD, None)


def _drop_breadcrumb_addresses(breadcrumbs: object) -> None:
    """Remove the client address from the data of every breadcrumb.

    The SDK stores breadcrumbs as ``{"values": [...]}``; a bare list is handled as well.
    Any other shape is left alone.
    """
    if isinstance(breadcrumbs, dict):
        breadcrumbs = breadcrumbs.get("values")
    if isinstance(breadcrumbs, list):
        for crumb in breadcrumbs:
            if isinstance(crumb, dict):
                _drop_log_address(crumb.get("data"))


def _exception_objects(hint: object) -> tuple[list[BaseException], set[int]]:
    """Return the exceptions behind an event and the ids of those whose text must be reduced.

    :param hint: SDK hint for the event; its ``exc_info`` names the exception.
    :return: Every exception reachable from the hint's exception, and the ids of the database
        errors among them. Both are empty when the hint carries no exception.
    """
    exc_info = hint.get("exc_info") if isinstance(hint, dict) else None
    top = exc_info[1] if isinstance(exc_info, tuple) and len(exc_info) == 3 else None
    if not isinstance(top, BaseException):
        return [], set()
    return exception_chain(top), {id(member) for member in database_error_chain(top)}


def _matches(exc: BaseException, entry: dict[str, object]) -> bool:
    """Tell whether an event's exception entry describes ``exc``."""
    kind = type(exc)
    # The SDK leaves the module out for builtin exception types.
    module = None if kind.__module__ == "builtins" else kind.__module__
    return module == entry.get("module") and entry.get("type") in (
        kind.__qualname__,
        kind.__name__,
    )


def _scrub_database_errors(event: "Event", hint: "Hint") -> None:
    """Reduce the message of every database error in an event's exception chain.

    An entry is paired with the exception it came from through the hint. A database error
    gets :func:`api.db.error_text.safe_error_text`. An entry that cannot be paired but names a
    SQLAlchemy or driver module keeps the first line of its message cut at the first quote mark.
    ``type``, ``module``, ``mechanism`` and ``stacktrace`` stay as they are. An event whose
    exception data has an unexpected shape is left alone.

    :param event: The event the SDK is about to send, modified in place.
    :param hint: SDK hint for the event.
    """
    exception = event.get("exception")
    entries = exception.get("values") if isinstance(exception, dict) else None
    if not isinstance(entries, list):
        return
    candidates, reduce = _exception_objects(hint)
    used: set[int] = set()
    # The SDK lists the root cause first; the objects are listed from the raised error down.
    for entry in reversed(entries):
        if not isinstance(entry, dict):
            continue
        match = next((c for c in candidates if id(c) not in used and _matches(c, entry)), None)
        if match is not None:
            used.add(id(match))
            if id(match) in reduce:
                entry["value"] = safe_error_text(match)
        elif is_database_module(entry.get("module")) and isinstance(entry.get("value"), str):
            entry["value"] = safe_message_text(entry["value"])


def scrub_request_data(event: "Event", hint: "Hint") -> "Event":
    """Reduce the request data of an event to what the error tracker may receive.

    Used as both ``before_send`` and ``before_send_transaction``. Keeps the request headers
    named in ``ALLOWED_REQUEST_HEADERS``, drops cookies, body, environment and query string,
    removes the client address from the user, and removes the ``ip`` field from the data of log
    breadcrumbs and from the event extras. It also reduces the text of database errors in the
    event's exception chain to the first line of the message cut at the first quote mark, plus
    the SQLSTATE and the constraint, table and column names; the ``DETAIL`` line and the SQL
    statement are dropped. An event without a request, or with fields of an unexpected type, is
    passed through otherwise unchanged, so the filter never raises and never drops an event.

    :param event: The event the SDK is about to send, modified in place.
    :param hint: SDK hint for the event; its ``exc_info`` is used to find the database errors.
    :return: The same event, with its request data and database error text reduced.
    """
    request = event.get("request")
    if isinstance(request, dict):
        for key in _DROPPED_REQUEST_KEYS:
            request.pop(key, None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                name: value
                for name, value in headers.items()
                if isinstance(name, str) and name.lower() in ALLOWED_REQUEST_HEADERS
            }
        elif headers is not None:
            # A shape this filter cannot inspect is not sent.
            del request["headers"]
    user = event.get("user")
    if isinstance(user, dict):
        user.pop("ip_address", None)
    _drop_breadcrumb_addresses(event.get("breadcrumbs"))
    _drop_log_address(event.get("extra"))
    _scrub_database_errors(event, hint)
    return event
