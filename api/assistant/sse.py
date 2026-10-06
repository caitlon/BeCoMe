"""Server-sent-event framing for the streaming chat route."""

import json
from typing import Any

# Valid inside a JSON string, and parsed back to the same character.
_LINE_BREAKS = {"\u2028": "\\u2028", "\u2029": "\\u2029", "\u0085": "\\u0085"}


def format_event(name: str, payload: Any) -> str:
    """Frame one server-sent event.

    The payload is written as compact JSON on a single ``data:`` line. JSON escapes the
    newlines inside its strings, so a blank line, which is what ends an event, can only be
    the one this function appends; an answer that contains a paragraph break therefore
    cannot split its own event. U+2028, U+2029 and U+0085 are escaped as well: browsers split
    an event stream only on ``\\r`` and ``\\n``, but a client that reads it with
    ``str.splitlines``, such as httpx's ``aiter_lines``, treats those three as line breaks too.
    Other non-ASCII text is kept as written.

    :param name: The event name, such as ``token``.
    :param payload: Any JSON-serialisable value.
    :return: The event text, ending with the blank line that terminates it.
    """
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    for character, escape in _LINE_BREAKS.items():
        data = data.replace(character, escape)
    return f"event: {name}\ndata: {data}\n\n"
