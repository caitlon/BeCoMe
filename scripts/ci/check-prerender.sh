#!/usr/bin/env bash
set -euo pipefail

# Checks that the frontend build prerenders the public pages and that nginx serves them.
#
# The build (`npm run build` in frontend/) renders every public route to dist/<route>/index.html
# and writes dist/spa.html, the empty shell for the routes behind a login (see
# frontend/scripts/prerender.mjs). The route list and the expected titles come from the
# build's own renderer (frontend/dist-ssr), so a route added to the app is checked without
# touching this script.
#
# Build checks (always):
#   - every public route has its file, with a non-empty root, its own title and canonical link;
#   - spa.html has the noindex tag and an empty root;
#   - every inline script in every built page has its sha256 in each Content-Security-Policy
#     of frontend/nginx.conf, because a script the policy does not allow is blocked silently.
#
# Image checks (--docker): builds the frontend image, runs it, and fetches pages over HTTP to
# prove that nginx answers without a redirect, with the security headers, with no-cache on the
# HTML, the prerendered page for a public route and the shell for an app route. The container and
# the image are removed afterwards.
#
# Usage (after `cd frontend && npm run build`):
#   ./scripts/ci/check-prerender.sh
#   ./scripts/ci/check-prerender.sh --docker

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FRONTEND="$PROJECT_ROOT/frontend"
DIST="$FRONTEND/dist"
NGINX_CONF="$FRONTEND/nginx.conf"
ORIGIN="https://www.becomify.app"

DOCKER=false
case "${1:-}" in
  "") ;;
  --docker) DOCKER=true ;;
  *) echo "Usage: $0 [--docker]" >&2; exit 2 ;;
esac

if [ ! -f "$DIST/index.html" ] || [ ! -f "$FRONTEND/dist-ssr/entry-server.js" ]; then
  echo "error: no build found -- run 'npm run build' in frontend/ first" >&2
  exit 2
fi

WORK="$(mktemp -d)"
FAILURES=0
CONTAINER=""
IMAGE=""

cleanup() {
  if [ -n "$CONTAINER" ]; then docker rm -f "$CONTAINER" > /dev/null 2>&1 || true; fi
  if [ -n "$IMAGE" ]; then docker rmi -f "$IMAGE" > /dev/null 2>&1 || true; fi
  rm -rf "$WORK"
}
trap cleanup EXIT

pass() { echo "  PASS  $1"; }
fail() { echo "  FAIL  $1" >&2; FAILURES=$((FAILURES + 1)); }

# Every public route with its expected title, one "route<TAB>title" per line.
ROUTES="$WORK/routes.tsv"
node --input-type=module -e '
  const { publicRoutes, pageMeta } = await import(process.argv[1]);
  for (const route of publicRoutes) console.log(`${route}\t${pageMeta(route).title}`);
' "$FRONTEND/dist-ssr/entry-server.js" > "$ROUTES" 2> /dev/null
[ -s "$ROUTES" ] || { echo "error: the renderer listed no public routes" >&2; exit 2; }

page_file() {
  if [ "$1" = "/" ]; then echo "$DIST/index.html"; else echo "$DIST$1/index.html"; fi
}

canonical_for() {
  if [ "$1" = "/" ]; then echo "$ORIGIN/"; else echo "$ORIGIN$1"; fi
}

title_for() {
  awk -F'\t' -v route="$1" '$1 == route { print $2 }' "$ROUTES"
}

has_empty_root() { grep -qF '<div id="root"></div>' "$1"; }

echo "=== Prerender build check ($(wc -l < "$ROUTES" | tr -d ' ') public routes) ==="

while IFS=$'\t' read -r route title; do
  file="$(page_file "$route")"
  if [ ! -f "$file" ]; then
    fail "$route: $file does not exist"
    continue
  fi
  problems=""
  if has_empty_root "$file"; then problems="$problems empty-root"; fi
  grep -qF "<title>$title</title>" "$file" || problems="$problems title"
  grep -qF "<link rel=\"canonical\" href=\"$(canonical_for "$route")\" />" "$file" || problems="$problems canonical"
  if grep -qF 'name="robots"' "$file"; then problems="$problems robots-tag"; fi
  if [ -n "$problems" ]; then fail "$route:$problems"; else pass "$route"; fi
done < "$ROUTES"

if [ ! -f "$DIST/spa.html" ]; then
  fail "spa.html does not exist"
elif grep -qF '<meta name="robots" content="noindex" />' "$DIST/spa.html" && has_empty_root "$DIST/spa.html"; then
  pass "spa.html: noindex, empty root"
