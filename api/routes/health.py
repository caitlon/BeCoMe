"""Health check endpoint."""

from fastapi import APIRouter

from api.config import get_settings
from api.middleware.rate_limit import limiter
from api.schemas.health import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
@limiter.exempt  # type: ignore[untyped-decorator]  # slowapi's exempt is untyped
def health_check() -> HealthResponse:
    """Check API health status.

    Exempt from rate limiting so infrastructure health probes are never throttled.
    """
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.api_version)
