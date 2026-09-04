#!/usr/bin/env bash
# Manual pg_dump backup of a BeCoMe database.
#
# Railway's native backups require the Pro plan, so this is the free fallback: it
# temporarily opens a public TCP proxy on the chosen database, runs pg_dump over it,
# and ALWAYS removes the proxy again (even on error). Run it before risky changes and
# periodically, and store the dumps somewhere safe, because they contain user data.
#
#   Usage:  ./scripts/db/backup.sh [prod|test|dev]      (default: prod)
#   Output: backups/<env>-<UTC-timestamp>.dump  (custom format)
#   Restore: pg_restore --no-owner --no-privileges -d <target-url> <dump>
#
# Requires: the Railway CLI logged in and linked (or RAILWAY_PROJECT_ID set), plus jq,
# and a way to run pg_dump at least as new as the server. A local client is used when it
# is new enough; otherwise a `postgres:<server major>` container is, so docker alone is
# sufficient and no formula has to be pinned per machine.
set -uo pipefail

ENV_ARG="${1:-prod}"
case "$ENV_ARG" in
  prod) RW_ENV="production"; DB_SVC="prod-db" ;;
  test) RW_ENV="staging";    DB_SVC="test-db" ;;
  dev)  RW_ENV="dev";        DB_SVC="dev-db" ;;
  *) echo "usage: $0 [prod|test|dev]"; exit 1 ;;
esac

# Project id from the linked Railway project; override with RAILWAY_PROJECT_ID.
PROJECT_ID="${RAILWAY_PROJECT_ID:-$(railway status --json 2>/dev/null | jq -r '.id // empty')}"
[ -z "$PROJECT_ID" ] && { echo "Set RAILWAY_PROJECT_ID, or run 'railway link' in this repo first"; exit 1; }
TOKEN=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.railway/config.json')))['user']['accessToken'])" 2>/dev/null)
[ -z "$TOKEN" ] && { echo "No Railway token. Run 'railway login', or 'railway whoami' to refresh"; exit 1; }

# GraphQL helper. The query is passed to jq as DATA (--arg), never embedded in the jq
# program, so the braces/`$vars` in the query can't be mis-parsed by any jq version.
api() {  # $1 = query/mutation string; $2 = variables JSON object (default {})
  local vars="${2:-}"; [ -z "$vars" ] && vars='{}'
  curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    https://backboard.railway.com/graphql/v2 \
    -d "$(jq -n --arg q "$1" --argjson v "$vars" '{query:$q,variables:$v}')"
}

# Always clean up: remove the temporary proxy (if opened) and the stderr scratch file.
# The proxy is PUBLIC while it is up: for its lifetime the only thing between the
# database and the internet is the role password, so a failed teardown must be loud
# rather than swallowed. The old form chained the delete with && and printed nothing when
# it failed, which looked exactly like the case where no proxy was ever opened.
ERRFILE=$(mktemp)
PROXY_ID=""
cleanup() {
  if [ -n "$PROXY_ID" ]; then
    if api 'mutation($id:String!){tcpProxyDelete(id:$id)}' "$(jq -n --arg id "$PROXY_ID" '{id:$id}')" >/dev/null; then
      echo "temporary proxy removed"
    else
      echo "WARNING: could not remove the temporary proxy ($PROXY_ID)." >&2
      echo "It is PUBLIC. Delete it in the Railway dashboard: $DB_SVC -> Settings -> TCP Proxy." >&2
    fi
  fi
  rm -f "$ERRFILE"
}
trap cleanup EXIT

# Resolve environment + service ids by name.
META=$(api 'query($id:String!){project(id:$id){environments{edges{node{id name}}}services{edges{node{id name}}}}}' "$(jq -n --arg id "$PROJECT_ID" '{id:$id}')")
ENV_ID=$(printf '%s' "$META" | jq -r --arg n "$RW_ENV" '.data.project.environments.edges[].node | select(.name==$n) | .id')
SVC_ID=$(printf '%s' "$META" | jq -r --arg n "$DB_SVC" '.data.project.services.edges[].node | select(.name==$n) | .id')
{ [ -z "$ENV_ID" ] || [ -z "$SVC_ID" ]; } && { echo "could not resolve $RW_ENV / $DB_SVC"; exit 1; }

