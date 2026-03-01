#!/usr/bin/env bash
set -euo pipefail

# Local CI pipeline runner — mirrors .github/workflows/ci.yml
#
# Usage:
#   ./scripts/ci/ci-local.sh              # full pipeline: lint + test + e2e
#   ./scripts/ci/ci-local.sh lint         # linting only
#   ./scripts/ci/ci-local.sh test         # unit + integration tests (no Docker)
#   ./scripts/ci/ci-local.sh e2e          # all E2E tests (backend + Playwright, needs Docker)
#   ./scripts/ci/ci-local.sh e2e-backend  # backend E2E only (pytest + httpx, needs Docker)
#   ./scripts/ci/ci-local.sh e2e-pw       # Playwright E2E only (needs Docker)
#   ./scripts/ci/ci-local.sh fast         # lint + test (no Docker needed)
#   ./scripts/ci/ci-local.sh smoke        # post-deployment smoke test
#   ./scripts/ci/ci-local.sh sonar        # SonarCloud analysis (full project)
#   ./scripts/ci/ci-local.sh sonar src    # SonarCloud analysis (specific module)
#   ./scripts/ci/ci-local.sh mutmut       # mutation testing on src/

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

run_lint() {
  echo "=== Lint ==="
  cd "$PROJECT_ROOT"
  uv run ruff format --check .
  uv run ruff check .
  uv run mypy src/ api/
  cd "$PROJECT_ROOT/frontend" && npm run lint
  echo ""
  echo "Lint passed."
}

run_test() {
  echo "=== Tests (unit + integration) ==="
  cd "$PROJECT_ROOT"
  SECRET_KEY=test-secret-key TESTING=1 \
    uv run pytest tests/unit/ tests/integration/ \
      --cov=src --cov=api --cov-report=term-missing
  cd "$PROJECT_ROOT/frontend" && npm run test:run
  echo ""
  echo "Tests passed."
}

run_e2e() {
  echo "=== E2E ==="
  "$PROJECT_ROOT/scripts/ci/e2e-local.sh"
}

run_e2e_backend() {
  echo "=== E2E (backend only) ==="
  "$PROJECT_ROOT/scripts/ci/e2e-local.sh" backend
}

run_e2e_playwright() {
  echo "=== E2E (Playwright only) ==="
  "$PROJECT_ROOT/scripts/ci/e2e-local.sh" playwright
}

cd "$PROJECT_ROOT"

case "${1:-all}" in
  lint)        run_lint ;;
  test)        run_test ;;
  e2e)         run_e2e ;;
  e2e-backend) run_e2e_backend ;;
  e2e-pw)      run_e2e_playwright ;;
  fast)        run_lint && run_test ;;
  smoke)       "$PROJECT_ROOT/scripts/ci/smoke-test.sh" "${@:2}" ;;
  sonar)       "$PROJECT_ROOT/scripts/ci/sonar-local.sh" "${@:2}" ;;
  mutmut)      "$PROJECT_ROOT/scripts/ci/mutmut-run.sh" "${@:2}" ;;
  all)         run_lint && run_test && run_e2e ;;
  *)
    echo "Usage: $0 {lint|test|e2e|e2e-backend|e2e-pw|fast|smoke|sonar|mutmut|all}"
    exit 1
    ;;
esac
