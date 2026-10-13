"""LangSmith tracing for the assistant agent, opt-in through one setting.

When tracing is on, the full text of questions, tool replies and answers goes to the
configured LangSmith endpoint, except that the expert names in an opinions block are
replaced with ``Expert 1``, ``Expert 2`` and so on before anything leaves the process (see
:func:`~api.assistant.agent.tools.mask_opinion_names`). ``assistant_langsmith_enabled`` is
the only switch, in every environment, and a deployed service may use only the EU endpoint
(Settings refuses the rest). With it off, which is the default, nothing is traced and
nothing leaves the machine, whatever the LangSmith library's own environment variables say.

A turn is one trace: :func:`start_turn` opens a root run in ``prepare``, and the scope of
each phase (prepare, then generation) hangs its runs under it until :func:`end_turn`.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import langsmith as ls
from langsmith.anonymizer import CallableNodeProcessor, create_anonymizer
from langsmith.run_trees import RunTree

from api.assistant.agent.tools import mask_opinion_names
from api.config import Settings

# The longest the application waits for pending traces to reach LangSmith on shutdown.
_FLUSH_TIMEOUT_SECONDS = 10.0

# How deep the anonymizer looks for strings in a run's inputs, outputs and metadata. The
# library's default is 10 and it skips anything deeper without a word, which would leave a
# name in a deeply nested state untouched.
_MASK_MAX_DEPTH = 50

# The one client of the process. It batches traces on a background thread, so building
# one per turn would start a thread per turn and lose the batching.
_client: ls.Client | None = None


def _shared_client(settings: Settings) -> ls.Client:
    """Return the process's LangSmith client, building it on first use.

    The client is built from the settings alone: the key and the endpoint are never
    taken from ``LANGSMITH_API_KEY`` or ``LANGSMITH_ENDPOINT`` in the environment, so
    the data region is a setting rather than whatever the shell happens to hold. The
    settings of a process do not change, so the client is not rebuilt when they are
    read again. The client's anonymizer masks the expert names of every opinions block in
    the inputs, outputs, metadata and errors of every run it sends. It also recognises a
    block whose newlines are escaped, as in ``repr(exc)``, which is how LangChain stores the
    error of a tool run.

    :param settings: Application settings, with tracing enabled.
    :return: The shared client.
    """
    global _client
    if _client is None:
        key = settings.assistant_langsmith_api_key
        _client = ls.Client(
            api_key=key.get_secret_value() if key else None,
            api_url=settings.assistant_langsmith_endpoint,
            anonymizer=create_anonymizer(
                CallableNodeProcessor(mask_opinion_names), max_depth=_MASK_MAX_DEPTH
            ),
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
def tracing_scope(settings: Settings, parent: RunTree | None = None) -> Iterator[None]:
    """Scope LangSmith tracing to one phase of an assistant turn, off unless enabled.

    ``assistant_langsmith_enabled`` is off by default, so a laptop with no LangSmith
    account runs the assistant with nothing traced and nothing sent over the network.
    That holds even when the process environment carries ``LANGSMITH_TRACING=true`` or
    ``LANGCHAIN_TRACING_V2=true``: with the setting off, the scope switches tracing
    off explicitly, so the setting is the only switch.

    When it is on, tracing is scoped to this one call rather than switched on
    process-wide. The full text of questions, tool replies and answers then goes to
    the configured LangSmith endpoint, with the expert names in opinion blocks replaced
    before anything leaves the process.

    :param settings: Application settings.
    :param parent: The turn's root run from :func:`start_turn`. The runs made inside the
        scope become its children; without it they form a trace of their own.
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
        parent=parent,
        enabled=True,
    ):
        yield


def start_turn(settings: Settings, question: str) -> RunTree | None:
    """Open the root run of an assistant turn.

    The run is queued for the shared client's background thread, so the caller does not
    wait for LangSmith.

    :param settings: Application settings.
    :param question: The user's message, the run's input.
    :return: The root run, or None when tracing is off.
    """
    if not settings.assistant_langsmith_enabled:
        return None
    run = RunTree(
        name="assistant_turn",
        run_type="chain",
        inputs={"question": question},
        project_name=settings.assistant_langsmith_project,
        ls_client=_shared_client(settings),
    )
    run.post()
    return run


def end_turn(
    run: RunTree | None, *, outputs: dict[str, str] | None = None, error: str | None = None
) -> None:
    """Close a turn's root run, once; a run already closed, or None, is left alone.

    :param run: The root run from :func:`start_turn`.
    :param outputs: What the turn produced, on success.
    :param error: The name of the exception that ended the turn, on failure.
    """
    if run is None or run.end_time is not None:
        return
    run.end(outputs=outputs, error=error)
    run.patch()


@contextmanager
def ending_turn(run: RunTree | None) -> Iterator[None]:
    """Close the turn's root run when the block exits, with the error if it raised.

    Cancellation and a closed generator count: a client that disconnects mid-stream ends
    the turn with ``GeneratorExit`` or ``CancelledError`` as its error. A block that
    reaches its end without calling :func:`end_turn` closes the run with no outputs.

    :param run: The root run from :func:`start_turn`, or None.
    """
    try:
        yield
    except BaseException as exc:
        end_turn(run, error=type(exc).__name__)
        raise
    finally:
        end_turn(run)
