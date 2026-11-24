#!/bin/sh
# Write the nginx maps that decide whether a request came through Cloudflare.
#
# The nginx image runs this script before it starts nginx. Cloudflare adds the shared
# secret as the X-Origin-Verify request header (a Transform Rule), and the server in
# nginx.conf answers 403 to a request for which $origin_allowed is 0. This script builds
# that variable from the runtime environment, using the variables the API reads:
#   CLOUDFLARE_ORIGIN_SECRET           the current value; empty switches the check off, but
#                                      only outside Railway
#   CLOUDFLARE_ORIGIN_SECRET_PREVIOUS  accepted too during a rotation; empty means none
# A value is 32 to 128 characters of A-Z, a-z, 0-9, "_" and "-" (the API's secrets are
# URL-safe base64). Anything else stops the container. nginx reads a map key that starts
# with "~" as a regex and matches other keys without regard to case, so each key is written
# as an anchored, case-sensitive regex, and the restricted characters need no escaping.
# Railway injects RAILWAY_ENVIRONMENT_NAME into every deployment, and there a missing
# secret stops the container, as the API refuses to start on a deploy without it. So does
# a previous value with no current one. One request needs no secret: GET /healthz, the
# health path, addressed to healthcheck.railway.app, which is how Railway probes a new
# deploy. The secret is never printed. The probe key is an anchored, case-sensitive regex
# for the same reason as the secret keys: a plain key would also match /HEALTHZ.
#
# ORIGIN_LOCK_CONF exists only so that a test can write somewhere else.

set -eu

out="${ORIGIN_LOCK_CONF:-/etc/nginx/conf.d/00-origin-lock.conf}"
secret="${CLOUDFLARE_ORIGIN_SECRET:-}"
previous="${CLOUDFLARE_ORIGIN_SECRET_PREVIOUS:-}"

refuse() {
    echo "origin-lock: $1" >&2
    exit 1
}

# Both arguments are the variable's name and its value; an empty value is the caller's case.
check_value() {
    case "$2" in
        *[!A-Za-z0-9_-]*)
            refuse "$1 may hold only the characters A-Z, a-z, 0-9, _ and -"
            ;;
    esac
    if [ "${#2}" -lt 32 ] || [ "${#2}" -gt 128 ]; then
        refuse "$1 must be 32 to 128 characters long"
    fi
}

export LC_ALL=C
if [ -z "$secret" ]; then
    if [ -n "${RAILWAY_ENVIRONMENT_NAME:-}" ]; then
        refuse "CLOUDFLARE_ORIGIN_SECRET is required on Railway"
    fi
    if [ -n "$previous" ]; then
        refuse "CLOUDFLARE_ORIGIN_SECRET_PREVIOUS is set without CLOUDFLARE_ORIGIN_SECRET"
    fi
else
    check_value CLOUDFLARE_ORIGIN_SECRET "$secret"
fi
if [ -n "$previous" ]; then
    check_value CLOUDFLARE_ORIGIN_SECRET_PREVIOUS "$previous"
fi

umask 077
{
    echo "# Generated at container start by 40-origin-lock.sh. Do not edit."
    echo 'map $http_x_origin_verify $origin_secret_ok {'
    if [ -z "$secret" ]; then
        echo "    default 1;"
    else
        echo "    default 0;"
        printf '    "~^%s$" 1;\n' "$secret"
        # A repeated key is an nginx error.
        if [ -n "$previous" ] && [ "$previous" != "$secret" ]; then
            printf '    "~^%s$" 1;\n' "$previous"
        fi
    fi
    echo "}"
    echo 'map "$request_method $host$request_uri" $origin_probe {'
    echo "    default 0;"
    echo '    "~^GET healthcheck\.railway\.app/healthz$" 1;'
    echo "}"
    echo 'map "$origin_secret_ok$origin_probe" $origin_allowed {'
    echo "    default 1;"
    echo '    "00" 0;'
    echo "}"
} > "$out"

if [ -z "$secret" ]; then
    echo "origin-lock: off, CLOUDFLARE_ORIGIN_SECRET is not set"
else
    echo "origin-lock: on"
fi
