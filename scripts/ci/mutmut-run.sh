#!/usr/bin/env bash
set -euo pipefail

# Run mutation testing on src/ module with mutmut.
#
# Usage:
#   ./scripts/ci/mutmut-run.sh          # full mutation run + results
#   ./scripts/ci/mutmut-run.sh results  # show results from cache
#   ./scripts/ci/mutmut-run.sh detail   # show surviving mutants by file

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

CACHE=".mutmut-cache"

show_results() {
  if [ ! -f "$CACHE" ]; then
    echo "No mutation cache found. Run './scripts/ci/mutmut-run.sh' first."
    exit 1
  fi

  echo "=== Mutation Testing Results ==="
  echo ""
  sqlite3 "$CACHE" "
    SELECT
      COALESCE(SUM(CASE WHEN status='ok_killed' THEN 1 END), 0) AS killed,
      COALESCE(SUM(CASE WHEN status='bad_survived' THEN 1 END), 0) AS survived,
      COALESCE(SUM(CASE WHEN status='bad_timeout' THEN 1 END), 0) AS timeout,
      COUNT(*) AS total
    FROM Mutant;
  " -header -column
  echo ""

  local killed survived total
  killed=$(sqlite3 "$CACHE" "SELECT COUNT(*) FROM Mutant WHERE status='ok_killed';")
  survived=$(sqlite3 "$CACHE" "SELECT COUNT(*) FROM Mutant WHERE status='bad_survived';")
  total=$((killed + survived))

  if [ "$total" -gt 0 ]; then
    echo "Mutation score: $killed / $total = $(echo "scale=1; $killed * 100 / $total" | bc)%"
  fi
}

show_detail() {
  if [ ! -f "$CACHE" ]; then
    echo "No mutation cache found. Run './scripts/ci/mutmut-run.sh' first."
    exit 1
  fi

  echo "=== Surviving Mutants by File ==="
  echo ""
  sqlite3 "$CACHE" "
    SELECT sf.filename, COUNT(*) as survived
    FROM Mutant m
    JOIN Line l ON m.line = l.id
    JOIN SourceFile sf ON l.sourcefile = sf.id
    WHERE m.status = 'bad_survived'
    GROUP BY sf.filename
    ORDER BY survived DESC;
  " -header -column
  echo ""

  echo "=== Surviving Mutant Lines ==="
  echo ""
  sqlite3 "$CACHE" "
    SELECT sf.filename || ':' || l.line_number AS location, SUBSTR(l.line, 1, 80) AS code
    FROM Mutant m
    JOIN Line l ON m.line = l.id
    JOIN SourceFile sf ON l.sourcefile = sf.id
    WHERE m.status = 'bad_survived'
    ORDER BY sf.filename, l.line_number;
  " -header -column
}

case "${1:-run}" in
  run)
    echo "=== Mutation Testing (src/) ==="
    echo "This may take several minutes..."
    echo ""
    uv run mutmut run --no-progress || true
    echo ""
    show_results
    ;;
  results)
    show_results
    ;;
  detail)
    show_detail
    ;;
  *)
    echo "Usage: $0 {run|results|detail}"
    exit 1
    ;;
esac
