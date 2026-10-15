"""LangSmith tracing for the assistant agent, opt-in through one setting.

When tracing is on, the text of questions, history, tool replies and answers goes to the
configured LangSmith endpoint, but not the names and positions of the turn's participants.
Those are the experts of every opinions list the turn fetched or read in a block, and they are
replaced with ``Expert 1``, ``Expert 2`` and ``[position of Expert 1]`` before anything leaves
the process (see :class:`~api.assistant.agent.masking.TurnRoster`). Every run of the turn is
masked with the roster as it stands when the turn ends. ``assistant_langsmith_enabled`` is the
only switch, in every environment, and a deployed service may use only the EU endpoint
(Settings refuses the rest). With it off, which is the default, nothing is traced and
nothing leaves the machine, whatever the LangSmith library's own environment variables say.

A turn is one trace: :func:`start_turn` opens a root run in ``prepare``, and the scope of
each phase (prepare, then generation) hangs its runs under it until :func:`end_turn`.

The participants are known only once the turn has fetched their opinions, which in agent
mode happens after the question and the first model call have started. So the shared client
holds every run of a turn in memory and, when the turn ends, reads the opinions blocks of all
of them into the roster, then masks and sends the runs in order. That work runs on a worker
thread of the client, not on the event loop. Two layers apply: the roster mask, then the
opinions-block mask by shape (see :func:`~api.assistant.agent.tools.mask_opinion_names`),
which also runs in the client's anonymizer. A call that cannot be tied to a turn, or that
cannot be masked, is dropped and never sent as it is. What this costs and leaves open:

- A trace appears in LangSmith only after the turn ends. A process that dies mid-turn loses
  that trace, and so does :func:`shutdown_tracing` for a turn still running.
- A name is found in its Czech cases and without diacritics. A typo, a diminutive and a form
  that changes the stem (Kupka, Kupce) are not found.
- A name in the history that belongs to a project this turn did not fetch is not found,
  unless it sits in an opinions block, which the shape mask handles.
- A run that ends after its turn, such as one cut off by a disconnecting client, is masked
  with the roster the turn had at its end, while the turn is among the last 256 released.
  Past that its calls are dropped.
- Streamed token events carry no text: the library drops it before sending. The events are
  masked as well.
"""

import contextlib
import functools
import json
import logging
import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import langsmith as ls
from langsmith.anonymizer import CallableNodeProcessor, create_anonymizer
from langsmith.run_trees import RunTree

from api.assistant.agent.masking import TurnRoster, mask_participants
from api.assistant.agent.tools import mask_opinion_names, mask_opinion_rows
from api.config import Settings

logger = logging.getLogger(__name__)

# The longest the application waits for pending traces to reach LangSmith on shutdown.
_FLUSH_TIMEOUT_SECONDS = 10.0

# How deep the anonymizer looks for strings in a run's inputs, outputs and metadata. The
# library's default is 10 and it skips anything deeper without a word, which would leave a
# name in a deeply nested state untouched.
_MASK_MAX_DEPTH = 50

# Turns held at once, and turns remembered after they ended. A turn is held until its end,
# which every code path reaches; the bound is for the one that does not, a stream that was
# never read. The oldest turn past the bound is dropped unsent and its later runs are masked
# and sent.
_MAX_HELD_TRACES = 256
_MAX_RELEASED_TRACES = 256

# The parts of a run that carry text. The library drops the text of streamed tokens itself.
# ``serialized`` is the configuration of a model, and may repeat what it was given. The
# assistant attaches nothing; an attachment that did appear would be read as text.
_MASKED_FIELDS = (
    *("name", "inputs", "outputs", "error", "extra"),
    *("events", "tags", "serialized", "attachments"),
)

# The one client of the process. It batches traces on a background thread, so building
# one per turn would start a thread per turn and lose the batching.
_client: "MaskingClient | None" = None


@dataclass
class _Op:
    """One call the client was asked to make.

    :ivar kind: ``create`` for ``create_run``, ``update`` for ``update_run``.
    :ivar kwargs: The call's arguments, all by keyword.
    """

    kind: str
    kwargs: dict[str, Any]


@dataclass
class _Held:
    """The calls of a turn that has not ended.

    :ivar roster: The turn's participants, still filling.
    :ivar ops: The calls, in the order they were made.
    """

    roster: TurnRoster
    ops: list[_Op] = field(default_factory=list)


