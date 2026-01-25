"""Health check endpoint."""

from fastapi import APIRouter

from api.config import get_settings
from api.schemas.health import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Check API health status."""
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.api_version)
