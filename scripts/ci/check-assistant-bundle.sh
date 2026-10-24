#!/usr/bin/env bash
set -euo pipefail

# Checks whether a production frontend build carries the assistant feature.
#
# The assistant is gated at build time by VITE_ASSISTANT_ENABLED (see
# frontend/src/components/assistant/index.tsx). Without the flag, Vite inlines the
# literal and Rollup drops the dynamic imports, so none of the assistant chunks, API
# paths or UI strings should reach dist/. This script is the check that claims.
#
# Each marker is looked for in dist/ (chunk file names and string literals):
#   absent   fails if ANY marker is found    -> run on a build WITHOUT the flag
#   present  fails if ANY marker is missing  -> run on a build WITH the flag
#
# Always run both. `present` is the positive control: if a marker is renamed, the
# `absent` check would pass for the wrong reason, and `present` is what notices.
#
# Usage:
#   ./scripts/ci/check-assistant-bundle.sh <dist-dir> absent|present
#
#   cd frontend && npm run build && cd ..
#   ./scripts/ci/check-assistant-bundle.sh frontend/dist absent

DIST_DIR="${1:-}"
EXPECT="${2:-}"

if [ -z "$DIST_DIR" ] || { [ "$EXPECT" != "absent" ] && [ "$EXPECT" != "present" ]; }; then
  echo "Usage: $0 <dist-dir> absent|present" >&2
  exit 2
fi

if [ ! -d "$DIST_DIR/assets" ]; then
  echo "error: $DIST_DIR/assets does not exist -- run 'npm run build' in frontend/ first" >&2
  exit 2
fi

# Lazy chunks, named after their source files (vite.config.ts sets no chunk naming).
CHUNK_PREFIXES=(AssistantRoot AssistantGuide AssistantPrivacyCard triggers)

# Strings that live only in the assistant code: its API paths, a label from each
# locale's assistant.json, and the panel footer, a second string from the English
# catalog, so a rename of either key is caught. The i18n catalogs are bundled together
# with the assistant namespace, so the labels also prove the namespace stays out of an
# unflagged build.
STRINGS=(
  "assistant/chat/stream"
  "assistant/config"
  "Explain this result"
  "Vysvětlit výsledek"
  "The assistant can be wrong"
)

FOUND=()
MISSING=()

for prefix in "${CHUNK_PREFIXES[@]}"; do
  if compgen -G "$DIST_DIR/assets/$prefix-*.js" > /dev/null; then
    FOUND+=("chunk $prefix-*.js")
  else
    MISSING+=("chunk $prefix-*.js")
  fi
done

for s in "${STRINGS[@]}"; do
  if grep -rqF -- "$s" "$DIST_DIR"; then
    FOUND+=("string \"$s\"")
  else
    MISSING+=("string \"$s\"")
  fi
done

echo "Assistant bundle check on $DIST_DIR (expecting: $EXPECT)"
echo "  found:   ${#FOUND[@]} of $((${#FOUND[@]} + ${#MISSING[@]})) markers"

if [ "$EXPECT" = "absent" ]; then
  if [ "${#FOUND[@]}" -gt 0 ]; then
    echo "FAIL: the build was meant to exclude the assistant but still contains:" >&2
    printf '  - %s\n' "${FOUND[@]}" >&2
    exit 1
  fi
  echo "PASS: no assistant marker in the build"
else
  if [ "${#MISSING[@]}" -gt 0 ]; then
    echo "FAIL: the build was meant to include the assistant but lacks:" >&2
    printf '  - %s\n' "${MISSING[@]}" >&2
    echo "If a marker was renamed on purpose, update this script." >&2
    exit 1
  fi
  echo "PASS: every assistant marker is in the build"
fi