def _trace_key(trace_id: Any) -> str | None:
    """Write a trace id in the one form the client keys its maps by.

    :param trace_id: A UUID, or text that spells one in any case.
    :return: The lower-case hyphenated form, or None when it is not a UUID.
    """
    try:
        return str(uuid.UUID(str(trace_id)))
    except ValueError:
        return None


@functools.cache
def _warn_no_trace_id() -> None:
    """Log, once per process, that a call arrived with no trace id."""
    logger.warning(
        "LangSmith call without a trace id dropped; the others are logged at DEBUG",
        extra={"event": "assistant_trace_no_trace_id", "reason": "no_trace_id"},
    )


def _plain(value: Any) -> Any:
    """Turn an object a run holds into JSON data.

    Dates are written in ISO form, messages are dumped, anything else is written with ``str``.
    """
    if isinstance(value, date):
        return value.isoformat()
    dump = getattr(value, "model_dump", None)
    return dump(mode="json") if callable(dump) else str(value)


def _mask_text(text: str, roster: TurnRoster) -> str:
    """Hide the participants in one string, in an order that keeps opinions blocks readable.

    The rows of opinions blocks are masked by shape first, a known expert keeping the roster's
    label and any other taking the next free one and joining the roster, and only then are
    names and positions replaced wherever else they stand. A participant whose name is a word
    of the block's layout, such as ``lower``, would otherwise break the layout before the
    shape mask could read it.

    :param text: Any string of a run.
    :param roster: The turn's participants.
    :return: The masked string.
    """
    return mask_participants(mask_opinion_rows(text, roster), roster)


def _map_strings(value: Any, change: Callable[[str], str]) -> Any:
    """Apply a function to every string of a value, whatever it is nested in.

    The value is first turned into plain JSON data, so that a message object in a run's
    outputs is read as text too.

    :param value: A part of a run.
    :param change: What to do with a string.
    :return: A copy with each string replaced by the function's result.
    """
    anonymizer = create_anonymizer(CallableNodeProcessor(change), max_depth=_MASK_MAX_DEPTH)
    return anonymizer(json.loads(json.dumps(value, default=_plain)))


def _note_experts(text: str, roster: TurnRoster) -> str:
    """Add the experts of the opinions blocks in a string to the roster; change nothing."""
    mask_opinion_rows(text, roster)
    return text


def _read_blocks(op: _Op, roster: TurnRoster) -> None:
    """Add the experts of every opinions block in a call to the roster, and nothing else."""
    for name in _MASKED_FIELDS:
        if op.kwargs.get(name):
            _map_strings(op.kwargs[name], lambda text: _note_experts(text, roster))


def _masked(op: _Op, roster: TurnRoster) -> _Op:
    """Mask the participants in the text-bearing parts of a call.

    :param op: The call.
    :param roster: The turn's participants.
    :return: The call with those parts masked.
    """
    kwargs = dict(op.kwargs)
    for name in _MASKED_FIELDS:
        if kwargs.get(name):
            kwargs[name] = _map_strings(kwargs[name], lambda text: _mask_text(text, roster))
    return _Op(op.kind, kwargs)