# Password + database name from the service's canonical Postgres variables.
VARS=$(api 'query($p:String!,$e:String!,$s:String!){variables(projectId:$p,environmentId:$e,serviceId:$s)}' "$(jq -n --arg p "$PROJECT_ID" --arg e "$ENV_ID" --arg s "$SVC_ID" '{p:$p,e:$e,s:$s}')")
printf '%s' "$VARS" | jq -e '.errors' >/dev/null 2>&1 && { echo "Railway API error: $(printf '%s' "$VARS" | jq -c '.errors')"; exit 1; }
PW=$(printf '%s' "$VARS" | jq -r '.data.variables.PGPASSWORD // .data.variables.POSTGRES_PASSWORD // empty')
DBN=$(printf '%s' "$VARS" | jq -r '.data.variables.PGDATABASE // .data.variables.POSTGRES_DB // "railway"')
[ -z "$PW" ] && { echo "could not read DB password for $DB_SVC (got vars: $(printf '%s' "$VARS" | jq -r '.data.variables|keys|join(",")' 2>/dev/null))"; exit 1; }

# Open a temporary public proxy (torn down by the trap above).
CR=$(api 'mutation($i:TCPProxyCreateInput!){tcpProxyCreate(input:$i){id domain proxyPort}}' "$(jq -n --arg e "$ENV_ID" --arg s "$SVC_ID" '{i:{environmentId:$e,serviceId:$s,applicationPort:5432}}')")
PROXY_ID=$(printf '%s' "$CR" | jq -r '.data.tcpProxyCreate.id // empty')
DOMAIN=$(printf '%s' "$CR" | jq -r '.data.tcpProxyCreate.domain // empty')
PORT=$(printf '%s' "$CR" | jq -r '.data.tcpProxyCreate.proxyPort // empty')
[ -z "$PROXY_ID" ] && { echo "proxy create failed: $CR"; exit 1; }
echo "temporary proxy open on $DOMAIN:$PORT"

PG_DUMP=/opt/homebrew/opt/libpq/bin/pg_dump
command -v "$PG_DUMP" >/dev/null 2>&1 || PG_DUMP=pg_dump
HAVE_LOCAL=""
command -v "$PG_DUMP" >/dev/null 2>&1 && HAVE_LOCAL=1

# Exported once rather than prefixed per command. Both keep it out of `ps`, but the
# docker fallback below cannot use a prefix: `docker run -e VAR=value` puts the value in
# the argv of the HOST docker process, where `ps` and `docker inspect` both show it.
# The bare `-e VAR` form forwards the exported value without ever naming it.
export PGPASSWORD="$PW"
URL="postgresql://postgres@$DOMAIN:$PORT/$DBN?sslmode=require&connect_timeout=10"

mkdir -p backups
OUT="backups/${ENV_ARG}-$(date -u +%Y%m%dT%H%M%SZ).dump"

# A dump that failed must not leave a file behind. `pg_dump -f` creates the target
# before it does anything else, so a failed run used to leave a 0-byte `.dump` with a
# correct-looking name sitting next to the real ones. That is worse than no backup:
# it is the thing you reach for on the day you need it. Measured 2026-09-03, when a
# version mismatch produced exactly that file.
#
# It removes only an EMPTY file, and that leaves one case uncovered on purpose: a dump
# that connects and then dies mid-stream leaves a truncated, non-empty file with the
# same correct-looking name. Any size threshold above zero would be a guess about how
# small a legitimate database can be, and a wrong guess throws away a real backup. The
# cover for that case is not this function, it is reading the dump's table of contents
# after the run: `pg_restore --list <file>`.
discard_output() { [ -f "$OUT" ] && [ ! -s "$OUT" ] && rm -f "$OUT"; }

