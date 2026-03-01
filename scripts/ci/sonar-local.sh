#!/usr/bin/env bash
set -euo pipefail

# Local SonarCloud scanner — analyze the whole project or a specific module.
#
# Usage:
#   ./scripts/ci/sonar-local.sh                    # full analysis (src + api + frontend/src)
#   ./scripts/ci/sonar-local.sh src                # core Python module only
#   ./scripts/ci/sonar-local.sh api                # API only
#   ./scripts/ci/sonar-local.sh frontend/src       # frontend only
#   ./scripts/ci/sonar-local.sh src,api            # multiple modules (comma-separated)
#   ./scripts/ci/sonar-local.sh --coverage         # generate coverage reports, then analyze
#   ./scripts/ci/sonar-local.sh --coverage src     # coverage + analyze specific module
#
# Environment:
#   SONAR_TOKEN — SonarCloud token (reads from env, then .env file)

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

# --- Token resolution ---
if [ -z "${SONAR_TOKEN:-}" ] && [ -f "$PROJECT_ROOT/.env" ]; then
  SONAR_TOKEN="$(grep -E '^SONAR_TOKEN=' "$PROJECT_ROOT/.env" | cut -d= -f2- | tr -d '"' || true)"
fi

if [ -z "${SONAR_TOKEN:-}" ]; then
  echo "Error: SONAR_TOKEN is not set."
  echo "Set it via environment variable or add SONAR_TOKEN=<token> to .env"
  exit 1
fi

# --- Parse arguments ---
COVERAGE=false
SOURCES=""

for arg in "$@"; do
  case "$arg" in
    --coverage) COVERAGE=true ;;
    --help|-h)
      echo "Usage: $0 [--coverage] [sources]"
      echo ""
      echo "  sources     Comma-separated directories to analyze (default: src,api,frontend/src)"
      echo "  --coverage  Generate Python and JS coverage reports before analysis"
      echo ""
      echo "Examples:"
      echo "  $0                         # full analysis"
      echo "  $0 src                     # core module only"
      echo "  $0 api                     # API only"
      echo "  $0 src,api                 # multiple modules"
      echo "  $0 --coverage              # full analysis with fresh coverage"
      echo "  $0 --coverage api          # API analysis with fresh coverage"
      exit 0
      ;;
    *) SOURCES="$arg" ;;
  esac
done

# --- Warn about non-standard sources ---
if [ -n "$SOURCES" ]; then
  for s in $(echo "$SOURCES" | tr ',' ' '); do
    case "$s" in
      src|api|frontend/src) ;;
      *)
        echo "WARNING: '$s' is not a standard source module (src, api, frontend/src)."
        echo "This scan will overwrite the main branch analysis on SonarCloud."
        printf "Continue? [y/N] "
        read -r answer
        [ "$answer" = "y" ] || exit 1
        break
        ;;
    esac
  done
fi

# --- Generate coverage (optional) ---
if [ "$COVERAGE" = true ]; then
  echo "=== Generating Python coverage ==="
  SECRET_KEY=test-secret-key TESTING=1 \
    uv run pytest tests/unit/ tests/integration/ \
      --cov=src --cov=api --cov-report=xml
  echo ""

  echo "=== Generating JS/TS coverage ==="
  cd "$PROJECT_ROOT/frontend" && npm run test:run -- --coverage
  cd "$PROJECT_ROOT"
  echo ""
fi

# --- Build scanner arguments ---
SCANNER_ARGS=(
  "-Dsonar.token=$SONAR_TOKEN"
  "-Dsonar.host.url=https://sonarcloud.io"
)

if [ -n "$SOURCES" ]; then
  SCANNER_ARGS+=("-Dsonar.sources=$SOURCES")
  echo "=== SonarCloud analysis: $SOURCES ==="
else
  echo "=== SonarCloud analysis: full project ==="
fi

# --- Run scanner ---
npx @sonar/scan "${SCANNER_ARGS[@]}"

echo ""
echo "Analysis complete. View results at:"
echo "  https://sonarcloud.io/project/overview?id=caitlon_BeCoMe"
