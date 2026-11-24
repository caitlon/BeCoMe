"""Filter for the request data attached to error events and sampled transactions.

Only the request data listed here reaches the error tracker. Log records the SDK turns into
breadcrumbs or event extras lose their ``ip`` field, which the access, auth, CSRF and
rate-limit records carry.
"""

from typing import TYPE_CHECKING

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


def scrub_request_data(event: "Event", hint: "Hint") -> "Event":
    """Reduce the request data of an event to what the error tracker may receive.

    Used as both ``before_send`` and ``before_send_transaction``. Keeps the request headers
    named in ``ALLOWED_REQUEST_HEADERS``, drops cookies, body, environment and query string,
    removes the client address from the user, and removes the ``ip`` field from the data of log
    breadcrumbs and from the event extras. An event without a request, or with fields
    of an unexpected type, is passed through otherwise unchanged, so the filter never raises
    and never drops an event.

    :param event: The event the SDK is about to send, modified in place.
    :param hint: SDK hint for the event (unused).
    :return: The same event, with its request data reduced.
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
    return event
