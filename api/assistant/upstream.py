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

#: A model or embedding server that cannot be reached or answers with an error status
#: (``openai``), an HTTP client failure of the same kind (``httpx``), and a database
#: that refuses or drops the connection (SQLAlchemy ``OperationalError``), or whose
#: connection is unusable (``InterfaceError``) or cannot be had from the pool in time
#: (the pool's ``TimeoutError``). ``DBAPIError`` as a whole is left out on purpose: it
#: also holds data errors such as ``IntegrityError``, which are bugs, not outages.
UNAVAILABLE_ERRORS: tuple[type[Exception], ...] = (
    openai.APIConnectionError,
    openai.APIStatusError,
    httpx.TransportError,
    httpx.HTTPStatusError,
    OperationalError,
    InterfaceError,
    PoolTimeoutError,
)
