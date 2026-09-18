"""Local assistant configuration endpoint.

This router is registered only when Settings.assistant_enabled is true (see
api.main.create_app), so every deployed profile answers 404 for the whole
/api/v1/assistant prefix. Settings._validate_assistant_local_only refuses to start
any deployed profile with the flag on in the first place, so this module never even
loads there.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from api.config import Settings, get_settings
from api.schemas.assistant import AssistantConfigResponse

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.get("/config", summary="Get the local assistant's active configuration")
def get_assistant_config(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AssistantConfigResponse:
    """Return which model, mode, and collection currently serve the assistant.

    Reachable only when this router is registered, which happens only when
    settings.assistant_enabled is true.

    :param settings: Application settings.
    :return: The assistant's active configuration.
    """
    return AssistantConfigResponse(
        enabled=settings.assistant_enabled,
        model=settings.assistant_llm_model,
        mode=settings.assistant_mode,
        collection=settings.assistant_collection,
    )
