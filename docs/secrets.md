# Secrets

Every secret the deployed services use, where it comes from, and how to replace it. This is
an operations runbook: it lists names, sources and procedures, never values. Why each secret
exists and what the application does with it is in [`security.md`](security.md). The
variables of each environment are in [`environments.md`](environments.md).

## Contents

- [Inventory](#inventory)
- [CI secrets](#ci-secrets)
- [Variables that are not secrets](#variables-that-are-not-secrets)
- [Rotation rules](#rotation-rules)
- [Rotation procedures](#rotation-procedures)
    - [Checking credentials from the container](#checking-credentials-from-the-container)
    - [SECRET_KEY](#secret_key)
    - [CLOUDFLARE_ORIGIN_SECRET](#cloudflare_origin_secret)
    - [Database and Redis credentials](#database-and-redis-credentials)
    - [Provider-issued keys](#provider-issued-keys)
    - [Bucket credentials](#bucket-credentials)
    - [GitHub Actions secrets](#github-actions-secrets)

## Inventory

The backend reads these in `api/config.py` and nowhere else, except the three password
variables at the end of the table. Those sit on the database, Redis and corpus services. The
backend reaches them only through the references in `MIGRATION_DATABASE_URL`, `REDIS_URL` and
`ASSISTANT_VECTOR_DB_URL`, and never holds the corpus owner's `POSTGRES_PASSWORD`, which only
ingest uses. `migrations/env.py` also reads `ALEMBIC_DATABASE_URL`, which
overrides `MIGRATION_DATABASE_URL` ([`environments.md`](environments.md)), so keep it unset
on deployed services. The "Verify" column says how to check a value without printing it.
A check with `curl` reads the key from a file, as the rotation rules below describe.
`<env>` stands for `dev`, `test` or `prod`.

| Variable | What it protects | Source | Verify |
|----------|------------------|--------|--------|
| `SECRET_KEY` | Signs session JWTs (`api/auth/jwt.py`) and keys the CSRF token (`api/auth/cookies.py`). While `LOG_HASH_KEY` is unset it also keys the email hashes in logs. A deployed service refuses to start with fewer than 32 characters | Created by us | Hash in the container, see [SECRET_KEY](#secret_key) |
| `CLOUDFLARE_ORIGIN_SECRET` | Proves a request came through Cloudflare, so `CF-Connecting-IP` can be trusted for rate limiting (`api/utils/client_ip.py`) | Created by us | Hash in the container against the hash of the rule value, see [CLOUDFLARE_ORIGIN_SECRET](#cloudflare_origin_secret) |
| `DATABASE_URL` | Password of the `become_app` role | Railway Postgres of the environment | In-container connection with the backend's own `DATABASE_URL` |
| `MIGRATION_DATABASE_URL` | Password of the owner role, used by Alembic only | Railway Postgres of the environment | In-container connection with the backend's own `MIGRATION_DATABASE_URL` |
| `REDIS_URL` | Access to the revocation and rate-limit store | Reference to the Railway Redis of the environment | In-container `PING` with the backend's own `REDIS_URL` |
| `EMAIL_API_KEY` | Sending mail through Resend | Resend, API Keys, permission "Sending access" restricted to the sending domain | `GET https://api.resend.com/domains` with the key. A sending-only key answers `401` `restricted_api_key`, which proves it is valid and restricted |
| `TURNSTILE_SECRET_KEY` | Server-side check of the bot-check token | Cloudflare dashboard, Turnstile, the widget | POST to the Turnstile `siteverify` endpoint with the secret and a dummy token. `invalid-input-response` means the secret is right, `invalid-input-secret` means it is wrong |
| `BUCKET_ACCESS_KEY_ID`, `BUCKET_SECRET_ACCESS_KEY` | Read and write access to the profile-photo bucket | Railway Bucket `<env>-photos` | S3 `list_objects_v2` with the backend's own variables |
| `BETTERSTACK_SOURCE_TOKEN` | Writing logs to a Better Stack source | Better Stack log source of the environment, EU region | Logs from the current container arrive |
| `SENTRY_DSN` | Sending backend events to Sentry. The key can only write events | Sentry, the backend project, client key | Events from the backend arrive in Sentry |
| `ASSISTANT_API_KEY_OVH` | Hosted model calls on OVHcloud AI Endpoints | OVHcloud | `GET https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/models` with the bearer key answers `200`. The endpoint also answers `200` with no key, so the result counts only next to a control request with a wrong key that answers `403` |
| `ASSISTANT_LANGSMITH_API_KEY` | Sending assistant traces to LangSmith (EU) | LangSmith | `GET https://eu.api.smith.langchain.com/api/v1/sessions?limit=1` with the `x-api-key` header answers `200` |
| `ASSISTANT_VECTOR_DB_URL` | Password of the read-only `corpus_reader` role on the corpus database | Reference to `CORPUS_READER_PASSWORD` on the `<env>-vector` service | In-container connection with the backend's own `ASSISTANT_VECTOR_DB_URL` |
| `POSTGRES_PASSWORD` | Password of the owner role on the `<env>-db` service (`postgres`) and on the `<env>-vector` service. `MIGRATION_DATABASE_URL` references the one on `<env>-db` | Railway Postgres of the environment | On `<env>-db`, the same check as `MIGRATION_DATABASE_URL`. On `<env>-vector`, the hash check of the Postgres steps and the next ingest |
| `REDIS_PASSWORD` | Password the `<env>-redis` service demands (`--requirepass`). `REDIS_URL` references it | Railway Redis of the environment | Same check as `REDIS_URL`, plus the hash of the value in the Redis container, see [Redis](#redis) |
| `CORPUS_READER_PASSWORD` | Password of `corpus_reader` on the `<env>-vector` service. `ASSISTANT_VECTOR_DB_URL` references it | Railway Postgres of the corpus service | Same check as `ASSISTANT_VECTOR_DB_URL` |

Two variables are optional and are not covered above. `LOG_HASH_KEY` is the key for the
email tags in security logs (`api/auth/logging.py`). When it is unset the code uses
`SECRET_KEY`, so every `SECRET_KEY` rotation re-tags all later records. Set it separately
to keep tags comparable across a rotation. The other is `BUCKET_REGION`, which is not a
secret. The frontend variable `VITE_TURNSTILE_SITE_KEY` is public and does not change when
the secret rotates.

`VITE_SENTRY_DSN` is a frontend build argument and ships in the bundle, so that DSN is
effectively public. `SENTRY_DSN` is a separate key of the backend Sentry project, read on
the server only (`api/config.py`). Like any DSN it can only send events. Nothing rotates
either on a schedule. To rotate the backend one, create a new client key in the Sentry
project, set `SENTRY_DSN` with `--stdin --skip-deploys`, redeploy the backend once, then
disable the old key.

## CI secrets

These are GitHub Actions secrets of the repository, not Railway variables. The list comes
from `secrets.*` in `.github/workflows/`.

| Secret | Used by | Source |
|--------|---------|--------|
| `SONAR_TOKEN` | The SonarCloud job in `ci.yml` | SonarCloud |
| `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | The publish job in `docs.yml`, which deploys the site to Cloudflare Pages | Cloudflare |
| `SEMGREP_APP_TOKEN` | `semgrep.yml`, which sends scan results to the Semgrep AppSec Platform | Semgrep AppSec Platform |
| `GITHUB_TOKEN` | `pr-size.yml` | Issued by GitHub for each run, nothing to rotate |

## Variables that are not secrets

`BUCKET_NAME`, `BUCKET_ENDPOINT`, `BUCKET_REGION`, `BETTERSTACK_INGESTING_HOST`,
`EMAIL_API_URL`, `API_PUBLIC_URL`,
`FRONTEND_BASE_URL`, `CORS_ORIGINS`, `TURNSTILE_HOSTNAMES` and the `ASSISTANT_*` base URLs
and model names are plain configuration. They sit next to the secrets in Railway but need no
special handling.

## Rotation rules

- Never print a value. Not in a terminal, not in a log, not in a chat.
- Start each procedure with `umask 077; S="$(mktemp -d)"` in the shell that sits in the
  linked checkout. Keep every value file in `"$S"` and finish with `rm -rf "$S"`. The
  directory lies outside the checkout, so `git add` cannot stage a plaintext value. Do not
  `cd` into it, because the Railway CLI finds the linked project by the working directory.
- Set a Railway variable with `railway variable set KEY --stdin --skip-deploys`, so the value
  comes from standard input, stays out of the shell history and the process list, and does
  not start a deploy of its own. `set` deploys by default, which would make every procedure
  below deploy twice. The one exception is the Redis password, see [Redis](#redis). Feed
  `--stdin` from a file or a pipe, for example `pbpaste | railway variable set KEY --stdin ...`,
  never by pasting into a prompt that echoes what you type.
- Batch the changes of one environment: set every variable with `--skip-deploys`, then
  redeploy the backend once with `railway redeploy -y -s <env>-backend -e <env>`. The Redis
  password deploys its own service first, see [Redis](#redis).
- In a `curl` check, pass the key from a file, never in the arguments: `-H @file` for a
  header, `--data-urlencode secret@file` for a form field. Arguments show up in the process
  list and the shell history.
- Compare an old and a new value by hash, for example `shasum -a 256`, never by eye.
- Write every value file with `printf '%s'` or `print(..., end="")`, so it has no trailing
  newline. Railway's `--stdin` trims every trailing newline, but `jq --rawfile`,
  `--data-urlencode secret@file` and the hash compare do not.
- Do prod only on the owner's explicit go.
- `GET /api/v1/health` proves only that the process started. It touches neither the
  database nor Redis, and a failed database warm-up at startup is logged, not fatal, so
  health answers `200` with a wrong password. Check a database or Redis credential from
  inside the new container, as described next.
- Cloudflare answers `403` to the default `Python-urllib` User-Agent. Check hosts with
  `curl` or set a custom User-Agent.

## Rotation procedures

### Checking credentials from the container

After the redeploy, save the script below as `"$S/check.py"` and run it inside the new backend
container with `railway ssh -e <env> -s <env>-backend python - < "$S/check.py"`. It connects with
the variables the container itself holds and prints variable names and, on a failure, the
exception type only, because the message of a malformed URL can echo the password. The
production image has `psycopg2`, `redis` and `boto3`, and no `psycopg` 3, which arrives with
the assistant extra.

```python
import os
import re

import boto3
import psycopg2
import redis
from botocore.config import Config


def check(name, probe, *args):
    try:
        probe(*args)
    except Exception as e:
        print(name, "failed", type(e).__name__)
    else:
        print(name, "ok")


def connect(name):
    psycopg2.connect(re.sub(r"\+psycopg2?", "", os.environ[name])).close()


def ping():
    redis.from_url(os.environ["REDIS_URL"]).ping()


def list_bucket():
    boto3.client(
        "s3",
        endpoint_url=os.environ["BUCKET_ENDPOINT"],
        aws_access_key_id=os.environ["BUCKET_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["BUCKET_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("BUCKET_REGION", "auto"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    ).list_objects_v2(Bucket=os.environ["BUCKET_NAME"], MaxKeys=1)


for name in ("DATABASE_URL", "MIGRATION_DATABASE_URL", "ASSISTANT_VECTOR_DB_URL"):
    if os.environ.get(name):
        check(name, connect, name)
check("REDIS_URL", ping)
if os.environ.get("BUCKET_NAME"):
    check("BUCKET_ACCESS_KEY_ID", list_bucket)
```

Two weaker signals support it. The new container's log has the `db_warmup` event and not
`db_warmup_failed`, and one login works. Neither replaces the connection test.

### SECRET_KEY

The application takes one `SECRET_KEY`. There is no window where two keys are accepted.

Any random value of at least 32 characters works, and the startup guard enforces that
floor.

1. Record the hash of the value the running container holds:
   `railway ssh -e <env> -s <env>-backend -- sh -c 'printf %s "$SECRET_KEY" | sha256sum'`.
   The container's shell expands `$SECRET_KEY`, so the value itself never leaves it.
2. Generate a value and pipe it straight into Railway, so it never reaches the terminal:
   `python -c 'import secrets; print(secrets.token_urlsafe(64))' | railway variable set SECRET_KEY --stdin --skip-deploys -s <env>-backend -e <env>`.
3. Redeploy the backend once.
4. Run the command of step 1 against the new container. The hash must differ from the old
   one. Check health to confirm the process started, then log in once to confirm a new
   session starts.

Every existing session ends and every user logs in again. Links in emails (verification and
password reset) are random tokens stored hashed in the database, not JWTs, so they keep
working. If `LOG_HASH_KEY` is unset, email tags in logs change too.

### CLOUDFLARE_ORIGIN_SECRET

The variable and the Transform Rule on the environment's API host must hold the same value.
The rule runs in the `http_request_late_transform` phase and sets `X-Origin-Verify`. The API
hosts under `becomify.app` are `api` (prod), `api-atelier` (dev) and `api-harbor` (test).

The value goes to two places, so it needs a holder that is not the terminal. Write the
generated value into `"$S/origin.secret"`. Feed the file to Railway on standard input. Build
the rule `PATCH` body from the same file, for example with `jq --rawfile`, so the value never
appears on the command line. Never echo it.

1. Generate a random value into that file, without a trailing newline.
2. Set `CLOUDFLARE_ORIGIN_SECRET` on the backend with `--stdin --skip-deploys`, reading the
   file.
3. Redeploy the backend once.
4. Update the rule of that host (a `PATCH` on the rule) to the same value from the file right
   away.
5. Compare three hashes, and all three must match. The zone holds one rule per API host in
   the `http_request_late_transform` entrypoint ruleset. The listing contains the secret, so
   `-o` writes it to a file instead of the terminal, and `"$S/cf.header"` holds the
   `Authorization: Bearer ...` line for the Cloudflare API token, written with `printf '%s'`
   like any value file:

   ```sh
   curl -s -H @"$S/cf.header" -o "$S/rule.json" \
     "https://api.cloudflare.com/client/v4/zones/<zone_id>/rulesets/phases/http_request_late_transform/entrypoint"
   ```

   Then compute each hash:

   ```sh
   railway ssh -e <env> -s <env>-backend -- sh -c 'printf %s "$CLOUDFLARE_ORIGIN_SECRET" | sha256sum'
   shasum -a 256 < "$S/origin.secret"
   jq -j '.result.rules[] | select(.expression | contains("\"<host>\"")) | .action_parameters.headers["X-Origin-Verify"].value' "$S/rule.json" | shasum -a 256
   ```

   The first line hashes the value in the container, the second the value file, the third
   the value in the rule of that host. `-j` matters, because it keeps `jq` from appending a
   newline that would change the hash. `<host>` is the full host name, for example
   `api-atelier.becomify.app`; the short label matches no rule and hashes the empty string.

On a mismatch requests are not rejected. Every request is keyed under one shared constant
for rate limiting instead, so all callers share one rate-limit bucket, which shows up as `429`
responses on a busy site. Keep the gap between steps 3 and 4 short.

### Database and Redis credentials

The Postgres service is `<env>-db`, with the application role `become_app` and the owner
`postgres`. The Redis service is `<env>-redis`, Redis 8 started with
`--requirepass $REDIS_PASSWORD`.
[`security.md`](security.md#secrets) describes a zero-downtime alternative for `become_app`
that adds a second role. After the backend redeploy, run the in-container check from
[Checking credentials from the container](#checking-credentials-from-the-container).

#### Postgres roles

1. For each role, generate a password into `"$S/<role>.password"`, with
   `python -c 'import secrets; print(secrets.token_urlsafe(32), end="")'`. The password goes
   into a URL later, and `token_urlsafe` output needs no percent-encoding. Compute its SCRAM
   verifier locally, so the plaintext never reaches the database. The script below reads the
   password on standard input and writes the verifier to standard output, into
   `"$S/<role>.verifier"`. The verifier is not the password, but it allows an offline
   guess, so handle it like one:

   ```python
   import base64, hashlib, hmac, os, sys

   password = sys.stdin.read().strip().encode()
   salt, rounds = os.urandom(16), 4096
   salted = hashlib.pbkdf2_hmac("sha256", password, salt, rounds)
   client_key = hmac.new(salted, b"Client Key", "sha256").digest()
   server_key = hmac.new(salted, b"Server Key", "sha256").digest()


   def b64(raw):
       return base64.b64encode(raw).decode()


   stored_key = hashlib.sha256(client_key).digest()
   print(
       f"SCRAM-SHA-256${rounds}:{b64(salt)}${b64(stored_key)}:{b64(server_key)}",
       end="",
   )
   ```

2. Write `"$S/roles.sql"` from the verifier files. The database logs DDL statements
   ([`security.md`](security.md#audit-logging)). The first line switches that off for the
   session. The second covers failing statements: at the default
   `log_min_error_statement = error`, Postgres logs a failing statement with its text,
   verifier included, whatever `log_statement` says. The third covers slow statements: at
   the production `log_min_duration_statement` threshold, a slow `ALTER ROLE` would be
   logged with its text, verifier included:

   ```sh
   {
     printf '%s\n' "SET log_statement = 'none';"
     printf '%s\n' "SET log_min_error_statement = 'panic';"
     printf '%s\n' "SET log_min_duration_statement = -1;"
     printf "ALTER ROLE become_app PASSWORD '%s';\n" "$(cat "$S/become_app.verifier")"
     printf "ALTER ROLE postgres PASSWORD '%s';\n" "$(cat "$S/postgres.verifier")"
   } > "$S/roles.sql"
   ```

3. Feed it to `psql` in the database container over the local socket, which admits the
   owner without a password. Nothing is typed or echoed. In the container `PGHOST` points
   to the internal TCP address and `PGPASSWORD` holds the password from container start.
   That password stops working once the owner's password changes, so both are unset:

   ```sh
   railway ssh -e <env> -s <env>-db env -u PGHOST -u PGPASSWORD \
     psql -h /var/run/postgresql -U postgres -d railway < "$S/roles.sql"
   ```

4. Confirm by hash. Put this query, which holds no secret, in `"$S/check.sql"`:
   `SELECT rolname, encode(sha256(convert_to(rolpassword, 'UTF8')), 'hex') FROM pg_authid WHERE rolname IN ('become_app', 'postgres') ORDER BY rolname;`
   Run it the same way as step 3 with `< "$S/check.sql"` and compare each hash with
   `shasum -a 256` of the matching verifier file. The output of `ALTER ROLE` through
   `railway ssh` is sometimes cut short, so it proves nothing.
5. Build the new `become_app` URL in `"$S/become_app.url"`, from the password file and the
   non-secret parts of the current `DATABASE_URL` (host, port, database and any query
   string). This command prints them with the credentials masked:

   ```sh
   railway ssh -e <env> -s <env>-backend -- sh -c 'printf "%s\n" "$DATABASE_URL" | sed "s#//[^@]*@#//***@#"'
   ```

   If its scheme differs from `postgresql`, use that scheme in the template below:

   ```sh
   printf '%s%s@%s' 'postgresql://become_app:' "$(cat "$S/become_app.password")" \
     '<host>:<port>/<database>' > "$S/become_app.url"
   ```

   `printf` is a shell builtin, so the password stays out of the process list. Set the
   backend's `DATABASE_URL`, a literal, with `railway variable set DATABASE_URL --stdin
   --skip-deploys -s <env>-backend -e <env> < "$S/become_app.url"`. Set `POSTGRES_PASSWORD` on
   `<env>-db` from `"$S/postgres.password"` the same way, so the database does not restart.
   `MIGRATION_DATABASE_URL` references it and picks it up on the redeploy.
6. Redeploy the backend once, right away. New connections with the old `become_app`
   password fail until then.

#### Redis

1. Generate the password into `"$S/redis.password"` with
   `python -c 'import secrets; print(secrets.token_hex(32), end="")'`. Hex output never
   starts with `-`, so Redis cannot read the value as an option of `--requirepass`, and it
   needs no percent-encoding in `REDIS_URL`.
2. Set `REDIS_PASSWORD` on the Redis service without `--skip-deploys`:
   `railway variable set REDIS_PASSWORD --stdin -s <env>-redis -e <env> < "$S/redis.password"`.
   Railway starts a new Redis deployment with the new value, and Redis is unavailable for a
   few seconds. The data stays on the service's `/data` volume. This works the same whether
   or not the service is asleep.
3. Wait until that deployment shows `SUCCESS` in
   `railway deployment list -s <env>-redis -e <env>`. Then redeploy the backend, because
   `REDIS_URL` references the Redis service.
4. Check that the Redis container runs with the new value. The hash from
   `railway ssh -e <env> -s <env>-redis -- sh -c 'printf %s "$REDIS_PASSWORD" | sha256sum'`
   must equal `shasum -a 256 < "$S/redis.password"`. Then run the in-container check from the
   backend, which prints `REDIS_URL ok`.

Never change the password only on the running server (`CONFIG SET requirepass`, with the
variable set under `--skip-deploys`). The running deployment keeps the old value in its
environment, and the next restart or wake from App Sleep brings the old password back.

From the Redis restart until the backend runs with the new password, new connections to
Redis are refused. The revocation store fails closed: authenticated requests answer `401`,
and login, refresh and logout answer `503` (see [`security.md`](security.md)). Redeploy the
backend right away.

#### Corpus database

Where the environment has a corpus service, follow the Postgres steps with these changes:

1. The service is `<env>-vector`. The roles are `corpus_reader` and the service's owner, the
   user named by its `POSTGRES_USER` variable. Read it with
   `railway ssh -e <env> -s <env>-vector printenv POSTGRES_USER`, not with
   `railway variable list`, which prints every value of the service.
2. In the `psql` command, pass the owner as `-U` and the database named by `POSTGRES_DB` of
   that service as `-d`, in place of `postgres` and `railway`. In `"$S/roles.sql"` and in the
   `rolname IN (...)` list of the hash check, name `corpus_reader` and the owner in place of
   `become_app` and `postgres`.
3. Skip the `DATABASE_URL` step. `ASSISTANT_VECTOR_DB_URL` references
   `CORPUS_READER_PASSWORD`, so the backend redeploy picks it up.
4. Set `CORPUS_READER_PASSWORD` and the service's `POSTGRES_PASSWORD` with
   `--stdin --skip-deploys`.
5. The next ingest connects as the owner
   ([`api/assistant/README.md`](https://github.com/caitlon/BeCoMe/blob/prod/api/assistant/README.md#read-only-role-for-a-deployed-corpus-database)),
   so use the new owner password in the `ASSISTANT_VECTOR_DB_URL` of that run.

### Provider-issued keys

This covers `EMAIL_API_KEY`, `TURNSTILE_SECRET_KEY`, `ASSISTANT_API_KEY_OVH` and
`ASSISTANT_LANGSMITH_API_KEY`.

1. Create the new key at the provider.
2. Find every environment that holds the old key by comparing the hash of the variable in
   each backend:
   `railway ssh -e <env> -s <env>-backend -- sh -c 'printf %s "$<VARIABLE>" | sha256sum'`
   for `dev`, `test` and `prod`. Equal hashes mean a shared key, and revoking it in the
   last step breaks every environment that still holds it.
3. Set the variable with `--stdin --skip-deploys` on every environment that shares the old
   key, before the next step.
4. Redeploy the backend of each of those environments once.
5. Check the new key as in the inventory table.
6. Revoke the old key at the provider.

Per provider:

- **Resend.** Give the key "Sending access", restricted to the sending domain.
- **Turnstile.** The project's Cloudflare API token has no Turnstile permission, so rotate in
  the dashboard: open Turnstile, the widget, and rotate the secret key. Keep the grace period,
  so the old secret still works while services switch, and it needs no revoking in step 6. The
  site key `VITE_TURNSTILE_SITE_KEY` stays.
- **LangSmith.** The key matters only where tracing is on.

### Bucket credentials

Railway can also change a bucket's secret on its own. The symptom is photos failing with
`SignatureDoesNotMatch`. Compare the backend variables with the output of
`railway bucket credentials --json` by hash. Both print the keys, so send the output to
`"$S/bucket.json"`, never to the terminal.

1. Run `railway bucket credentials --reset --yes --json -b <env>-photos -e <env>` with its
   output redirected into that file. The old pair stops working at once. When the account
   has two-factor authentication on, the command asks for a code. Without an interactive
   terminal it fails unless you add `--2fa-code <code>`.
2. Set `BUCKET_ACCESS_KEY_ID` and `BUCKET_SECRET_ACCESS_KEY` on the backend right away.
   `--stdin` takes a single key, so this is two `railway variable set KEY --stdin
   --skip-deploys` calls, each fed with `jq -r` from the matching field of that file. The
   backend holds them as literal values.
3. Redeploy the backend once. Photos fail from the reset until this redeploy finishes, so do
   steps 1 to 3 without a pause.
4. Run the in-container check from [Checking credentials from the
   container](#checking-credentials-from-the-container). It lists one object with the
   backend's own bucket variables.

### GitHub Actions secrets

Replace the value in the repository's Actions secrets, then re-run the job that uses it.
Revoke the old token at the provider afterwards.