class MaskingClient(ls.Client):
    """A LangSmith client that holds the runs of a turn until the turn ends, then masks them.

    A turn is registered with :meth:`hold` before its first run is made. From then on every
    ``create_run`` and ``update_run`` of that trace is copied and kept instead of sent, and
    :meth:`release` hands them, in order, to the client's single worker thread, which masks
    each with the turn's roster and sends it. A call for a trace that was released goes to the
    same worker, so it stays behind the held ones. A call that belongs to no known trace, or
    that cannot be masked, is dropped: the client never sends a call it did not mask. The calls
    come from the event loop and from executor threads, so the maps are guarded by a lock.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Build the client; the arguments are the library's."""
        super().__init__(**kwargs)
        self._hold_lock = threading.Lock()
        self._held: OrderedDict[str, _Held] = OrderedDict()
        self._released: OrderedDict[str, TurnRoster] = OrderedDict()
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="trace-release")

    def hold(self, trace_id: str, roster: TurnRoster) -> None:
        """Start keeping the runs of a trace instead of sending them.

        :param trace_id: The trace's id, as the root run has it.
        :param roster: The turn's participants; it may still fill while the trace is held.
        :raises ValueError: If the id is not a UUID.
        """
        key = uuid.UUID(str(trace_id))
        with self._hold_lock:
            self._held[str(key)] = _Held(roster)
            while len(self._held) > _MAX_HELD_TRACES:
                dropped_id, dropped = self._held.popitem(last=False)
                self._remember(dropped_id, dropped.roster)

    def release(self, trace_id: str) -> None:
        """Hand the held runs of a trace to the worker; a trace not held is left alone.

        Returns at once: the masking and the sending happen on the worker thread.

        :param trace_id: The trace's id.
        """
        key = _trace_key(trace_id)
        with self._hold_lock:
            held = self._held.pop(key, None) if key else None
            if held is None or key is None:
                return
            self._remember(key, held.roster)
            if held.roster.incomplete:
                # A name may be missing from the roster: drop the trace, do not send it.
                logger.info(
                    "LangSmith trace dropped",
                    extra={"event": "assistant_trace_dropped", "reason": "roster_incomplete"},
                )
                return
            # Under the lock, so that no late call reaches the worker before this flush.
            self._submit(self._flush, held)

    def wait_idle(self, timeout: float) -> bool:
        """Wait until every job handed to the worker so far has run.

        :param timeout: The most seconds to wait.
        :return: Whether the worker went idle in time.
        """
        fence = self._submit(lambda: None)
        if fence is None:
            return True
        done, _ = wait([fence], timeout=timeout)
        return bool(done)

    def drain(self, timeout: float) -> None:
        """Finish the jobs handed to the worker, then stop it, for shutdown.

        A job that outlasts the timeout is abandoned, and so are the jobs behind it. Held
        traces of turns that have not ended are not jobs; they are dropped.

        :param timeout: The most seconds to wait.
        """
        self.wait_idle(timeout)
        self._worker.shutdown(wait=False, cancel_futures=True)

    def _submit(self, job: Callable[..., Any], *args: Any) -> Any:
        """Give the worker a job; once it is stopped the job is dropped, never run here."""
        try:
            return self._worker.submit(job, *args)
        except RuntimeError:
            return None

    def _remember(self, trace_id: str, roster: TurnRoster) -> None:
        """Remember the roster of a trace that is no longer held; the caller holds the lock."""
        self._released[trace_id] = roster
        self._released.move_to_end(trace_id)
        while len(self._released) > _MAX_RELEASED_TRACES:
            self._released.popitem(last=False)

    def create_run(self, name: str, inputs: dict[str, Any], run_type: str, **kwargs: Any) -> None:
        """Create a run, or keep it while its trace is held."""
        self._route(_Op("create", {"name": name, "inputs": inputs, "run_type": run_type, **kwargs}))

    def update_run(self, run_id: Any, **kwargs: Any) -> None:
        """Update a run, or keep the update while its trace is held."""
        self._route(_Op("update", {"run_id": run_id, **kwargs}))

    def _route(self, op: _Op) -> None:
        """Keep a call, or hand it to the worker to be masked, or drop it.

        A call whose trace is neither held nor remembered is dropped, whatever the reason:
        it names no trace, names a malformed one, or names one of a turn long past.
        """
        key = _trace_key(op.kwargs.get("trace_id"))
        with self._hold_lock:
            held = self._held.get(key) if key else None
            roster = self._released.get(key) if key else None
            if held is not None:
                held.ops.append(_Op(op.kind, ls.utils.deepish_copy(op.kwargs)))
                return
            if roster is not None and not roster.incomplete:
                kept = _Op(op.kind, ls.utils.deepish_copy(op.kwargs))
                self._submit(self._send_late, kept, roster)
                return
        self._log_dropped(key, "unknown_trace" if roster is None else "roster_incomplete")

    @staticmethod
    def _log_dropped(key: str | None, reason: str) -> None:
        """Log a call dropped for want of a turn.

        The first call with no trace id is logged at WARNING, so that a library that stopped
        sending it cannot drop every update in silence. Every call is logged at DEBUG.
        """
        if key is None:
            _warn_no_trace_id()
        logger.debug(
            "LangSmith call dropped",
            extra={"event": "assistant_trace_dropped", "reason": reason},
        )

    def _flush(self, held: _Held) -> None:
        """Mask and send the calls of a turn that ended, in order; runs on the worker.

        The opinions blocks of all the calls are read into the roster first, so that a name
        met only in a later run is masked in an earlier one, the question in the root run
        included. A call that cannot be read here is dropped by the second pass.
        """
        for op in held.ops:
            with contextlib.suppress(Exception):
                _read_blocks(op, held.roster)
        for op in held.ops:
            self._send_masked(op, held.roster)
        held.roster.drop_matcher()

    def _send_late(self, op: _Op, roster: TurnRoster) -> None:
        """Mask and send a call that came after its turn, keeping no pattern in its roster."""
        self._send_masked(op, roster)
        roster.drop_matcher()

    def _send_masked(self, op: _Op, roster: TurnRoster) -> None:
        """Mask a call and send it. A call that cannot be masked is dropped, with a log record
        that names the exception class and nothing of the call; a refused send is logged alike.
        """
        try:
            masked = _masked(op, roster)
        except Exception as exc:
            logger.warning(
                "LangSmith call could not be masked and was dropped",
                extra={"event": "assistant_trace_mask_failed", "reason": type(exc).__name__},
            )
            return
        try:
            if masked.kind == "create":
                super().create_run(**masked.kwargs)
            else:
                super().update_run(**masked.kwargs)
        except Exception as exc:
            logger.warning(
                "LangSmith call could not be sent",
                extra={"event": "assistant_trace_send_failed", "reason": type(exc).__name__},
            )


