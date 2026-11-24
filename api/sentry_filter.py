"""Filter for the request data attached to error events and sampled transactions.

Only the request data listed here reaches the error tracker.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentry_sdk._types import Event, Hint

# Compared in lower case. Any other header can carry credentials, client addresses or tokens.
ALLOWED_REQUEST_HEADERS = frozenset({"host", "accept", "content-type", "content-length"})

# Request fields the tracker never receives: cookies, the parsed or raw body, the server
# environment (which holds the client address) and the query string.
_DROPPED_REQUEST_KEYS = ("cookies", "data", "env", "query_string")


def scrub_request_data(event: "Event", hint: "Hint") -> "Event":
    """Reduce the request data of an event to what the error tracker may receive.

    Used as both ``before_send`` and ``before_send_transaction``. Keeps the request headers
    named in ``ALLOWED_REQUEST_HEADERS``, drops cookies, body, environment and query string,
    and removes the client address from the user. An event without a request, or with fields
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
    return event
