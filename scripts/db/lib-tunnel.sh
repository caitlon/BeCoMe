# Sourced by scripts/db/*.sh, never run on its own.
#
# Opens an SSH tunnel to a Railway Postgres service and exports the libpq settings that
# verify the server certificate against that database's own root CA. No public TCP proxy
# is created. The root is fetched over `railway ssh` on every run and never pinned in the
# repository: the postgres-ssl image regenerates it on a restore, near expiry and on a
# volume rebuild, so a stored copy would go stale. The server certificate always carries
# DNS:localhost, which is why the connection goes to `localhost` and not to 127.0.0.1.
#
# The tunnel lands on the container's loopback, where pg_hba says `trust`: while it is open
# any local process can connect as any role without a password. Open it only for a run,
# on an ephemeral port, and close it on exit (db_tunnel_close, from an EXIT trap).
#
# Messages go to stderr so that a command run through the tunnel keeps a clean stdout.

DB_TUNNEL_PID=""
DB_TUNNEL_DIR=""
DB_TUNNEL_PORT=""
DB_TUNNEL_ROOT_CERT=""
DB_TUNNEL_PROJECT_ID=""

# A plain connect, not lsof: it needs no extra tool and works as the readiness probe too.
_tunnel_listening() { ( exec 3<>"/dev/tcp/127.0.0.1/$1" ) 2>/dev/null; }

_tunnel_wait_exit() {  # $1 = pid, $2 = number of 0.2 s polls
  local i
  for i in $(seq 1 "$2"); do kill -0 "$1" 2>/dev/null || return 0; sleep 0.2; done
  ! kill -0 "$1" 2>/dev/null
}

# Reports, then tears down whatever got opened so far, so a half-open state never leaks.
_tunnel_fail() { echo "db tunnel: $*" >&2; db_tunnel_close; return 1; }

