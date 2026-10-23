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
variables at the end of the table. Those sit on the database, Redis and corpus services and
reach the backend only through the references in `MIGRATION_DATABASE_URL`, `REDIS_URL` and
`ASSISTANT_VECTOR_DB_URL`. `migrations/env.py` also reads `ALEMBIC_DATABASE_URL`, which
overrides `MIGRATION_DATABASE_URL` ([`environments.md`](environments.md)), so keep it unset
on deployed services. The "Verify" column says how to check a value without printing it.
A check with `curl` reads the key from a file, as the rotation rules below describe.
`<env>` stands for `dev`, `test` or `prod`.

| Variable | What it protects | Source | Scope | Verify |
|----------|------------------|--------|-------|--------|
| `SECRET_KEY` | Signs session JWTs (`api/auth/jwt.py`) and keys the CSRF token (`api/auth/cookies.py`). While `LOG_HASH_KEY` is unset it also keys the email hashes in logs. A deployed service refuses to start with fewer than 32 characters | Created by us | One per environment | Hash compare |
| `CLOUDFLARE_ORIGIN_SECRET` | Proves a request came through Cloudflare, so `CF-Connecting-IP` can be trusted for rate limiting (`api/utils/client_ip.py`) | Created by us | One per environment, paired with a Transform Rule on that environment's API host | Hash compare against the rule value |
| `DATABASE_URL` | Password of the `become_app` role | Railway Postgres of the environment | One per environment | In-container connection with the backend's own `DATABASE_URL` |
| `MIGRATION_DATABASE_URL` | Password of the owner role, used by Alembic only | Railway Postgres of the environment | One per environment | In-container connection with the backend's own `MIGRATION_DATABASE_URL` |
| `REDIS_URL` | Access to the revocation and rate-limit store | Reference to the Railway Redis of the environment | One per environment | In-container `PING` with the backend's own `REDIS_URL` |
| `EMAIL_API_KEY` | Sending mail through Resend | Resend, API Keys, permission "Sending access" restricted to the sending domain | Prod has its own key. Dev and test share one | `GET https://api.resend.com/domains` with the key. A sending-only key answers `401` `restricted_api_key`, which proves it is valid and restricted |
| `TURNSTILE_SECRET_KEY` | Server-side check of the bot-check token | Cloudflare dashboard, Turnstile, the widget | Prod has its own widget. Dev and test share one | POST to the Turnstile `siteverify` endpoint with the secret and a dummy token. `invalid-input-response` means the secret is right, `invalid-input-secret` means it is wrong |
| `BUCKET_ACCESS_KEY_ID`, `BUCKET_SECRET_ACCESS_KEY` | Read and write access to the profile-photo bucket | Railway Bucket `<env>-photos` | One per environment | S3 `list_objects_v2` with the backend's own variables |
| `BETTERSTACK_SOURCE_TOKEN` | Writing logs to a Better Stack source | Better Stack log source of the environment, EU region | One per environment | Logs from the current container arrive |
| `SENTRY_DSN` | Sending backend events to Sentry. The key can only write events | Sentry, the backend project, client key | Per Sentry project | Events from the backend arrive in Sentry |
| `ASSISTANT_API_KEY_OVH` | Hosted model calls on OVHcloud AI Endpoints | OVHcloud | Dev and test share one. Prod will have its own | `GET https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/models` with the bearer key answers `200`. The endpoint also answers `200` with no key, so the result counts only next to a control request with a wrong key that answers `403` |
| `ASSISTANT_LANGSMITH_API_KEY` | Sending assistant traces to LangSmith (EU) | LangSmith | Needed only where tracing is on | `GET https://eu.api.smith.langchain.com/api/v1/sessions?limit=1` with the `x-api-key` header answers `200` |
| `ASSISTANT_VECTOR_DB_URL` | Password of the read-only `corpus_reader` role on the corpus database | Reference to `CORPUS_READER_PASSWORD` on the `<env>-vector` service | One per environment that has a corpus service | In-container connection with the backend's own `ASSISTANT_VECTOR_DB_URL` |
| `POSTGRES_PASSWORD` | Password of the owner role `postgres` on the `<env>-db` service. `MIGRATION_DATABASE_URL` references it | Railway Postgres of the environment | One per environment, set on the database service | Same check as `MIGRATION_DATABASE_URL` |
| `REDIS_PASSWORD` | Password the `<env>-redis` service demands (`--requirepass`). `REDIS_URL` references it | Railway Redis of the environment | One per environment, set on the Redis service | Same check as `REDIS_URL` |
| `CORPUS_READER_PASSWORD` | Password of `corpus_reader` on the `<env>-vector` service. `ASSISTANT_VECTOR_DB_URL` references it | Railway Postgres of the corpus service | One per environment that has a corpus service, set on that service | Same check as `ASSISTANT_VECTOR_DB_URL` |