else
  fail "spa.html needs the noindex tag and an empty root"
fi

# The SHA-256 of each inline script, as the Content-Security-Policy writes it.
inline_hashes() {
  node --input-type=module -e '
    import { createHash } from "node:crypto";
    import { readFileSync } from "node:fs";
    const html = readFileSync(process.argv[1], "utf8");
    for (const match of html.matchAll(/<script(?![^>]*\ssrc=)[^>]*>([\s\S]*?)<\/script>/g)) {
      console.log(createHash("sha256").update(match[1]).digest("base64"));
    }
  ' "$1"
}

csp_lines="$WORK/csp.txt"
grep 'add_header Content-Security-Policy' "$NGINX_CONF" > "$csp_lines" || true
[ -s "$csp_lines" ] || { echo "error: no Content-Security-Policy in $NGINX_CONF" >&2; exit 2; }

while IFS= read -r html_file; do
  rel="${html_file#"$DIST"/}"
  count=0
  while IFS= read -r hash; do
    [ -n "$hash" ] || continue
    count=$((count + 1))
    missing="$(grep -vcF "'sha256-$hash'" "$csp_lines" || true)"
    if [ "$missing" != "0" ]; then fail "$rel: inline script sha256-$hash is missing from $missing Content-Security-Policy line(s)"; fi
  done < <(inline_hashes "$html_file")
  if [ "$count" -eq 0 ]; then fail "$rel: no inline script found, the pre-paint script is gone"; fi
done < <(find "$DIST" -name '*.html' | sort)
if [ "$FAILURES" -eq 0 ]; then pass "inline scripts of every page are allowed by the Content-Security-Policy"; fi

if [ "$DOCKER" = true ]; then
  echo ""
  echo "=== Prerender image check ==="
  IMAGE="become-frontend-prerender-check:$$"
  docker build --quiet -t "$IMAGE" "$FRONTEND" > /dev/null
  CONTAINER="$(docker run -d --rm -p 127.0.0.1::8080 "$IMAGE")"
  PORT="$(docker port "$CONTAINER" 8080/tcp | head -n 1 | sed 's/.*://')"
  BASE="http://127.0.0.1:$PORT"

  for _ in $(seq 1 30); do
    curl -s -o /dev/null --max-time 2 "$BASE/" && break
    sleep 1
  done

  # fetch <path> -> sets STATUS, and leaves the headers and body in $WORK/headers and $WORK/body.
  fetch() {
    STATUS="$(curl -s -o "$WORK/body" -D "$WORK/headers" -w '%{http_code}' --max-time 10 "$BASE$1" || true)"
  }

  check_response() {
    local label="$1" problems=""
    [ "$STATUS" = "200" ] || problems="$problems status-$STATUS"
    if grep -qi '^location:' "$WORK/headers"; then problems="$problems redirect"; fi
    grep -qi '^content-security-policy:' "$WORK/headers" || problems="$problems no-csp"
    grep -qi '^cache-control: no-cache' "$WORK/headers" || problems="$problems cache-control"
    if [ -n "$problems" ]; then fail "$label:$problems"; return 1; fi
  }

  case_study="$(awk -F'\t' '$1 ~ /^\/case-study\// { print $1; exit }' "$ROUTES")"
  for request in / /about /about/ "$case_study"; do
    fetch "$request"
    route="${request%/}"
    [ -n "$route" ] || route="/"
    title="$(title_for "$route")"
    if check_response "GET $request"; then
      if ! grep -qF "<title>$title</title>" "$WORK/body"; then
        fail "GET $request: the title is not \"$title\""
      elif grep -qF 'name="robots"' "$WORK/body"; then
        fail "GET $request: a public page carries a robots tag"
      else
        pass "GET $request: 200, prerendered \"$title\""
      fi
    fi
  done

  fetch /projects
  if check_response "GET /projects"; then
    if has_empty_root "$WORK/body" && grep -qF '<meta name="robots" content="noindex" />' "$WORK/body"; then
      pass "GET /projects: 200, the app shell with noindex"
    else
      fail "GET /projects: expected the app shell (empty root, noindex)"
    fi
  fi
fi

echo ""
if [ "$FAILURES" -gt 0 ]; then
  echo "FAIL: $FAILURES problem(s)" >&2
  exit 1
fi
if [ "$DOCKER" = true ]; then
  echo "PASS: the build prerenders the public pages and the image serves them"
else
  echo "PASS: the build prerenders the public pages"
fi