# Every message this script greps for is `pg_dump`'s own, and `pg_dump` is translated:
# under a German locale the version refusal reads "Abbruch wegen unpassender
# Serverversion", under Russian something different again, and the greps below match
# none of them. Without `LC_ALL=C` this whole fallback is silently inert on any machine
# whose shell is not English, which is the worst way for a safety net to fail.
mismatch() { LC_ALL=C grep -q "server version mismatch" "$ERRFILE" 2>/dev/null; }
server_major() { sed -n 's/.*server version: \([0-9][0-9]*\).*/\1/p' "$ERRFILE" | head -1; }

docker_dump() {  # $1 = postgres major to run
  discard_output
  docker run --rm -i -e PGPASSWORD -e LC_ALL=C "postgres:$1" \
    pg_dump "$URL" --no-owner --no-privileges -Fc > "$OUT" 2>"$ERRFILE"
}

# The proxy needs the same warm-up here as it does for a local client, and the reason
# this is easy to miss is that the fix above removed the wait: before it, a mismatch
# spun through six retries and the proxy came up during them. Breaking out early made
# the diagnosis honest and left the container racing a proxy that is not listening yet.
# Whether it wins depends on how long docker spends pulling an image, which is not a
# thing to depend on. A mismatch still returns immediately: it is the caller's cue to
# correct the major and try again, and no amount of waiting changes it.
docker_dump_waiting() {  # $1 = postgres major to run
  local i
  for i in $(seq 1 6); do
    if docker_dump "$1"; then return 0; fi
    if mismatch; then return 1; fi
    echo "  (proxy warming up, retry $i)..."; sleep 5
  done
  return 1
}

ok=""
if [ -n "$HAVE_LOCAL" ]; then
  for i in $(seq 1 6); do
    if LC_ALL=C "$PG_DUMP" "$URL" --no-owner --no-privileges -Fc -f "$OUT" 2>"$ERRFILE"; then ok=1; break; fi
    # Only a warming proxy is worth retrying. A version mismatch will not fix itself in
    # five seconds, and the loop used to hide it behind six identical lines.
    if mismatch; then break; fi
    echo "  (proxy warming up, retry $i)..."; sleep 5
  done
fi

# `pg_dump` refuses to dump a server newer than itself, and the client here comes from
# Homebrew while the server is whatever Railway runs. Rather than pinning a formula on
# every machine, fall back to a container of the server's own major, read out of the
# refusal itself. With no local client at all there is nothing to read, so a candidate
# is tried first and corrected once if it is also too old.
if [ -z "$ok" ] && { [ -z "$HAVE_LOCAL" ] || mismatch; }; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "  need a pg_dump at least as new as the server, and docker is not installed."
    echo "  install one, e.g. brew install postgresql@$(server_major || echo 18)"
  elif ! docker info >/dev/null 2>&1; then
    echo "  need a pg_dump at least as new as the server, and the docker daemon is not running."
  else
    CAND=$(server_major); [ -z "$CAND" ] && CAND=18
    [ -z "$HAVE_LOCAL" ] && echo "  no local pg_dump found; using postgres:$CAND in docker"
    [ -n "$HAVE_LOCAL" ] && echo "  local pg_dump is older than the server; using postgres:$CAND in docker"
    if docker_dump_waiting "$CAND"; then
      ok=1
    elif mismatch; then
      REAL=$(server_major)
      if [ -n "$REAL" ] && [ "$REAL" != "$CAND" ]; then
        echo "  server is actually $REAL; retrying with postgres:$REAL"
        docker_dump_waiting "$REAL" && ok=1
      fi
    fi
  fi
fi

if [ -z "$ok" ]; then
  echo "pg_dump failed:"; cat "$ERRFILE"; discard_output; exit 1
fi
if [ ! -s "$OUT" ]; then
  echo "pg_dump wrote nothing to $OUT"; discard_output; exit 1
fi
echo "OK: $OUT ($(du -h "$OUT" | cut -f1))"
echo "restore: pg_restore --no-owner --no-privileges -d <target-url> $OUT"