Two variables are optional and are not covered above. `LOG_HASH_KEY` is the key for the
email tags in security logs (`api/auth/logging.py`). When it is unset the code uses
`SECRET_KEY`, so every `SECRET_KEY` rotation re-tags all later records. Set it separately
to keep tags comparable across a rotation. The other is `BUCKET_REGION`, which is not a
secret. The frontend variable `VITE_TURNSTILE_SITE_KEY` is public and does not change when
the secret rotates.

`BETTERSTACK_SOURCE_TOKEN` is not rotated in place. A new token comes only with a new source,
and on the current plan a new source can only be created in the `us_west` region. The
tokens stay as they are, an accepted trade-off. The token only allows writing logs.

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
| `GITHUB_TOKEN` | `pr-size.yml` | Issued by GitHub for each run, nothing to rotate |

## Variables that are not secrets

`BUCKET_NAME`, `BUCKET_ENDPOINT`, `BUCKET_REGION`, `BETTERSTACK_INGESTING_HOST`,
`EMAIL_API_URL`, `API_PUBLIC_URL`,
`FRONTEND_BASE_URL`, `CORS_ORIGINS`, `TURNSTILE_HOSTNAMES` and the `ASSISTANT_*` base URLs
and model names are plain configuration. They sit next to the secrets in Railway but need no
special handling.

## Rotation rules

- Never print a value. Not in a terminal, not in a log, not in a chat.
- Set a Railway variable with `railway variable set KEY --stdin --skip-deploys`, so the value
  comes from standard input, stays out of the shell history and the process list, and does
  not start a deploy of its own. `set` deploys by default, which would make every procedure
  below deploy twice. Feed `--stdin` from a file or a pipe, for example
  `pbpaste | railway variable set KEY --stdin ...`, never by pasting into a prompt that
  echoes what you type.
- Batch the changes of one environment: set every variable with `--skip-deploys`, then
  redeploy the backend once with `railway redeploy -y -s <env>-backend -e <env>`.
- In a `curl` check, pass the key from a file, never in the arguments: `-H @file` for a
  header, `--data-urlencode secret@file` for a form field. Arguments show up in the process
  list and the shell history.
- Compare an old and a new value by hash, for example `shasum -a 256`, never by eye.
- Write every value file with `printf '%s'` or `print(..., end="")`, so it has no trailing
  newline. Railway's `--stdin` trims one, but `jq --rawfile`, `--data-urlencode secret@file`,
  `redis-cli -x` and the hash compare do not.
- Do prod only on the owner's explicit go.
- `GET /api/v1/health` proves only that the process started. It touches neither the
  database nor Redis, and a failed database warm-up at startup is logged, not fatal, so
  health answers `200` with a wrong password. Check a database or Redis credential from
  inside the new container, as described next.
- Cloudflare answers `403` to the default `Python-urllib` User-Agent. Check hosts with
  `curl` or set a custom User-Agent.

## Rotation procedures

### Checking credentials from the container

After the redeploy, save the script below as `check.py` and run it inside the new backend
container with `railway ssh -e <env> -s <env>-backend python - < check.py`. It connects with
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
    check("BUCKET_NAME", list_bucket)
