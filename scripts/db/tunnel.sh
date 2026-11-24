#!/usr/bin/env bash
# Open an SSH tunnel to a BeCoMe database on Railway, with the server certificate verified.
#
#   Usage:  ./scripts/db/tunnel.sh <dev|prod> <service> [-- command [args...]]
#
# With a command, the tunnel lives exactly as long as the command and the command's exit
# status is returned. Its environment carries DB_TUNNEL_PORT and DB_TUNNEL_ROOT_CERT, plus the
# libpq variables PGHOST, PGPORT, PGSSLMODE and PGSSLROOTCERT, so a URL is written inside
# `sh -c '...'`, where those names expand when the command runs. The corpus ingest, for example:
#
#   `./scripts/db/tunnel.sh dev dev-vector -- sh -c 'ASSISTANT_VECTOR_DB_URL="postgresql+psycopg://<owner>@localhost:$DB_TUNNEL_PORT/<database>?sslmode=verify-full&sslrootcert=$DB_TUNNEL_ROOT_CERT" uv run python scripts/assistant/ingest.py ...'`
#
# The full command is in api/assistant/README.md.
#
# Without a command, it prints the connection details and holds the tunnel open until Ctrl+C.
#
# The tunnel lands on the container's loopback, where Postgres trusts every connection:
# while it is open, any process on this machine can connect as any role, with no password.
# The exported PG* variables also point every libpq client the command starts at this
# database, so a URL without a host inside the command reaches it too.
# No public TCP proxy is involved, and the tunnel closes when the command ends or on Ctrl+C.
#
# Requires: a Railway CLI with `connect --tunnel-only` (5.71 or newer), an SSH key registered
# with `railway ssh keys add`, jq, openssl and python3. The repo needs `railway link`, or
# RAILWAY_PROJECT_ID set. How the certificate is checked: scripts/db/lib-tunnel.sh.
set -uo pipefail

usage() { echo "usage: $0 <dev|prod> <service> [-- command [args...]]" >&2; exit 2; }

[ $# -ge 2 ] || usage
ENV_ARG="$1"; SVC="$2"; shift 2
if [ $# -gt 0 ]; then
  [ "$1" = "--" ] && [ $# -ge 2 ] || usage
  shift
fi

# shellcheck source=scripts/db/lib-tunnel.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib-tunnel.sh"

# The signal traps turn Ctrl+C into a normal exit, so the EXIT trap always closes the tunnel.
trap db_tunnel_close EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

db_tunnel_open "$ENV_ARG" "$SVC" || exit 1

if [ $# -gt 0 ]; then
  "$@"
  exit $?
fi

echo "host:        localhost"
echo "port:        $DB_TUNNEL_PORT"
echo "sslmode:     verify-full"
echo "sslrootcert: $DB_TUNNEL_ROOT_CERT"
echo "example:     psql \"postgresql://<role>@localhost:$DB_TUNNEL_PORT/<database>?sslmode=verify-full&sslrootcert=$DB_TUNNEL_ROOT_CERT\""
echo "Ctrl+C closes the tunnel."
# Polling the tunnel process also ends the wait if the tunnel dies on its own.
while kill -0 "$DB_TUNNEL_PID" 2>/dev/null; do sleep 1; done
echo "the tunnel process ended" >&2
exit 1
