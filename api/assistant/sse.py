"""Server-sent-event framing for the streaming chat route."""

import json
from typing import Any


def format_event(name: str, payload: Any) -> str:
    """Frame one server-sent event.

    The payload is written as compact JSON on a single ``data:`` line. JSON escapes the
    newlines inside its strings, so a blank line, which is what ends an event, can only be
    the one this function appends; an answer that contains a paragraph break therefore
    cannot split its own event. Non-ASCII text is kept as written.

    :param name: The event name, such as ``token``.
    :param payload: Any JSON-serialisable value.
    :return: The event text, ending with the blank line that terminates it.
    """
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {name}\ndata: {data}\n\n"
