#!/usr/bin/env bash

# Lightweight smoke test for post-deployment verification.
# Checks API health, calculation endpoint, and frontend availability.
#
# Usage:
#   ./scripts/ci/smoke-test.sh                                        # localhost defaults
#   ./scripts/ci/smoke-test.sh http://api.example.com/api/v1          # custom API URL
#   ./scripts/ci/smoke-test.sh http://api.example.com/api/v1 http://app.example.com

API_URL="${1:-http://localhost:8000/api/v1}"
FRONTEND_URL="${2:-http://localhost:8080}"
FAILURES=0
CHECKS=0

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}PASS${NC}  $1"; }
fail() { echo -e "  ${RED}FAIL${NC}  $1"; FAILURES=$((FAILURES + 1)); }

echo "=== Smoke Test ==="
echo "  API:      $API_URL"
echo "  Frontend: $FRONTEND_URL"
echo ""

# --- Check 1: API Health ---
CHECKS=$((CHECKS + 1))
HEALTH=$(curl -sf --max-time 5 "$API_URL/health" 2>/dev/null) && \
  echo "$HEALTH" | grep -q '"ok"' && \
  pass "API health endpoint" || \
  fail "API health endpoint ($API_URL/health)"

# --- Check 2: Calculate endpoint ---
CHECKS=$((CHECKS + 1))
CALC_BODY='{"experts":[{"name":"A","lower":5.0,"peak":10.0,"upper":15.0},{"name":"B","lower":8.0,"peak":12.0,"upper":18.0}]}'
CALC=$(curl -sf --max-time 5 -X POST "$API_URL/calculate" \
  -H "Content-Type: application/json" \
  -d "$CALC_BODY" 2>/dev/null) && \
  echo "$CALC" | grep -q 'best_compromise' && \
  pass "Calculate endpoint" || \
  fail "Calculate endpoint ($API_URL/calculate)"

# --- Check 3: Frontend loads ---
CHECKS=$((CHECKS + 1))
curl -sf --max-time 10 -o /dev/null "$FRONTEND_URL" 2>/dev/null && \
  pass "Frontend loads" || \
  fail "Frontend ($FRONTEND_URL)"

# --- Results ---
echo ""
if [ "$FAILURES" -eq 0 ]; then
  echo -e "${GREEN}All $CHECKS checks passed.${NC}"
  exit 0
else
  echo -e "${RED}$FAILURES of $CHECKS checks failed.${NC}"
  exit 1
fi
