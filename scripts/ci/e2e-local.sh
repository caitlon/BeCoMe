#!/usr/bin/env bash
set -euo pipefail

# Full-stack E2E tests runner for local development.
# Starts PostgreSQL in Docker, runs the API, executes backend and Playwright tests, then cleans up.
#
# Usage:
#   ./scripts/ci/e2e-local.sh              # all E2E tests (backend + Playwright + visual)
#   ./scripts/ci/e2e-local.sh backend      # backend E2E only (pytest + httpx)
#   ./scripts/ci/e2e-local.sh playwright   # Playwright functional tests only
#   ./scripts/ci/e2e-local.sh visual       # Visual regression tests only (Chromium)

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CONTAINER_NAME="become-e2e-db"
DB_PORT=5433
DB_USER="become"
DB_PASS="become"
DB_NAME="become_test"
API_PORT=8000
API_PID=""
MODE="${1:-all}"

case "$MODE" in
  all|backend|playwright|visual|docs) ;;
  *)
    echo "ERROR: Invalid mode '$MODE'. Use one of: all, backend, playwright, visual, docs."
    exit 2
    ;;
esac

cleanup() {
  echo ""
  echo "Cleaning up..."
  if [ -n "$API_PID" ] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
    echo "  API server stopped"
  fi
  if docker ps -aq -f name="$CONTAINER_NAME" 2>/dev/null | grep -q .; then
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    echo "  PostgreSQL container removed"
  fi
  echo "Done."
}

trap cleanup EXIT

echo "=== BeCoMe Full-Stack E2E Tests (mode: $MODE) ==="
echo ""

# 1. Start PostgreSQL
echo "[1/3] Starting PostgreSQL..."
if docker ps -aq -f name="$CONTAINER_NAME" 2>/dev/null | grep -q .; then
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi

docker run -d --name "$CONTAINER_NAME" \
  -p "$DB_PORT":5432 \
  -e POSTGRES_USER="$DB_USER" \
  -e POSTGRES_PASSWORD="$DB_PASS" \
  -e POSTGRES_DB="$DB_NAME" \
  postgres:16-alpine >/dev/null

# Wait for PostgreSQL to be ready
for i in $(seq 1 30); do
  if docker exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" >/dev/null 2>&1; then
    echo "  PostgreSQL ready"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "  ERROR: PostgreSQL failed to start"
    exit 1
  fi
  sleep 1
done

# 2. Start API server
echo "[2/3] Starting API server..."
export APP_ENV="test"
export DATABASE_URL="postgresql://$DB_USER:$DB_PASS@localhost:$DB_PORT/$DB_NAME"
export SECRET_KEY="e2e-local-test-secret-key"
export TESTING="1"
# E2E signs up under a synthetic domain with no DNS records, so the address policy's
# resolver check is switched off for this run.
export MX_CHECK_ENABLED="false"
# Forced, never inherited: this machine's .env points at a live mail provider, and
# without this every E2E signup would attempt a real send to a made-up address. The
# console sender is also what makes the activation link readable below.
export EMAIL_PROVIDER="console"
# Activation links are built from this, so they point at the app Playwright drives.
export FRONTEND_BASE_URL="http://localhost:8080"
# The Playwright helper reads each activation link back out of the API's stdout, which
# is the only place one exists, since the flow deliberately keeps it out of the response.
# PYTHONUNBUFFERED because stdout to a file is block-buffered: without it a link can
# sit unwritten in an 8 KiB buffer for the whole run.
export E2E_API_LOG="${E2E_API_LOG:-/tmp/become-e2e-api.log}"
export PYTHONUNBUFFERED=1
: > "$E2E_API_LOG"
echo "  API log: $E2E_API_LOG"

# The documentation screenshots photograph the example project, and that project only
# seeds when the demo expert pool exists. The pool is created by a MIGRATION, while the
# test profile builds its schema with `create_all`, which makes tables and no rows. So
# this mode runs migrations first; without them the seed is skipped, the account opens
# on an empty project list, and the failure reads as a missing link rather than as a
# missing pool. Only this mode, so the other three keep the schema they were written
# against.
if [ "$MODE" = "docs" ]; then
  echo "  Running migrations (the example project's expert pool comes from one)..."
  uv run --project "$PROJECT_ROOT" alembic upgrade head >> "$E2E_API_LOG" 2>&1 || {
    echo "  ERROR: migrations failed"; tail -n 20 "$E2E_API_LOG"; exit 1;
  }
