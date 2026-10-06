"""Local assistant endpoints: its configuration and the chat.

This router is registered only when Settings.assistant_enabled is true (see
api.main.create_app), so every deployed profile answers 404 for the whole
/api/v1/assistant prefix. Settings._validate_assistant_local_only refuses to start
any deployed profile with the flag on in the first place, so this module never even
loads there.
"""

import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse

from api.assistant.agent.generation import raised_at
from api.assistant.deps import (
    AssistantServiceDep,
    PreparedTurnDep,
    enforce_message_limit,
)
from api.assistant.errors import AssistantUnavailableError, AssistantUpstreamError
from api.assistant.exception_handlers import UNAVAILABLE_DETAIL
from api.assistant.sse import format_event
from api.config import Settings, get_settings
from api.middleware.rate_limit import LIMIT_ASSISTANT_CHAT, limiter
from api.schemas.assistant import AssistantChatResponse, AssistantConfigResponse

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])
logger = logging.getLogger(__name__)


@router.get("/config", summary="Get the local assistant's active configuration")
def get_assistant_config(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AssistantConfigResponse:
    """Return which model, mode, and collection currently serve the assistant.

    The model is the one that writes chat answers, not the query-transform model.

    Reachable only when this router is registered, which happens only when
    settings.assistant_enabled is true.

    :param settings: Application settings.
    :return: The assistant's active configuration.
    """
    return AssistantConfigResponse(
        enabled=settings.assistant_enabled,
        model=settings.assistant_answer_llm_model,
        mode=settings.assistant_mode,
        collection=settings.assistant_collection,
    )


@router.post(
    "/chat",
    summary="Ask the assistant about the method or a project",
    dependencies=[Depends(enforce_message_limit)],
)
@limiter.limit(LIMIT_ASSISTANT_CHAT)
async def chat(
    request: Request,
    turn: PreparedTurnDep,
    service: AssistantServiceDep,
) -> AssistantChatResponse:
    """Answer one chat turn as the signed-in user.

    The message limit runs first, as a dependency of the route: it authenticates the
    caller and spends one message of their hourly budget before the API client, the
    retriever or any model is built. The service turns a dependency outage or a turn that
    outlives its deadline into ``AssistantUnavailableError``, and a project the caller
    cannot see into ``ProjectNotFoundError``; both are answered by handlers registered
    next to this router.

    :param request: The incoming request, read by the per-address rate limit.
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
    dependencies=[Depends(enforce_message_limit)],
)
@limiter.limit(LIMIT_ASSISTANT_CHAT)
async def chat_stream(
    request: Request,
    turn: PreparedTurnDep,
    service: AssistantServiceDep,
) -> StreamingResponse:
    """Answer one chat turn as a stream of server-sent events.

    Retrieval runs before the response opens, so a project the caller cannot see, a
    dependency outage before the model is called, the message limit and the per-address
    limit are answered as plain HTTP errors, exactly as ``/chat`` answers them. Once the
    stream is open the status is already 200: a failure of the model call is sent as an
    ``error`` event with the code and text the handlers would have used (any other
    exception is sent as code 500), and the stream ends. The events are ``token``
    (``{"text": ...}``) for each piece of the answer, then ``done`` with the body ``/chat``
    returns, or ``error`` (``{"code", "detail"}``).

    :param request: The incoming request, read by the per-address rate limit.
    :param turn: The validated chat request and the context built for it.
    :param service: The assistant service for the configured mode.
    :return: A ``text/event-stream`` response.
    """
    prepared = await service.prepare(turn.request, turn.context)

    async def events() -> AsyncIterator[str]:
        try:
            # Closes the service's stream and the model's explicitly on exit, rather than
            # leaving that to the garbage collector.
            async with contextlib.aclosing(service.stream(prepared)) as items:
                async for item in items:
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

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