db_tunnel_open() {  # $1 = dev|prod, $2 = service name ("<env>-db", "<env>-vector")
  local env="${1:-}" svc="${2:-}" help port root pem subject i up=""
  case "$env" in dev|prod) ;; *) echo "db tunnel: environment must be dev or prod, got '$env'" >&2; return 1 ;; esac
  case "$svc" in
    *[!A-Za-z0-9-]*) svc="" ;;
    "$env"-?*) ;;
    *) svc="" ;;
  esac
  [ -n "$svc" ] || { echo "db tunnel: service must be named ${env}-<name>, got '${2:-}'" >&2; return 1; }
  [ -z "$DB_TUNNEL_PID" ] || { echo "db tunnel: a tunnel is already open (pid $DB_TUNNEL_PID)" >&2; return 1; }

  command -v railway >/dev/null 2>&1 || { echo "db tunnel: the Railway CLI is not installed" >&2; return 1; }
  help=$(railway connect --help 2>&1)
  case "$help" in
    *--tunnel-only*) ;;
    *) echo "db tunnel: this Railway CLI has no 'connect --tunnel-only' (needs 5.71 or newer): brew upgrade railway" >&2; return 1 ;;
  esac
  for i in jq openssl python3; do
    command -v "$i" >/dev/null 2>&1 || { echo "db tunnel: $i is required but not installed" >&2; return 1; }
  done

  DB_TUNNEL_PROJECT_ID="${RAILWAY_PROJECT_ID:-$(railway status --json 2>/dev/null | jq -r '.id // empty')}"
  [ -n "$DB_TUNNEL_PROJECT_ID" ] || { echo "db tunnel: set RAILWAY_PROJECT_ID, or run 'railway link' in this repo first" >&2; return 1; }

  DB_TUNNEL_DIR=$(mktemp -d "${TMPDIR:-/tmp}/db-tunnel.XXXXXX") || return 1
  chmod 700 "$DB_TUNNEL_DIR"
  root="$DB_TUNNEL_DIR/root.crt"

  # With no running instance the gateway answers with a help blob and exit 0, so the output
  # is cut down to the PEM block and the subject checked before it is trusted as a root.
  pem=$(railway ssh -p "$DB_TUNNEL_PROJECT_ID" -e "$env" -s "$svc" 'cat /var/lib/postgresql/data/certs/root.crt' 2>/dev/null \
    | sed -n '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/p')
  printf '%s\n' "$pem" > "$root"
  subject=$(openssl x509 -in "$root" -noout -subject 2>/dev/null | tr -d ' ')
  case "$subject" in
    *CN=root-ca) ;;
    *) _tunnel_fail "could not read the root certificate of $svc. Is the service running (a deployment that 'railway deployment list' shows as SLEEPING wakes on a private-network request, not on SSH), and is an SSH key registered ('railway ssh keys add')?"; return 1 ;;
  esac
  echo "db tunnel: root CA sha256 $(openssl x509 -in "$root" -noout -fingerprint -sha256 | sed 's/.*=//'), notAfter $(openssl x509 -in "$root" -noout -enddate | sed 's/.*=//')" >&2

  port=$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
  DB_TUNNEL_PORT="$port"
  # The details it prints may include credentials, so they go to a file in the private dir.
  railway connect "$svc" -p "$DB_TUNNEL_PROJECT_ID" -e "$env" --tunnel-only --port "$port" > "$DB_TUNNEL_DIR/tunnel.log" 2>&1 &
  DB_TUNNEL_PID=$!
  for i in $(seq 1 150); do
    kill -0 "$DB_TUNNEL_PID" 2>/dev/null || { _tunnel_fail "the tunnel process exited before it was ready. Run 'railway connect $svc -p $DB_TUNNEL_PROJECT_ID -e $env --tunnel-only' by hand to see why."; return 1; }
    if _tunnel_listening "$port"; then up=1; break; fi
    sleep 0.2
  done
  [ -n "$up" ] || { _tunnel_fail "the tunnel did not listen on 127.0.0.1:$port within 30 s. Run 'railway connect $svc -p $DB_TUNNEL_PROJECT_ID -e $env --tunnel-only' by hand to see why."; return 1; }

  export DB_TUNNEL_PORT DB_TUNNEL_ROOT_CERT="$root"
  export PGHOST=localhost PGPORT="$port" PGSSLMODE=verify-full PGSSLROOTCERT="$root"
  echo "db tunnel: $svc open on localhost:$port. While it is open, any local process can connect without a password." >&2
}

db_tunnel_close() {  # idempotent; safe in an EXIT trap even when db_tunnel_open failed halfway
  local pid="${DB_TUNNEL_PID:-}"
  if [ -n "$pid" ]; then
    if kill -0 "$pid" 2>/dev/null; then
      kill -INT "$pid" 2>/dev/null
      _tunnel_wait_exit "$pid" 15 || { kill -TERM "$pid" 2>/dev/null; _tunnel_wait_exit "$pid" 10; }
    fi
    if kill -0 "$pid" 2>/dev/null; then
      echo "db tunnel: WARNING: the tunnel process $pid is still running. Kill it by hand: kill -9 $pid" >&2
    elif [ -n "${DB_TUNNEL_PORT:-}" ] && _tunnel_listening "$DB_TUNNEL_PORT"; then
      echo "db tunnel: WARNING: something still listens on 127.0.0.1:$DB_TUNNEL_PORT (tunnel pid was $pid)" >&2
    else
      wait "$pid" 2>/dev/null
      echo "db tunnel: closed" >&2
    fi
  fi
  case "${DB_TUNNEL_DIR:-}" in */db-tunnel.*) rm -rf "$DB_TUNNEL_DIR" ;; esac
  # The libpq variables exist only after a successful open; leave a caller's own alone.
  [ -z "${DB_TUNNEL_ROOT_CERT:-}" ] || unset PGHOST PGPORT PGSSLMODE PGSSLROOTCERT
  DB_TUNNEL_PID=""; DB_TUNNEL_DIR=""; DB_TUNNEL_PORT=""; DB_TUNNEL_ROOT_CERT=""
  return 0
}