fi

CORS_ORIGINS='["http://localhost:8080"]' \
DEBUG="false" \
  uv run --project "$PROJECT_ROOT" uvicorn api.main:app \
    --host 0.0.0.0 --port "$API_PORT" \
    --log-level warning > "$E2E_API_LOG" 2>&1 &
API_PID=$!

for i in $(seq 1 30); do
  if curl -sf "http://localhost:$API_PORT/api/v1/health" >/dev/null 2>&1; then
    echo "  API server ready"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "  ERROR: API server failed to start"
    tail -n 40 "$E2E_API_LOG"
    exit 1
  fi
  sleep 2
done

# 3. Run E2E tests
echo "[3/3] Running E2E tests..."
echo ""

BACKEND_EXIT=0
PLAYWRIGHT_EXIT=0
VISUAL_EXIT=0
DOCS_EXIT=0

# Backend E2E (pytest + httpx)
if [ "$MODE" = "all" ] || [ "$MODE" = "backend" ]; then
  echo "--- Backend E2E (pytest + httpx) ---"
  cd "$PROJECT_ROOT"
  # -n 0 opts out of the shared -n logical: the workers would share one uvicorn and
  # one Postgres, and the client's 10s timeout in tests/e2e/conftest.py is exceeded.
  uv run pytest tests/e2e/ -v -m e2e -n 0 || BACKEND_EXIT=$?
  echo ""
fi

# Playwright E2E (functional tests: chromium, firefox, webkit)
if [ "$MODE" = "all" ] || [ "$MODE" = "playwright" ]; then
  echo "--- Playwright E2E ---"
  cd "$PROJECT_ROOT/frontend"
  npx playwright test --project=chromium --project=firefox --project=webkit || PLAYWRIGHT_EXIT=$?
  echo ""
fi

# Visual regression (Chromium only, requires baseline screenshots)
if [ "$MODE" = "all" ] || [ "$MODE" = "visual" ]; then
  echo "--- Visual Regression ---"
  cd "$PROJECT_ROOT/frontend"
  npx playwright test --project=visual-regression || VISUAL_EXIT=$?
  echo ""
fi

# Documentation screenshots. Never part of `all`: it writes PNGs into docs/user/img/
# rather than checking anything, so it runs only when asked for by name.
if [ "$MODE" = "docs" ]; then
  echo "--- Documentation Screenshots ---"
  cd "$PROJECT_ROOT/frontend"
  npx playwright test --project=docs-screenshots || DOCS_EXIT=$?
  echo ""
fi

# Report
echo "=== Results ==="
if [ "$MODE" = "all" ] || [ "$MODE" = "backend" ]; then
  if [ $BACKEND_EXIT -eq 0 ]; then
    echo "  Backend E2E:      PASSED"
  else
    echo "  Backend E2E:      FAILED (exit code: $BACKEND_EXIT)"
  fi
fi
if [ "$MODE" = "all" ] || [ "$MODE" = "playwright" ]; then
  if [ $PLAYWRIGHT_EXIT -eq 0 ]; then
    echo "  Playwright E2E:   PASSED"
  else
    echo "  Playwright E2E:   FAILED (exit code: $PLAYWRIGHT_EXIT)"
  fi
fi
if [ "$MODE" = "all" ] || [ "$MODE" = "visual" ]; then
  if [ $VISUAL_EXIT -eq 0 ]; then
    echo "  Visual Regression: PASSED"
  else
    echo "  Visual Regression: FAILED (exit code: $VISUAL_EXIT)"
  fi
fi
if [ "$MODE" = "docs" ]; then
  if [ $DOCS_EXIT -eq 0 ]; then
    echo "  Docs screenshots: WRITTEN"
  else
    echo "  Docs screenshots: FAILED (exit code: $DOCS_EXIT)"
  fi
fi

# Exit with failure if any suite failed
# `DOCS_EXIT` belongs in this list even though the docs mode writes files rather than
# checking anything. Left out, a failed screenshot run still printed "All E2E tests
# passed!" and exited 0, which is how a missing picture reaches a pull request.
if [ "$BACKEND_EXIT" -eq 0 ] && [ "$PLAYWRIGHT_EXIT" -eq 0 ] && [ "$VISUAL_EXIT" -eq 0 ] \
   && [ "$DOCS_EXIT" -eq 0 ]; then
  echo ""
  echo "All E2E tests passed!"
  exit 0
fi

exit 1
