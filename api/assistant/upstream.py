"""The failures that mean a service the assistant depends on cannot answer right now.

The assistant reads from a model server (local by default, or a hosted provider per
role), an embedding and rerank server, the document index in PostgreSQL and the
application's own API. When any of them fails in one of the ways listed here, the chat
service answers "temporarily unavailable" and a tool tells the model the data is
unavailable, instead of reporting a fault in the question.

This module is imported only by code that loads when the assistant is enabled, and
never by ``api/assistant/errors.py``: that module loads in every deployed process,
and this one pulls in the model and database client libraries.
"""

import httpx
import openai
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from api.assistant.errors import AssistantUpstreamError
from api.assistant.rag.models import MalformedModelResponseError
from api.assistant.rag.store import CollectionUnavailableError
from api.assistant.roles import UpstreamRole, tagged_role

#: A model or embedding server that cannot be reached, answers with an error status, or
#: sends an error chunk in the middle of a stream (``openai.APIError``: it is the base of
#: the connection and status errors, and the client raises it bare for the error chunk),
#: an HTTP client failure of the same kind (``httpx``), and a database that refuses or
#: drops the connection (SQLAlchemy ``OperationalError``), or whose connection is unusable
#: (``InterfaceError``) or cannot be had from the pool in time (the pool's ``TimeoutError``),
#: and the builtin ``ConnectionError``, which some database drivers raise bare for a refused
#: connection, and a collection whose table is missing or unreadable
#: (``CollectionUnavailableError``, raised by ``open_store``), and a chat model server whose
#: 200 holds no completion (``MalformedModelResponseError``, raised by the chat models only).
#: ``DBAPIError`` as a whole is left out on purpose: it also holds data errors such as
#: ``IntegrityError``, which are bugs, not outages.
UNAVAILABLE_ERRORS: tuple[type[Exception], ...] = (
    openai.APIError,
    httpx.TransportError,
    httpx.HTTPStatusError,
    OperationalError,
    InterfaceError,
    PoolTimeoutError,
    ConnectionError,
    CollectionUnavailableError,
    MalformedModelResponseError,
)

_VECTOR_DB_ERRORS = (OperationalError, InterfaceError, PoolTimeoutError, CollectionUnavailableError)


def role_of(exc: BaseException, default: UpstreamRole = "unknown") -> UpstreamRole:
    """Name the server a listed failure came from, for the log record of the 503.

    The code that talks to a server writes its role on the exception (``api/assistant/roles.py``),
    and that wins. A failure nothing tagged is named by its class where the class says it: a
    database or collection error comes from the vector index, and the error the application
    client raises for an answer it cannot use comes from the application's API. The text of
    the exception is never read.

    :param exc: The failure.
    :param default: The role to give a failure that neither carries a tag nor has a class
        that names one, for a caller that knows where it caught the failure.
    :return: The role, or ``default``.
    """
    if (tagged := tagged_role(exc)) is not None:
        return tagged
    if isinstance(exc, _VECTOR_DB_ERRORS):
        return "vector_db"
    if isinstance(exc, AssistantUpstreamError):
        return "app_api"
    return default
