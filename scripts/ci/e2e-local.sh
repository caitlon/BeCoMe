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

cleanup() {
  echo ""
  echo "Cleaning up..."
  if [ -n "$API_PID" ] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
    echo "  API server stopped"
  fi
  if docker ps -q -f name="$CONTAINER_NAME" 2>/dev/null | grep -q .; then
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1
    echo "  PostgreSQL container removed"
  fi
  echo "Done."
}

trap cleanup EXIT

echo "=== BeCoMe Full-Stack E2E Tests (mode: $MODE) ==="
echo ""

# 1. Start PostgreSQL
echo "[1/3] Starting PostgreSQL..."
if docker ps -q -f name="$CONTAINER_NAME" 2>/dev/null | grep -q .; then
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1
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
DATABASE_URL="postgresql://$DB_USER:$DB_PASS@localhost:$DB_PORT/$DB_NAME" \
SECRET_KEY="e2e-local-test-secret-key" \
CORS_ORIGINS='["http://localhost:8080"]' \
SUPABASE_URL="" \
SUPABASE_KEY="" \
TESTING="1" \
DEBUG="false" \
  uv run --project "$PROJECT_ROOT" uvicorn api.main:app \
    --host 0.0.0.0 --port "$API_PORT" \
    --log-level warning &
API_PID=$!

for i in $(seq 1 30); do
  if curl -sf "http://localhost:$API_PORT/api/v1/health" >/dev/null 2>&1; then
    echo "  API server ready"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "  ERROR: API server failed to start"
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

# Backend E2E (pytest + httpx)
if [ "$MODE" = "all" ] || [ "$MODE" = "backend" ]; then
  echo "--- Backend E2E (pytest + httpx) ---"
  cd "$PROJECT_ROOT"
  uv run pytest tests/e2e/ -v -m e2e || BACKEND_EXIT=$?
  echo ""
fi

# Playwright E2E (functional tests — chromium, firefox, webkit)
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

# Exit with failure if any suite failed
TOTAL_EXIT=$((BACKEND_EXIT + PLAYWRIGHT_EXIT + VISUAL_EXIT))
if [ $TOTAL_EXIT -eq 0 ]; then
  echo ""
  echo "All E2E tests passed!"
fi

exit $TOTAL_EXIT
