"""Local assistant endpoints: its configuration and the chat.

This router is registered only when Settings.assistant_enabled is true (see
api.main.create_app), so every deployed profile answers 404 for the whole
/api/v1/assistant prefix. Settings._validate_assistant_local_only refuses to start
any deployed profile with the flag on in the first place, so this module never even
loads there.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from api.assistant.deps import (
    AssistantServiceDep,
    PreparedTurnDep,
    enforce_message_limit,
)
from api.config import Settings, get_settings
from api.middleware.rate_limit import LIMIT_ASSISTANT_CHAT, limiter
from api.schemas.assistant import AssistantChatResponse, AssistantConfigResponse

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


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
