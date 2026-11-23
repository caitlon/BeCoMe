#!/bin/sh
# Write the nginx maps that decide whether a request came through Cloudflare.
#
# The nginx image runs this script before it starts nginx. Cloudflare adds the shared
# secret as the X-Origin-Verify request header (a Transform Rule), and the server in
# nginx.conf answers 403 to a request for which $origin_allowed is 0. This script builds
# that variable from the runtime environment, using the variables the API reads:
#   CLOUDFLARE_ORIGIN_SECRET           the current value; unset or empty switches the check off
#   CLOUDFLARE_ORIGIN_SECRET_PREVIOUS  accepted too during a rotation; empty means none
# One request needs no secret: GET / addressed to healthcheck.railway.app, which is how
# Railway probes a new deploy. A value nginx could not hold in a quoted string stops the
# container instead of opening or closing the site. The secret is never printed.
#
# ORIGIN_LOCK_CONF exists only so that a test can write somewhere else.

set -eu

out="${ORIGIN_LOCK_CONF:-/etc/nginx/conf.d/00-origin-lock.conf}"
secret="${CLOUDFLARE_ORIGIN_SECRET:-}"
previous="${CLOUDFLARE_ORIGIN_SECRET_PREVIOUS:-}"

# Accept printable ASCII without a space, minus the characters nginx reads inside quotes.
check_value() {
    case "$2" in
        *[!!-~]*|*'"'*|*'\'*|*'$'*|*';'*)
            echo "origin-lock: $1 has a character that cannot go into the nginx config" >&2
            exit 1
            ;;
    esac
    if [ "${#2}" -gt 128 ]; then
        echo "origin-lock: $1 is longer than 128 characters" >&2
        exit 1
    fi
}

export LC_ALL=C
check_value CLOUDFLARE_ORIGIN_SECRET "$secret"
check_value CLOUDFLARE_ORIGIN_SECRET_PREVIOUS "$previous"

umask 077
{
    echo "# Generated at container start by 40-origin-lock.sh. Do not edit."
    echo "map_hash_bucket_size 256;"
    echo 'map $http_x_origin_verify $origin_secret_ok {'
    if [ -z "$secret" ]; then
        echo "    default 1;"
    else
        echo "    default 0;"
        echo "    \"$secret\" 1;"
        # An empty key would match a request without the header, and a repeated key
        # is an nginx error.
        if [ -n "$previous" ] && [ "$previous" != "$secret" ]; then
            echo "    \"$previous\" 1;"
        fi
    fi
    echo "}"
    echo 'map "$request_method $host$request_uri" $origin_probe {'
    echo "    default 0;"
    echo '    "GET healthcheck.railway.app/" 1;'
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
