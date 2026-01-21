# BeCoMe API - Production Dockerfile
# Multi-stage build with uv package manager

# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.13 AS builder

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# uv optimization settings
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency files first (better caching)
COPY pyproject.toml uv.lock ./

# Install dependencies first (without project) for better layer caching
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev --extra api

# Copy application code
COPY src/ ./src/
COPY api/ ./api/
COPY README.md ./

# Install project with dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra api

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.13 AS runtime

WORKDIR /app

# Create non-root user for security
RUN groupadd --system --gid 999 appgroup && \
    useradd --system --gid 999 --uid 999 --create-home appuser

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup api/ ./api/
COPY --chown=appuser:appgroup pyproject.toml ./

# Switch to non-root user
USER appuser

# Environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# Run with uvicorn (4 workers for production)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
