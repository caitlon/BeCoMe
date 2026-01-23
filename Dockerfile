# syntax=docker/dockerfile:1

# BeCoMe API - Production Dockerfile
# Multi-stage build for smaller image size

FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency resolution (pinned version for supply-chain security)
COPY --from=ghcr.io/astral-sh/uv:0.5.14 /uv /usr/local/bin/uv

# Copy dependency files and README (required for hatchling build)
COPY pyproject.toml uv.lock README.md ./

# Copy source code (needed for package installation)
COPY src/ ./src/

# Install dependencies into a virtual environment
RUN uv sync --frozen --no-dev --extra api

# Install the become package itself (so 'src' module is available)
RUN uv pip install --no-deps .

# Production stage
FROM python:3.13-slim

WORKDIR /app

# Install runtime dependencies and create non-root user with explicit UID/GID
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 appgroup \
    && useradd --system --gid 10001 --uid 10001 --create-home appuser

# Copy virtual environment from builder with correct permissions
COPY --chown=appuser:appgroup --from=builder /app/.venv /app/.venv

# Copy application code with correct permissions
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup api/ ./api/

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER appuser

# Expose port (Azure App Service uses 8000 by default)
EXPOSE 8000

# Health check for Azure App Service
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run uvicorn in single-process mode.
# Azure App Service handles horizontal scaling via multiple container instances,
# so a single worker per container is sufficient.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
