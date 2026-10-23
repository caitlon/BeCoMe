"""Assistant endpoints: its configuration and the chat.

This router is registered only when Settings.assistant_enabled is true (see
api.main.create_app), so a service that leaves the flag off answers 404 for the whole
/api/v1/assistant prefix. Settings._validate_assistant_deploy refuses to start a Railway
environment other than dev, test and prod with the flag on, so this module never loads there.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Coroutine
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import StreamingResponse

from api.assistant.agent.generation import raised_at
from api.assistant.deps import (
    AssistantServiceDep,
    PreparedTurnDep,
    hold_turn_slot,
    limit_per_address,
)
from api.assistant.errors import AssistantUnavailableError, AssistantUpstreamError
from api.assistant.exception_handlers import UNAVAILABLE_DETAIL
from api.assistant.sse import KEEP_ALIVE, format_event
from api.auth.dependencies import CurrentUser
from api.config import Settings, get_settings
from api.schemas.assistant import AssistantChatResponse, AssistantConfigResponse

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])
logger = logging.getLogger(__name__)

# The status for a request whose client went away before the answer: nginx's "client closed
# request". Nothing reaches the client, which is gone, so the code only has to be one that the
# request log and the metrics can tell from a success and from a server fault.
CLIENT_CLOSED_REQUEST = 499


async def _wait_for_disconnect(request: Request) -> None:
    """Return when the client has gone away.

    The body was read by the route's dependencies, so after it ``receive`` answers nothing until
    the server reports ``http.disconnect``: uvicorn waits on an event for the next message and
    the middleware stack passes that wait down (Starlette's ``BaseHTTPMiddleware`` waits on the
    server's own ``receive`` once the body is consumed). The loop skips any other message, and
    only that wait keeps it from spinning.

    :param request: The request whose client is watched.
    """
    while (await request.receive())["type"] != "http.disconnect":
        pass


async def _run_unless_disconnected[T](
    request: Request, work: Coroutine[Any, Any, T], route: str
) -> T | None:
    """Run the work, and cancel it if the client goes away first.

    Without this a request whose client has left would keep a model call, a retrieval and a
    turn slot until the turn timeout. The work runs in a task of its own, so cancelling it
    unwinds it as its own deadline does; an exception it raises is raised here. When the work
    and the disconnect arrive together, the work wins. Only a watcher that saw the disconnect
    cancels the work. One that fails (Starlette's middleware raises on a message it did not
    expect) says nothing about the client, so the failure is logged and the turn runs on without
    the watch: it still answers, as it did before there was one, instead of failing a turn that
    nobody left.

    :param request: The request whose client is watched.
    :param work: What to run.
    :param route: The route's name, for the record written when the client left.
    :return: What the work returned, or None when the client left first.
    """
    loop = asyncio.get_running_loop()
    started = loop.time()
    job = asyncio.ensure_future(work)
    watcher = asyncio.ensure_future(_wait_for_disconnect(request))
    try:
        await asyncio.wait({job, watcher}, return_when=asyncio.FIRST_COMPLETED)
        if not job.done() and (failure := watcher.exception()) is not None:
            logger.warning(
                "Assistant disconnect watch failed: %s",
                type(failure).__name__,
                extra={
                    "event": "assistant_disconnect_watch_failed",
                    "route": route,
                    "reason": type(failure).__name__,
                },
            )
            await job
        finished = job.done()
    finally:
        watcher.cancel()
        job.cancel()
        await asyncio.gather(job, watcher, return_exceptions=True)
    if finished:
        return job.result()
    logger.info(
        "Assistant client disconnected",
        extra={
            "event": "assistant_client_disconnected",
            "route": route,
            "duration_ms": round((loop.time() - started) * 1000),
        },
    )
    return None


@router.get("/config", summary="Get the assistant's active configuration")
def get_assistant_config(
    _current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AssistantConfigResponse:
    """Return which model, mode, and collection currently serve the assistant.

    The model is the one that writes chat answers, not the query-transform model.

    Reachable only when this router is registered, which happens only when
    settings.assistant_enabled is true. It needs a session, like the chat: an anonymous
    request is answered 401.

    :param _current_user: The signed-in user; the route reads nothing from it, it only
        refuses a request that has no session.
    :param settings: Application settings.
    :return: The assistant's active configuration.
    """
    return AssistantConfigResponse(
        enabled=settings.assistant_enabled,
        model=settings.assistant_answer_llm_model,
        mode=settings.assistant_mode,
        collection=settings.assistant_collection,
        answer_provider=settings.assistant_answer_provider,
        query_provider=settings.assistant_llm_provider,
        embedding_provider=settings.assistant_embedding_provider,
    )


@router.post(
    "/chat",
    summary="Ask the assistant about the method or a project",
    # Stated because the route may return a bare response (see below), which would otherwise
    # leave FastAPI no model to describe the body by.
    response_model=AssistantChatResponse,
    dependencies=[Depends(limit_per_address), Depends(hold_turn_slot)],
)
async def chat(
    request: Request,
    turn: PreparedTurnDep,
    service: AssistantServiceDep,
) -> AssistantChatResponse | Response:
    """Answer one chat turn as the signed-in user.

    The checks run in the order :func:`~api.assistant.deps.enforce_message_limit` states: the
    per-address limit (``429``), the turn slot (``503`` with ``Retry-After``), the request check
    and the retriever (``422``, ``503``), then the hourly budget, and only after it the API
    client and the model. A request refused before the budget spends no message. A reached
    global ceiling is ``503`` with ``Retry-After``, not ``429``. The service turns a dependency
    outage or a turn that outlives its deadline into ``AssistantUnavailableError``, and a
    project the caller cannot see into ``ProjectNotFoundError``; both are answered by handlers
    registered next to this router.

    A client that goes away while the turn runs cancels it, and the slot is given back.

    :param request: The incoming request, watched for its client going away.
    :param turn: The validated chat request and the context built for it, whose API client
        carries the caller's own access token.
    :param service: The assistant service for the configured mode.
    :return: The answer, its sources, the tools that ran, the grounding checks and the
        token usage of the turn; for a client that has gone away, an empty ``499`` that nobody
        receives.
    """
    answer = await _run_unless_disconnected(
        request, service.answer(turn.request, turn.context), "chat"
    )
    if answer is None:
        return Response(status_code=CLIENT_CLOSED_REQUEST)
    return answer


@router.post(
    "/chat/stream",
    summary="Ask the assistant and read the answer as it is written",
    dependencies=[Depends(limit_per_address), Depends(hold_turn_slot)],
)
async def chat_stream(
    request: Request,
    turn: PreparedTurnDep,
    service: AssistantServiceDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Answer one chat turn as a stream of server-sent events.

    Retrieval runs before the response opens, so a project the caller cannot see, a
    dependency outage before the model is called, a full turn cap, the message limit, the
    global ceiling and the per-address limit are answered as plain HTTP errors, exactly as
    ``/chat`` answers them and in the same order (see :func:`chat`). The turn slot is held
    until the stream ends. Once the stream is open the status is already 200: a failure of the
    model call is sent as an ``error`` event with the code and text the handlers would have used
    (any other exception is sent as code 500), and the stream ends. The events are ``token``
    (``{"text": ...}``) for each piece of the answer, then ``done`` with the body ``/chat``
    returns, or ``error`` (``{"code", "detail"}``).

    While the stream waits for the model, which in the ``hybrid`` and ``agent`` modes sends nothing
    until the final response, a comment block, ``: keep-alive``, is sent every
    ``assistant_stream_heartbeat_seconds`` so that a proxy in front sees bytes. A client that
    goes away during the retrieval cancels it, and one that goes away during the stream
    cancels the stream (Starlette watches for the disconnect once the response is open).

    :param request: The incoming request, watched for its client going away.
    :param turn: The validated chat request and the context built for it.
    :param service: The assistant service for the configured mode.
    :param settings: Application settings, for the keep-alive interval.
    :return: A ``text/event-stream`` response; for a client that has gone away, an empty
        ``499`` that nobody receives.
    :raises ProjectNotFoundError: If the request names a project the caller cannot see.
    :raises AssistantUpstreamError: If the project API answers something unusable while the
        project is fetched.
    :raises AssistantUnavailableError: If a dependency is down or the deadline passes before
        the model is called.
    """
    prepared = await _run_unless_disconnected(
        request, service.prepare(turn.request, turn.context), "chat_stream"
    )
    if prepared is None:
        return Response(status_code=CLIENT_CLOSED_REQUEST)

    async def produce(
        queue: asyncio.Queue[str | AssistantChatResponse | Exception | None],
    ) -> None:
        # One task runs the service's stream from first item to last. The stream holds context
        # managers across its yields, and a context variable can only be reset by the context
        # that set it, so it must not be advanced from a new task each time. A failure is queued
        # for events() to raise, which keeps the mapping to error events in one place; None
        # marks the end, whatever ended it. The queue is unbounded on purpose: it holds at most
        # one answer, and the turn deadline bounds how long that takes, so a client that reads
        # slowly no longer slows the model, as a bounded queue's backpressure would.
        try:
            # Closes the service's stream and the model's explicitly on exit, rather than
            # leaving that to the garbage collector.
            async with contextlib.aclosing(service.stream(prepared)) as items:
                async for item in items:
                    queue.put_nowait(item)
        except Exception as exc:
            queue.put_nowait(exc)
        finally:
            queue.put_nowait(None)

    async def events() -> AsyncIterator[str]:
        queue: asyncio.Queue[str | AssistantChatResponse | Exception | None] = asyncio.Queue()
        producer = asyncio.ensure_future(produce(queue))
        try:
            while True:
                try:
                    # Cancelling a wait on the queue loses no item; cancelling the stream's
                    # next step would end the stream.
                    item = await asyncio.wait_for(
                        queue.get(), settings.assistant_stream_heartbeat_seconds
                    )
                except TimeoutError:
                    yield KEEP_ALIVE
                    continue
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                if isinstance(item, AssistantChatResponse):
                    yield format_event("done", item.model_dump(mode="json"))
                else:
                    yield format_event("token", {"text": item})
        except AssistantUnavailableError:
            # The service has logged the failure already.
            code = status.HTTP_503_SERVICE_UNAVAILABLE
            yield format_event("error", {"code": code, "detail": UNAVAILABLE_DETAIL})
        except AssistantUpstreamError as exc:
            # Nothing below logs this one, so the record is written here, at the level and
            # under the event name the /chat handler uses, so error tracking sees both routes.
            logger.error(
                "assistant upstream error: %s",
                type(exc).__name__,
                extra={"event": "assistant_upstream_error", "reason": type(exc).__name__},
            )
            code = status.HTTP_503_SERVICE_UNAVAILABLE
            yield format_event("error", {"code": code, "detail": UNAVAILABLE_DETAIL})
        except Exception as exc:
            # The 200 is sent already, so a failure the service did not map still has to end
            # the stream with an event; the record names the exception type and where it was
            # raised, never its text.
            logger.error(
                "assistant stream failed: %s",
                type(exc).__name__,
                extra={
                    "event": "assistant_stream_failed",
                    "reason": type(exc).__name__,
                    "where": raised_at(exc),
                },
            )
            code = status.HTTP_500_INTERNAL_SERVER_ERROR
            yield format_event("error", {"code": code, "detail": "Internal server error"})
        finally:
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
