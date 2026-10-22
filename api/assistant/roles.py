"""The server a failure came from, written on the exception at the place it is raised.

A 503 record has to say which of the servers the assistant depends on failed, and the
exception's text is the one thing it must not be read from: it can name a host or hold a
body. So the code that talks to a server writes the role on the exception object, and the
log reads it back. The module has no imports beyond the standard library, so the client,
the model factories and the log sites can all use it.
"""

from typing import Final, Literal

#: The servers a turn can name as the failing one: the model that writes answers, the one that
#: translates queries, the embedding and rerank servers, the document index and the
#: application's own API. ``unknown`` is what a log record says when nothing tagged the failure.
type UpstreamRole = Literal[
    "answer", "query", "embedding", "rerank", "vector_db", "app_api", "unknown"
]

_ATTRIBUTE: Final = "upstream_role"


def tag_role(exc: BaseException, role: UpstreamRole) -> None:
    """Write the role of the failing server on an exception, unless it already has one.

    The first tag wins: it is the one written closest to the server.

    :param exc: The exception, raised by code that talks to the server.
    :param role: The role of that server.
    """
    if tagged_role(exc) is None:
        setattr(exc, _ATTRIBUTE, role)


def tagged_role(exc: BaseException) -> UpstreamRole | None:
    """Read the role written on an exception.

    :param exc: Any exception.
    :return: The role it was tagged with, or None when nothing tagged it.
    """
    return getattr(exc, _ATTRIBUTE, None)
