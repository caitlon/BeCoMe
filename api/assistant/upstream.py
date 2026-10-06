"""The failures that mean a service the assistant depends on cannot answer right now.

The assistant reads from a local model server, an embedding and rerank server, the
document index in PostgreSQL and the application's own API. When any of them fails
in one of the ways listed here, the chat service answers "temporarily unavailable"
and a tool tells the model the data is unavailable, instead of reporting a fault in
the question.

This module is imported only by code that loads when the assistant is enabled, and
never by ``api/assistant/errors.py``: that module loads in every deployed process,
and this one pulls in the model and database client libraries.
"""

import httpx
import openai
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

#: A model or embedding server that cannot be reached, answers with an error status, or
#: sends an error chunk in the middle of a stream (``openai.APIError``: it is the base of
#: the connection and status errors, and the client raises it bare for the error chunk),
#: an HTTP client failure of the same kind (``httpx``), and a database that refuses or
#: drops the connection (SQLAlchemy ``OperationalError``), or whose connection is unusable
#: (``InterfaceError``) or cannot be had from the pool in time (the pool's ``TimeoutError``),
#: and the builtin ``ConnectionError``, which some database drivers raise bare for a refused
#: connection. ``DBAPIError`` as a whole is left out on purpose: it also holds data errors
#: such as ``IntegrityError``, which are bugs, not outages.
UNAVAILABLE_ERRORS: tuple[type[Exception], ...] = (
    openai.APIError,
    httpx.TransportError,
    httpx.HTTPStatusError,
    OperationalError,
    InterfaceError,
    PoolTimeoutError,
    ConnectionError,
)
