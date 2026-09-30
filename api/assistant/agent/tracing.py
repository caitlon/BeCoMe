"""LangSmith tracing scope for the assistant agent, opt-in and for local work.

When tracing is on, the full text of questions, tool replies and answers goes to the
configured LangSmith endpoint. It is switched on by hand, for local work, and the
endpoint defaults to the EU region. With it off, which is the default, nothing is
traced and nothing leaves the machine.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import langsmith as ls

from api.config import Settings

# The longest the application waits for pending traces to reach LangSmith on shutdown.
_FLUSH_TIMEOUT_SECONDS = 10.0

# The one client of the process. It batches traces on a background thread, so building
# one per turn would start a thread per turn and lose the batching.
_client: ls.Client | None = None


def _shared_client(settings: Settings) -> ls.Client:
    """Return the process's LangSmith client, building it on first use.

    The client is built from the settings alone: the key and the endpoint are never
    taken from ``LANGSMITH_API_KEY`` or ``LANGSMITH_ENDPOINT`` in the environment, so
    the data region is a setting rather than whatever the shell happens to hold. The
    settings of a process do not change, so the client is not rebuilt when they are
    read again.

    :param settings: Application settings, with tracing enabled.
    :return: The shared client.
    """
    global _client
    if _client is None:
        _client = ls.Client(
            api_key=settings.assistant_langsmith_api_key,
            api_url=settings.assistant_langsmith_endpoint,
        )
    return _client


def shutdown_tracing() -> None:
    """Flush pending traces and drop the shared client, for application shutdown.

    Does nothing when no client was built. A later scope builds a new client.
    """
    global _client
    client, _client = _client, None
    if client is not None:
        client.cleanup(timeout=_FLUSH_TIMEOUT_SECONDS)


@contextmanager
def tracing_scope(settings: Settings) -> Iterator[None]:
    """Scope LangSmith tracing to one assistant turn, off unless enabled.

    ``assistant_langsmith_enabled`` is off by default, so a laptop with no LangSmith
    account runs the assistant with nothing traced and nothing sent over the network.
    That holds even when the process environment carries ``LANGSMITH_TRACING=true`` or
    ``LANGCHAIN_TRACING_V2=true``: with the setting off, the scope switches tracing
    off explicitly, so the setting is the only switch.

    When it is on, tracing is scoped to this one call rather than switched on
    process-wide. The full text of questions, tool replies and answers then goes to
    the configured LangSmith endpoint, so it is for local work, switched on by hand,
    against the EU endpoint by default.

    :param settings: Application settings.
    :return: A context manager that traces what runs inside it when tracing is
        enabled and suppresses tracing when it is not.
    """
    if not settings.assistant_langsmith_enabled:
        with ls.tracing_context(enabled=False):
            yield
        return
    with ls.tracing_context(
        client=_shared_client(settings),
        project_name=settings.assistant_langsmith_project,
        enabled=True,
    ):
        yield
