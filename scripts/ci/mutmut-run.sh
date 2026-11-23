#!/usr/bin/env bash
set -euo pipefail

# Run mutation testing on src/ with mutmut 3.
#
# mutmut 3 keeps its state in the mutants/ directory (a mutated copy of the source
# plus per-file results), which is git-ignored. Configuration is [tool.mutmut] in
# pyproject.toml.
#
# Usage:
#   ./scripts/ci/mutmut-run.sh                 # full mutation run + summary
#   ./scripts/ci/mutmut-run.sh results         # summary from the existing mutants/ output
#   ./scripts/ci/mutmut-run.sh detail          # surviving mutants grouped by file
#   ./scripts/ci/mutmut-run.sh detail <name>   # diff of one mutant (name from "detail")

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

MUTANTS_DIR="mutants"

require_results() {
  if [ ! -d "$MUTANTS_DIR" ]; then
    echo "No mutation results found. Run './scripts/ci/mutmut-run.sh' first."
    exit 1
  fi
}

# Every mutant with its status, one "<name>: <status>" line each. This is mutmut's
# own CLI output, so the script does not depend on the layout of mutants/.
all_mutants() {
  uv run mutmut results --all true | sed 's/^ *//'
}

show_results() {
  require_results

  local mutants
  mutants="$(all_mutants)"
  if [ -z "$mutants" ]; then
    echo "No mutants recorded. Run './scripts/ci/mutmut-run.sh' first."
    exit 1
  fi

  echo "=== Mutation Testing Results ==="
  echo ""
  # The status is the text after the last ": ". The score is killed divided by the
  # mutants that were actually tried (killed, survived, timeout, suspicious,
  # segfault); "no tests", "skipped" and "caught by type check" stay out of it.
  echo "$mutants" | awk '
    BEGIN {
      n = split("killed|survived|timeout|suspicious|segfault|no tests|skipped|caught by type check|not checked|check was interrupted by user", order, "|")
    }
    {
      i = match($0, /: [^:]*$/)
      count[substr($0, i + 2)]++
      total++
    }
    END {
      for (k = 1; k <= n; k++) {
        printf "%-30s %d\n", order[k], count[order[k]] + 0
      }
      printf "%-30s %d\n", "total", total
      tried = count["killed"] + count["survived"] + count["timeout"] + count["suspicious"] + count["segfault"]
      if (tried > 0) {
        printf "\nMutation score: %d / %d = %.1f%%\n", count["killed"], tried, count["killed"] * 100 / tried
      }
    }'
}

show_detail() {
  require_results

  local survivors
  survivors="$(all_mutants | sed -n 's/: survived$//p')"
  if [ -z "$survivors" ]; then
    echo "No surviving mutants."
    return
  fi

  echo "=== Surviving Mutants by Module ==="
  echo ""
  # The module is everything before the last dot of the mutant name.
  echo "$survivors" | sed 's/\.[^.]*$//' | sort | uniq -c | sort -rn \
    | awk '{ printf "%5d  %s\n", $1, $2 }'
  echo ""

  echo "=== Surviving Mutants ==="
  echo ""
  echo "$survivors" | sort
  echo ""
  echo "Show one: ./scripts/ci/mutmut-run.sh detail <name>"
}

case "${1:-run}" in
  run)
    echo "=== Mutation Testing (src/) ==="
    echo "This may take several minutes..."
    echo ""
    # mutmut run exits 0 when mutants survive. A non-zero exit is a real failure
    # (the unmutated tests fail, pytest cannot start), so set -e stops here.
    uv run mutmut run
    echo ""
    show_results
    ;;
  results)
    show_results
    ;;
  detail)
    if [ -n "${2:-}" ]; then
      require_results
      uv run mutmut show "$2"
    else
      show_detail
    fi
    ;;
  *)
    echo "Usage: $0 {run|results|detail [mutant-name]}"
    exit 1
    ;;
esac
