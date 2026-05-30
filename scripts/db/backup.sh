#!/usr/bin/env bash
# Manual pg_dump backup of a BeCoMe database.
#
# Railway's native backups require the Pro plan, so this is the free fallback: it
# temporarily opens a public TCP proxy on the chosen database, runs pg_dump over it,
# and ALWAYS removes the proxy again (even on error). Run it before risky changes and
# periodically; store the dumps somewhere safe -- they contain user data.
#
#   Usage:  ./scripts/db/backup.sh [prod|test|dev]      (default: prod)
#   Output: backups/<env>-<UTC-timestamp>.dump  (custom format)
#   Restore: pg_restore --no-owner --no-privileges -d <target-url> <dump>
#
# Requires: the Railway CLI logged in and linked (or RAILWAY_PROJECT_ID set), plus jq
# and a current pg_dump (>= the server; `brew install libpq` provides one).
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
[ -z "$TOKEN" ] && { echo "No Railway token -- run 'railway login' (or 'railway whoami' to refresh)"; exit 1; }
gql() { curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" https://backboard.railway.com/graphql/v2 -d "$1"; }

# Always clean up: remove the temporary proxy (if opened) and the stderr scratch file.
ERRFILE=$(mktemp)
PROXY_ID=""
cleanup() {
  [ -n "$PROXY_ID" ] && gql "$(jq -n --arg id "$PROXY_ID" '{query:"mutation($id:String!){tcpProxyDelete(id:$id)}",variables:{id:$id}}')" >/dev/null && echo "temporary proxy removed"
  rm -f "$ERRFILE"
}
trap cleanup EXIT

# Resolve environment + service ids by name.
META=$(gql "$(jq -n --arg id "$PROJECT_ID" '{query:"query($id:String!){project(id:$id){environments{edges{node{id name}}}services{edges{node{id name}}}}}",variables:{id:$id}}')")
ENV_ID=$(printf '%s' "$META" | jq -r --arg n "$RW_ENV" '.data.project.environments.edges[].node | select(.name==$n) | .id')
SVC_ID=$(printf '%s' "$META" | jq -r --arg n "$DB_SVC" '.data.project.services.edges[].node | select(.name==$n) | .id')
{ [ -z "$ENV_ID" ] || [ -z "$SVC_ID" ]; } && { echo "could not resolve $RW_ENV / $DB_SVC"; exit 1; }

# Password + database name from the internal DATABASE_URL (password is shared with the proxy).
INTURL=$(gql "$(jq -n --arg p "$PROJECT_ID" --arg e "$ENV_ID" --arg s "$SVC_ID" '{query:"query($p:String!,$e:String!,$s:String!){variables(projectId:$p,environmentId:$e,serviceId:$s)}",variables:{p:$p,e:$e,s:$s}}')" | jq -r '.data.variables.DATABASE_URL // empty')
[ -z "$INTURL" ] && { echo "no DATABASE_URL for $DB_SVC"; exit 1; }
PW=$(printf '%s' "$INTURL" | sed -E 's#^postgres(ql)?://[^:]+:([^@]+)@.*#\2#')
DBN=$(printf '%s' "$INTURL" | sed -E 's#.*/([^/?]+)(\?.*)?$#\1#')

# Open a temporary public proxy (torn down by the trap above).
CR=$(gql "$(jq -n --arg e "$ENV_ID" --arg s "$SVC_ID" '{query:"mutation($i:TCPProxyCreateInput!){tcpProxyCreate(input:$i){id domain proxyPort}}",variables:{i:{environmentId:$e,serviceId:$s,applicationPort:5432}}}')")
PROXY_ID=$(printf '%s' "$CR" | jq -r '.data.tcpProxyCreate.id // empty')
DOMAIN=$(printf '%s' "$CR" | jq -r '.data.tcpProxyCreate.domain // empty')
PORT=$(printf '%s' "$CR" | jq -r '.data.tcpProxyCreate.proxyPort // empty')
[ -z "$PROXY_ID" ] && { echo "proxy create failed: $CR"; exit 1; }
echo "temporary proxy open on $DOMAIN:$PORT"

PG_DUMP=/opt/homebrew/opt/libpq/bin/pg_dump
command -v "$PG_DUMP" >/dev/null 2>&1 || PG_DUMP=pg_dump
# Password goes through PGPASSWORD so it never appears in the process arguments (ps aux).
URL="postgresql://postgres@$DOMAIN:$PORT/$DBN?sslmode=require&connect_timeout=10"

mkdir -p backups
OUT="backups/${ENV_ARG}-$(date -u +%Y%m%dT%H%M%SZ).dump"
ok=""
for i in $(seq 1 6); do
  if PGPASSWORD="$PW" "$PG_DUMP" "$URL" --no-owner --no-privileges -Fc -f "$OUT" 2>"$ERRFILE"; then ok=1; break; fi
  echo "  (proxy warming up, retry $i)..."; sleep 5
done
[ -z "$ok" ] && { echo "pg_dump failed:"; cat "$ERRFILE"; exit 1; }
echo "OK: $OUT ($(du -h "$OUT" | cut -f1))"
echo "restore: pg_restore --no-owner --no-privileges -d <target-url> $OUT"
