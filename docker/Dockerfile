# BeCoMe API - Production Dockerfile
# Multi-stage build with uv package manager

# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.13 AS builder

WORKDIR /app

# Install build dependencies for psycopg2 (PostgreSQL adapter)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
# Pinned to specific digest for supply-chain security.
# To update uv:
#   1. docker pull ghcr.io/astral-sh/uv:latest
#   2. docker inspect --format='{{index .RepoDigests 0}}' ghcr.io/astral-sh/uv:latest
#   3. Replace the sha256 digest below
COPY --from=ghcr.io/astral-sh/uv@sha256:9a23023be68b2ed09750ae636228e903a54a05ea56ed03a934d00fe9fbeded4b /uv /uvx /bin/

# uv optimization settings
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency files first (better caching)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies first (without project) for better layer caching
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev --extra api

# Copy application code
COPY src/ ./src/
COPY api/ ./api/

# Install project with dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra api

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.13 AS runtime

WORKDIR /app

# Install runtime dependencies for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
# Using high UID/GID (10001) to avoid conflicts with host system users
RUN groupadd --system --gid 10001 appgroup && \
    useradd --system --gid 10001 --uid 10001 --create-home appuser

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
# Prevent runtime .pyc creation (uv precompiles via UV_COMPILE_BYTECODE=1 at build time)
ENV PYTHONDONTWRITEBYTECODE=1

# Default worker count (can be overridden via environment)
# Azure App Service: set to 1 (horizontal scaling via container instances)
# Local/self-hosted: set to 4 or more
ENV UVICORN_WORKERS=4

# Expose port
EXPOSE 8000

# Health check (start_period matches docker-compose.yml)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# Run with uvicorn (worker count configurable via UVICORN_WORKERS env var)
CMD uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}
