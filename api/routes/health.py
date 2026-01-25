"""Health check endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel

from api.config import get_settings


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    version: str


router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Check API health status."""
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.api_version)
