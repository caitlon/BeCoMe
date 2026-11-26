#!/usr/bin/env bash
set -euo pipefail

# Starts the API in the background for the CI E2E jobs and waits until it answers.
#
# The caller sets the environment the API reads: DATABASE_URL, CORS_ORIGINS,
# FRONTEND_BASE_URL, DEBUG and MX_CHECK_ENABLED, plus E2E_API_LOG, the file that
# takes the server's output. The tests read the activation links from that file.
# uvicorn keeps running after this script exits, for the later steps of the job.
#
# Usage:
#   scripts/ci/start-api.sh

# The shared test environment, so the API reads no live mail provider or tracing key from a
# .env on the machine. None of the variables the caller sets above is in that list.
. "$(dirname "$0")/test-env.sh"

# PYTHONUNBUFFERED because stdout to a file is block-buffered: without it the
# activation link sits in a 8 KiB buffer and the suite times out waiting.
PYTHONUNBUFFERED=1 uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 \
  > "$E2E_API_LOG" 2>&1 &

for i in $(seq 1 30); do
  curl -sf http://localhost:8000/api/v1/health && break
  echo "Waiting for API... ($i/30)"
  sleep 2
done
curl -sf http://localhost:8000/api/v1/health || {
  echo "API failed to start"; tail -n 40 "$E2E_API_LOG"; exit 1;
}
