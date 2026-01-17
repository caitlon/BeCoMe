"""FastAPI application entry point."""

from fastapi import FastAPI
from pydantic import BaseModel

from api.config import get_settings


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    version: str


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="BeCoMe API",
        description="Best Compromise Mean — Group Decision Making under Fuzzy Uncertainty",
        version=settings.api_version,
    )

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
    def health_check() -> HealthResponse:
        """Check API health status."""
        return HealthResponse(status="ok", version=settings.api_version)

    return app


app = create_app()
