#!/usr/bin/env bash
set -euo pipefail

# Checks that the frontend build prerenders the public pages and that nginx serves them.
#
# The build (`npm run build` in frontend/) renders every public route to dist/<route>/index.html
# and writes dist/spa.html, the empty shell for the routes behind a login, and dist/404.html,
# the not-found page (see frontend/scripts/prerender.mjs). The route list and the expected
# titles come from the build's own renderer (frontend/dist-ssr), so a route added to the app
# is checked without touching this script.
#
# Build checks (always):
#   - every public route has its file, with a non-empty root that names its route (data-route),
#     its own title, description and canonical link, and no robots tag;
#   - spa.html has the noindex tag and an empty root;
#   - 404.html has a non-empty root with no data-route, the not-found title, the noindex tag
#     and no canonical link;
#   - every inline script in every built page has its sha256 in each Content-Security-Policy
#     of frontend/nginx.conf, because a script the policy does not allow is blocked silently.
#
# Image checks (--docker): builds the frontend image, runs it, and fetches pages over HTTP to
# prove that nginx answers without a redirect, with the security headers, with no-cache on the
# HTML, the prerendered page for a public route, the shell for each app route behind a login
# (/login, /projects, /projects/<id>, /profile/), a real 404 with the not-found page for an
# unknown path and an unknown case study, and a plain 404 for a missing asset. The container and
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

# Every public route with its expected title and description as prerender.mjs writes them
# (HTML-escaped), one "route<TAB>title<TAB>description" per line.
ROUTES="$WORK/routes.tsv"
NOT_FOUND_TITLE_FILE="$WORK/not-found-title.txt"
if ! node --input-type=module -e '
  const { publicRoutes, pageMeta, notFoundMeta } = await import(process.argv[1]);
  const { writeFileSync } = await import("node:fs");
  const escapeHtml = (text) =>
    text
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll("\"", "&quot;")
      .replaceAll("\u0027", "&#39;");
  const lines = publicRoutes.map((route) => {
    const { title, description } = pageMeta(route);
    return `${route}\t${escapeHtml(title)}\t${escapeHtml(description)}`;
  });
  writeFileSync(process.argv[2], lines.join("\n") + "\n");
  writeFileSync(process.argv[3], escapeHtml(notFoundMeta().title));
' "$FRONTEND/dist-ssr/entry-server.js" "$ROUTES" "$NOT_FOUND_TITLE_FILE" 2> "$WORK/routes.err"; then
  echo "error: could not load the renderer frontend/dist-ssr/entry-server.js:" >&2
  cat "$WORK/routes.err" >&2
  exit 2
fi
[ -s "$ROUTES" ] || { echo "error: the renderer listed no public routes" >&2; exit 2; }
NOT_FOUND_TITLE="$(cat "$NOT_FOUND_TITLE_FILE")"

page_file() {
  if [ "$1" = "/" ]; then echo "$DIST/index.html"; else echo "$DIST$1/index.html"; fi
}

title_for() {
  awk -F'\t' -v route="$1" '$1 == route { print $2 }' "$ROUTES"
}

has_empty_root() { grep -qF '<div id="root"></div>' "$1"; }

echo "=== Prerender build check ($(wc -l < "$ROUTES" | tr -d ' ') public routes) ==="

while IFS=$'\t' read -r route title description; do
  file="$(page_file "$route")"
  if [ ! -f "$file" ]; then
    fail "$route: $file does not exist"
    continue
  fi
  problems=""
  if has_empty_root "$file"; then problems="$problems empty-root"; fi
  grep -qF "<div id=\"root\" data-route=\"$route\">" "$file" || problems="$problems data-route"
  grep -qF "<title>$title</title>" "$file" || problems="$problems title"
  grep -qF "<meta name=\"description\" content=\"$description\" />" "$file" || problems="$problems description"
  grep -qF "<link rel=\"canonical\" href=\"$ORIGIN$route\" />" "$file" || problems="$problems canonical"
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

if [ ! -f "$DIST/404.html" ]; then
  fail "404.html does not exist"
else
  problems=""
  if has_empty_root "$DIST/404.html"; then problems="$problems empty-root"; fi
  if grep -qF 'data-route=' "$DIST/404.html"; then problems="$problems data-route"; fi
  grep -qF "<title>$NOT_FOUND_TITLE</title>" "$DIST/404.html" || problems="$problems title"
  grep -qF '<meta name="robots" content="noindex" />' "$DIST/404.html" || problems="$problems noindex"
  if grep -qF 'rel="canonical"' "$DIST/404.html"; then problems="$problems canonical"; fi
  if [ -n "$problems" ]; then fail "404.html:$problems"; else pass "404.html: not-found title, noindex, no canonical, no data-route"; fi
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

  # check_response <label> [expected status, 200 by default]
  check_response() {
    local label="$1" expected="${2:-200}" problems=""
    [ "$STATUS" = "$expected" ] || problems="$problems status-$STATUS"
    if grep -qi '^location:' "$WORK/headers"; then problems="$problems redirect"; fi
    grep -qi '^content-security-policy:' "$WORK/headers" || problems="$problems no-csp"
    if [ "$expected" = "200" ]; then
      grep -qi '^cache-control: no-cache' "$WORK/headers" || problems="$problems cache-control"
    elif grep -qiE '^(cache-control|last-modified):' "$WORK/headers"; then
      # nginx's `expires` skips a 404, so the page has no cache header. Without a
      # Last-Modified either, a cache has no freshness to work from and revalidates.
      problems="$problems cache-header"
    fi
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

  for request in /login /projects /projects/123 /profile/; do
    fetch "$request"
    if check_response "GET $request"; then
      if has_empty_root "$WORK/body" && grep -qF '<meta name="robots" content="noindex" />' "$WORK/body"; then
        pass "GET $request: 200, the app shell with noindex"
      else
        fail "GET $request: expected the app shell (empty root, noindex)"
      fi
    fi
  done

  for request in /no-such-page /case-study/unknown; do
    fetch "$request"
    if check_response "GET $request" 404; then
      if grep -qF "<title>$NOT_FOUND_TITLE</title>" "$WORK/body" && grep -qF '<meta name="robots" content="noindex" />' "$WORK/body"; then
        pass "GET $request: 404, the not-found page"
      else
        fail "GET $request: expected the not-found page (title \"$NOT_FOUND_TITLE\", noindex)"
      fi
    fi
  done

  # A missing asset is a real 404 too, and never the app shell.
  fetch /assets/missing.js
  if [ "$STATUS" = "404" ] && ! grep -qF 'id="root"></div>' "$WORK/body"; then
    pass "GET /assets/missing.js: 404"
  else
    fail "GET /assets/missing.js: expected 404 and no app shell, got $STATUS"
  fi
fi

echo ""
if [ "$FAILURES" -gt 0 ]; then
  echo "FAIL: $FAILURES problem(s)" >&2
  exit 1
fi
if [ "$DOCKER" = true ]; then
  echo "PASS: the build prerenders the public pages and the image serves them and answers 404 for the rest"
else
  echo "PASS: the build prerenders the public pages"
fi
