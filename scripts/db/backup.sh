#!/usr/bin/env bash
# Manual pg_dump backup of a BeCoMe database.
#
# Railway's native backups require the Pro plan, so this is the free fallback: it opens an
# SSH tunnel to the chosen database (scripts/db/lib-tunnel.sh), runs pg_dump through it with
# the server certificate verified against the database's own root CA, and ALWAYS closes the
# tunnel again (even on error). No public TCP proxy is involved. While the tunnel is open,
# any process on this machine can connect to the database without a password, so run it
# attended. Run it before risky changes and periodically, and store the dumps somewhere safe,
# because they contain user data.
#
#   Usage:  ./scripts/db/backup.sh [prod|dev]  (default: prod)
#   Output: backups/<env>-<UTC-timestamp>.dump  (custom format)
#   Restore: pg_restore --no-owner --no-privileges -d <target-url> <dump>
#
# Requires: a Railway CLI with `connect --tunnel-only` (5.71 or newer) that is logged in, an
# SSH key registered with `railway ssh keys add`, a linked repo (`railway link`) or
# RAILWAY_PROJECT_ID, jq, openssl, python3, and a local pg_dump at least as new as the server
# (`brew install libpq`). pg_dump runs on this machine; the script has no container fallback.
set -uo pipefail

ENV_ARG="${1:-prod}"
case "$ENV_ARG" in
  prod) RW_ENV="prod"; DB_SVC="prod-db" ;;
  dev)  RW_ENV="dev";  DB_SVC="dev-db" ;;
  *) echo "usage: $0 [prod|dev]"; exit 1 ;;
esac

# shellcheck source=scripts/db/lib-tunnel.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib-tunnel.sh"

# Always clean up: close the tunnel (if opened) and remove the stderr scratch file.
ERRFILE=$(mktemp)
cleanup() { db_tunnel_close; rm -f "$ERRFILE"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

PG_DUMP=/opt/homebrew/opt/libpq/bin/pg_dump
command -v "$PG_DUMP" >/dev/null 2>&1 || PG_DUMP=pg_dump
command -v "$PG_DUMP" >/dev/null 2>&1 || { echo "no pg_dump found. Install one at least as new as the server: brew install libpq"; exit 1; }

db_tunnel_open "$RW_ENV" "$DB_SVC" || exit 1

# The database name comes from the service's own variables. Nothing else is read from them,
# and the JSON goes straight into jq, because it also holds the superuser password.
DBN=$(railway variables -p "$DB_TUNNEL_PROJECT_ID" -e "$RW_ENV" -s "$DB_SVC" --json 2>/dev/null \
  | jq -r '.PGDATABASE // .POSTGRES_DB // empty' 2>/dev/null)
[ -z "$DBN" ] && DBN=railway

# `postgres` is trusted on the tunnel's loopback, so no password is needed. verify-full with
# host `localhost` is what the certificate's name allows (see lib-tunnel.sh).
URL="postgresql://postgres@localhost:$DB_TUNNEL_PORT/$DBN?sslmode=verify-full&sslrootcert=$DB_TUNNEL_ROOT_CERT&connect_timeout=10"

# The dump holds user data, so the file (and a backups/ folder this run creates) is owner-only.
umask 077
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

# `pg_dump` refuses to dump a server newer than itself, and the client here comes from
# Homebrew while the server is whatever Railway runs. The refusal is `pg_dump`'s own
# message, and it is translated: under a German locale it reads "Abbruch wegen
# unpassender Serverversion", and a grep for the English text would silently match
# nothing. `LC_ALL=C` keeps it English, so the hint below still fires on any machine.
if ! LC_ALL=C "$PG_DUMP" "$URL" --no-owner --no-privileges -Fc -f "$OUT" 2>"$ERRFILE"; then
  echo "pg_dump failed:"; cat "$ERRFILE"; discard_output
  if LC_ALL=C grep -q "server version mismatch" "$ERRFILE" 2>/dev/null; then
    echo "  pg_dump is older than the server. Install one at least as new: brew upgrade libpq"
  fi
  exit 1
fi
if [ ! -s "$OUT" ]; then
  echo "pg_dump wrote nothing to $OUT"; discard_output; exit 1
fi
echo "OK: $OUT ($(du -h "$OUT" | cut -f1))"
echo "restore: pg_restore --no-owner --no-privileges -d <target-url> $OUT"
