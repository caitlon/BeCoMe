"""Assistant endpoints: its configuration and the chat.

This router is registered only when Settings.assistant_enabled is true (see
api.main.create_app), so a service that leaves the flag off answers 404 for the whole
/api/v1/assistant prefix. Settings._validate_assistant_deploy refuses to start a Railway
environment other than dev, test and prod with the flag on, so this module never loads there.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, status
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
    dependencies=[Depends(limit_per_address), Depends(hold_turn_slot)],
)
async def chat(
    turn: PreparedTurnDep,
    service: AssistantServiceDep,
) -> AssistantChatResponse:
    """Answer one chat turn as the signed-in user.

    The checks run in the order :func:`~api.assistant.deps.enforce_message_limit` states: the
    per-address limit (``429``), the turn slot (``503`` with ``Retry-After``), the request check
    and the retriever (``422``, ``503``), then the hourly budget, and only after it the API
    client and the model. A request refused before the budget spends no message. A reached
    global ceiling is ``503`` with ``Retry-After``, not ``429``. The service turns a dependency
    outage or a turn that outlives its deadline into ``AssistantUnavailableError``, and a
    project the caller cannot see into ``ProjectNotFoundError``; both are answered by handlers
    registered next to this router.

    :param turn: The validated chat request and the context built for it, whose API client
        carries the caller's own access token.
    :param service: The assistant service for the configured mode.
    :return: The answer, its sources, the tools that ran, the grounding checks and the
        token usage of the turn.
    """
    return await service.answer(turn.request, turn.context)


@router.post(
    "/chat/stream",
    summary="Ask the assistant and read the answer as it is written",
    dependencies=[Depends(limit_per_address), Depends(hold_turn_slot)],
)
async def chat_stream(
    turn: PreparedTurnDep,
    service: AssistantServiceDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
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
    ``assistant_stream_heartbeat_seconds`` so that a proxy in front sees bytes.

    :param turn: The validated chat request and the context built for it.
    :param service: The assistant service for the configured mode.
    :param settings: Application settings, for the keep-alive interval.
    :return: A ``text/event-stream`` response.
    :raises ProjectNotFoundError: If the request names a project the caller cannot see.
    :raises AssistantUpstreamError: If the project API answers something unusable while the
        project is fetched.
    :raises AssistantUnavailableError: If a dependency is down or the deadline passes before
        the model is called.
    """
    prepared = await service.prepare(turn.request, turn.context)

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