```

Two weaker signals support it. The new container's log has the `db_warmup` event and not
`db_warmup_failed`, and one login works. Neither replaces the connection test.

### SECRET_KEY

The application takes one `SECRET_KEY`. There is no window where two keys are accepted.

Any random value of at least 32 characters works, and the startup guard enforces that
floor.

1. Generate a value and pipe it straight into Railway, so it never reaches the terminal:
   `python -c 'import secrets; print(secrets.token_urlsafe(64))' | railway variable set SECRET_KEY --stdin --skip-deploys -s <env>-backend -e <env>`.
2. Redeploy the backend once.
3. Check health to confirm the process started, then log in once to confirm a new session
   starts.

Every existing session ends and every user logs in again. Links in emails (verification and
password reset) are random tokens stored hashed in the database, not JWTs, so they keep
working. If `LOG_HASH_KEY` is unset, email tags in logs change too.

### CLOUDFLARE_ORIGIN_SECRET

The variable and the Transform Rule on the environment's API host must hold the same value.
The rule runs in the `http_request_late_transform` phase and sets `X-Origin-Verify`. The API
hosts under `becomify.app` are `api` (prod), `api-atelier` (dev) and `api-harbor` (test).

The value goes to two places, so it needs a holder that is not the terminal. Create a file
under `umask 077` and write the generated value into it. Feed the file to Railway on
standard input. Build the rule `PATCH` body from the same file, for example with
`jq --rawfile`, so the value never appears on the command line. Never echo it, and delete
the file when the last step is done.

1. Generate a random value into that file, without a trailing newline.
2. Set `CLOUDFLARE_ORIGIN_SECRET` on the backend with `--stdin --skip-deploys`, reading the
   file.
3. Redeploy the backend once.
4. Update the rule of that host (a `PATCH` on the rule) to the same value from the file right
   away.
5. Compare the hash of the variable with the hash of the rule value, then delete the file.

On a mismatch requests are not rejected. Every request is keyed under one shared constant
for rate limiting instead, so all callers share one rate-limit bucket, which shows up as `429`
responses on a busy site. Keep the gap between steps 3 and 4 short.

### Database and Redis credentials

The Postgres service is `<env>-db`, with the application role `become_app` and the owner
`postgres`. The Redis service is `<env>-redis`, Redis 8 started with
`--requirepass $REDIS_PASSWORD`.
[`security.md`](security.md#secrets) describes a zero-downtime alternative for `become_app`
that adds a second role.

#### Postgres roles

1. For each role, generate a password into a file created under `umask 077`, with
   `python -c 'import secrets; print(secrets.token_urlsafe(32), end="")'`. The password goes
   into a URL later, and `token_urlsafe` output needs no percent-encoding. Compute its SCRAM
   verifier locally, so the plaintext never reaches the database. The script below reads the
   password on standard input and writes the verifier to standard output, into a second file
   created under `umask 077`. The verifier is not the password, but it allows an offline
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

2. Write `roles.sql` under `umask 077` from the verifier files. The database logs DDL
   statements ([`security.md`](security.md#audit-logging)). The first line switches that off
   for the session. The second stops a failing statement from being logged with its text,
   verifier included. Postgres 16 does that when `log_statement` is `ddl`:

   ```sh
   {
     printf '%s\n' "SET log_statement = 'none';"
     printf '%s\n' "SET log_min_error_statement = 'panic';"
     printf "ALTER ROLE become_app PASSWORD '%s';\n" "$(cat become_app.verifier)"
     printf "ALTER ROLE postgres PASSWORD '%s';\n" "$(cat postgres.verifier)"
   } > roles.sql
   ```

3. Feed it to `psql` in the database container over the local socket, which admits the
   owner without a password. Nothing is typed or echoed. In the container `PGHOST` points
   to the internal TCP address and `PGPASSWORD` holds the password from container start.
   That password stops working once the owner's password changes, so both are unset:

   ```sh
   railway ssh -e <env> -s <env>-db env -u PGHOST -u PGPASSWORD \
     psql -h /var/run/postgresql -U postgres -d railway < roles.sql
   ```

4. Confirm by hash. Put this query, which holds no secret, in `check.sql`:
   `SELECT rolname, encode(sha256(convert_to(rolpassword, 'UTF8')), 'hex') FROM pg_authid WHERE rolname IN ('become_app', 'postgres') ORDER BY rolname;`
   Run it the same way as step 3 with `< check.sql` and compare each hash with `shasum -a 256`
   of the matching verifier file. The output of `ALTER ROLE` through `railway ssh` is
   sometimes cut short, so it proves nothing.
5. Build the new `become_app` URL in a file, from the password file and the non-secret parts
   of the current `DATABASE_URL` (host, port, database and any query string):

   ```sh
   printf '%s%s@%s' 'postgresql://become_app:' "$(cat become_app.password)" \
     '<host>:<port>/<database>' > become_app.url
   ```

   `printf` is a shell builtin, so the password stays out of the process list. Set the
   backend's `DATABASE_URL`, a literal, with `railway variable set DATABASE_URL --stdin
   --skip-deploys -s <env>-backend -e <env> < become_app.url`. Set `POSTGRES_PASSWORD` on
   `<env>-db` from `postgres.password` the same way, so the database does not restart.
   `MIGRATION_DATABASE_URL` references it and picks it up on the redeploy.
6. Redeploy the backend once, right away. New connections with the old `become_app`
   password fail until then. Delete every file of this procedure afterwards.

#### Redis

1. Generate the password into a file created under `umask 077`, as in step 1 of the Postgres
   roles.
2. If Redis is awake, change the running server. The container's `REDIS_PASSWORD` is still
   the old one here, and `-x` reads the last argument from standard input:

   ```sh
   railway ssh -e <env> -s <env>-redis \
     'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli -x CONFIG SET requirepass' < redis.password
   ```

   `railway ssh` joins its arguments into one command string for the remote shell, so the
   whole remote command is one quoted argument and `$REDIS_PASSWORD` expands in the container.

   If Redis is asleep (App Sleep), SSH does not reach the container. Skip this step and omit
   `--skip-deploys` in the next one, which restarts Redis with the new password.
3. Set `REDIS_PASSWORD` on the Redis service with `--stdin --skip-deploys`, so a later
   restart keeps the new password.
4. Redeploy the backend, because `REDIS_URL` references the Redis service.
5. Delete `redis.password`.

Between step 2 and the backend running with the new password, new connections to Redis
are refused. The revocation store fails closed: authenticated requests answer `401`, and
login, refresh and logout answer `503` (see [`security.md`](security.md)). Redeploy the
backend right away.

#### Corpus database

Where the environment has a corpus service, follow the Postgres steps with these changes:

1. The service is `<env>-vector`. The roles are `corpus_reader` and the service's owner, the
   user named by its `POSTGRES_USER` variable. A user name is not a secret, so read it from
   the variable.
2. In the `psql` command, pass the owner as `-U` and the database named by `POSTGRES_DB` of
   that service as `-d`, in place of `postgres` and `railway`.
3. Skip the `DATABASE_URL` step. `ASSISTANT_VECTOR_DB_URL` references
   `CORPUS_READER_PASSWORD`, so the backend redeploy picks it up.
4. Set `CORPUS_READER_PASSWORD` and the service's `POSTGRES_PASSWORD` with
   `--stdin --skip-deploys`.
5. The next ingest connects as the owner
   ([`api/assistant/README.md`](https://github.com/caitlon/BeCoMe/blob/prod/api/assistant/README.md#read-only-role-for-a-deployed-corpus-database)),
   so use the new owner password in the `ASSISTANT_VECTOR_DB_URL` of that run.

#### Verify

Run the in-container check from [Checking credentials from the
container](#checking-credentials-from-the-container) against the new backend container.

### Provider-issued keys

This covers `EMAIL_API_KEY`, `TURNSTILE_SECRET_KEY`, `ASSISTANT_API_KEY_OVH` and
`ASSISTANT_LANGSMITH_API_KEY`.

1. Create the new key at the provider.
2. Set the variable with `--stdin --skip-deploys` on every environment that shares the old
   key, before the next step.
3. Redeploy the backend of each of those environments once.
4. Check the new key as in the inventory table.
5. Revoke the old key at the provider.

Per provider:

- **Resend.** Give the key "Sending access", restricted to the sending domain. Dev and test
  share one.
- **Turnstile.** The project's Cloudflare API token has no Turnstile permission, so rotate in
  the dashboard: open Turnstile, the widget, and rotate the secret key. Keep the grace period,
  so the old secret still works while services switch, and it needs no revoking in step 5. The
  site key `VITE_TURNSTILE_SITE_KEY` stays. Dev and test share a widget.
- **OVHcloud and LangSmith.** Dev and test share the OVHcloud key. The LangSmith key matters
  only where tracing is on.

### Bucket credentials

Railway can also change a bucket's secret on its own. The symptom is photos failing with
`SignatureDoesNotMatch`. Compare the backend variables with the output of
`railway bucket credentials --json` by hash. Both print the keys, so send the output to a
file created under `umask 077`, never to the terminal.

1. Run `railway bucket credentials --reset --yes --json -b <env>-photos -e <env>` with its
   output redirected into such a file. The old pair stops working at once.
2. Set `BUCKET_ACCESS_KEY_ID` and `BUCKET_SECRET_ACCESS_KEY` on the backend right away.
   `--stdin` takes a single key, so this is two `railway variable set KEY --stdin
   --skip-deploys` calls, each fed with `jq -r` from the matching field of that file. Delete
   the file afterwards. The backend holds them as literal values.
3. Redeploy the backend once. Photos fail from the reset until this redeploy finishes, so do
   steps 1 to 3 without a pause.
4. Run the in-container check from [Checking credentials from the
   container](#checking-credentials-from-the-container). It lists one object with the
   backend's own bucket variables.

### GitHub Actions secrets

Replace the value in the repository's Actions secrets, then re-run the job that uses it.
Revoke the old token at the provider afterwards.
