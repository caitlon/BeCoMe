#!/usr/bin/env bash
set -euo pipefail

# Runs Playwright inside the official Playwright image, for the CI E2E jobs.
#
# The image has the browsers and their system libraries baked in, so no apt runs
# on the CI runner. `playwright install --with-deps` used to pull WebKit's
# libraries from the runner's Ubuntu mirror, and on a slow mirror that step
# stalled for tens of minutes.
#
# Only Playwright runs in the image. The API, Postgres, Python and `npm ci` stay on
# the runner: psycopg2 ships no wheels and builds from source, which needs gcc and
# libpq-dev, and the image has neither. The container shares the host network, so
# the API on localhost:8000 and the dev server it starts on localhost:8080 are
# reached exactly as they are without a container. The checkout is mounted at the
# same path, so `node_modules`, the reports and the snapshots live on the host.
#
# The image tag is the exact `@playwright/test` version from frontend/package.json,
# which keeps the browsers matched to the library, and a version bump moves both.
#
# Usage:
#   scripts/ci/playwright-image.sh pull                # docker pull the image
#   scripts/ci/playwright-image.sh run <args...>       # npx playwright <args...>

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

version="$(node -p "require('$ROOT/frontend/package.json').devDependencies['@playwright/test']")"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: @playwright/test must be pinned to an exact X.Y.Z in frontend/package.json, found '$version'." >&2
  exit 1
fi
image="mcr.microsoft.com/playwright:v${version}-noble"

case "${1:-}" in
  pull)
    docker pull "$image"
    ;;
  run)
    shift
    # A bare `-e NAME` passes the variable through only when it is set. /tmp is
    # mounted because the API log the tests read is $E2E_API_LOG under /tmp.
    exec docker run --rm --network host --ipc host \
      -e CI -e E2E_API_LOG -e SECRET_KEY -e LOG_HASH_KEY -e VITE_ASSISTANT_ENABLED \
      -v "$ROOT:$ROOT" -v /tmp:/tmp \
      -w "$ROOT/frontend" \
      "$image" npx playwright "$@"
    ;;
  *)
    echo "Usage: $0 {pull|run <playwright args...>}" >&2
    exit 2
    ;;
esac