def _new_client(**kwargs: Any) -> MaskingClient:
    """Build a client; the one place a test replaces the client class.

    :param kwargs: The library's client arguments.
    :return: The client.
    """
    return MaskingClient(**kwargs)


def _shared_client(settings: Settings) -> MaskingClient:
    """Return the process's LangSmith client, building it on first use.

    The client is built from the settings alone: the key and the endpoint are never
    taken from ``LANGSMITH_API_KEY`` or ``LANGSMITH_ENDPOINT`` in the environment, so
    the data region is a setting rather than whatever the shell happens to hold. The
    settings of a process do not change, so the client is not rebuilt when they are
    read again. The client holds the runs of a turn and masks them with the turn's roster
    (see :class:`MaskingClient`). Its anonymizer is the second layer: it masks the expert
    names of every opinions block in the inputs, outputs, metadata and errors of every run
    it sends, also a block whose newlines are escaped, as in ``repr(exc)``, which is how
    LangChain stores the error of a tool run.

    :param settings: Application settings, with tracing enabled.
    :return: The shared client.
    """
    global _client
    if _client is None:
        key = settings.assistant_langsmith_api_key
        _client = _new_client(
            api_key=key.get_secret_value() if key else None,
            api_url=settings.assistant_langsmith_endpoint,
            anonymizer=create_anonymizer(
                CallableNodeProcessor(mask_opinion_names), max_depth=_MASK_MAX_DEPTH
            ),
        )
    return _client


def shutdown_tracing() -> None:
    """Flush pending traces and drop the shared client, for application shutdown.

    Does nothing when no client was built. A later scope builds a new client. The runs of
    turns that ended and are still being masked are finished first, then the library's queue
    is flushed, each wait bounded by the flush timeout. The runs of a turn that has not ended
    are held, not pending, so they are dropped unsent.
    """
    global _client
    client, _client = _client, None
    if client is not None:
        client.drain(_FLUSH_TIMEOUT_SECONDS)
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
    the configured LangSmith endpoint, with the turn's participants hidden once the turn
    ends (see :func:`start_turn`).

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


def start_turn(settings: Settings, question: str, roster: TurnRoster) -> RunTree | None:
    """Open the root run of an assistant turn.

    The turn's runs are held by the shared client from this moment until :func:`end_turn`,
    so nothing of the turn reaches LangSmith before the roster is complete. The root run is
    queued for the shared client's background thread, so the caller does not wait for
    LangSmith.

    :param settings: Application settings.
    :param question: The user's message, the run's input.
    :param roster: The turn's participants, filled as the turn fetches opinions.
    :return: The root run, or None when tracing is off.
    """
    if not settings.assistant_langsmith_enabled:
        return None
    client = _shared_client(settings)
    run = RunTree(
        name="assistant_turn",
        run_type="chain",
        inputs={"question": question},
        project_name=settings.assistant_langsmith_project,
        ls_client=client,
    )
    client.hold(str(run.trace_id), roster)
    run.post()
    return run


def end_turn(
    run: RunTree | None, *, outputs: dict[str, str] | None = None, error: str | None = None
) -> None:
    """Close a turn's root run, once, and send the turn's trace; None is left alone.

    A run already closed is left alone, so the held trace is sent once.

    :param run: The root run from :func:`start_turn`.
    :param outputs: What the turn produced, on success.
    :param error: The name of the exception that ended the turn, on failure.
    """
    if run is None or run.end_time is not None:
        return
    run.end(outputs=outputs, error=error)
    try:
        run.patch()
    finally:
        client = run.client
        if isinstance(client, MaskingClient):
            client.release(str(run.trace_id))


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
