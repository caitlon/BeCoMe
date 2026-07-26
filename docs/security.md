# Security

What is actually implemented in BeCoMe to keep the product and its users' data safe, and
how to operate the pieces that need runbooks. This is a description of the running system,
not a wishlist. Deployment topology lives in [`environments.md`](environments.md); the
academic threat model (attack trees, residual-risk argument) lives in the thesis
workspace and is not duplicated here.

## Status at a glance

| Area | Status | Where |
|------|--------|-------|
| Authentication -- JWT, refresh rotation, lockout | Implemented | `api/auth/` |
| Session transport -- HttpOnly cookies + CSRF | Implemented | `api/auth/cookies.py`, `api/middleware/csrf.py` |
| Authorization and tenant isolation | Implemented | `api/dependencies.py` |
| Rate limiting and abuse control | Implemented | `api/middleware/rate_limit.py` |
| Input validation | Implemented | `api/schemas/` |
| Configuration invariants per profile | Implemented | `api/config.py` |
| Network and edge -- Cloudflare, CORS, headers | Implemented | `api/main.py`, Cloudflare |
| Logging, observability, and PII scrubbing | Implemented | `api/logging_config.py`, `api/logging_context.py` |
| Secrets management and rotation | Implemented | Railway variables, [below](#secrets) |
| GDPR export and erasure | Implemented | `api/routes/users.py` |
| Database least-privilege, network, auditing | Implemented | `scripts/db/`, `api/db/engine.py` |
| Automated database backups | Partial -- manual dumps | `scripts/db/backup.sh` |

## Authentication

Sessions are stateless JWTs signed with `SECRET_KEY` (HS256). Login returns a short-lived
access token and a longer-lived refresh token. Refresh tokens rotate: each refresh mints a
fresh pair tied to a rotation family (a `sid` claim). Presenting a refresh token that has
already been rotated is treated as theft and revokes the entire family, so a stolen token
stops working the moment the legitimate client refreshes. Changing the password stamps a
per-user cutoff that rejects every token issued before it, and the cutoff itself expires
once the longest-lived token would have, so it is not stored forever.

Passwords are hashed with bcrypt. Because bcrypt silently truncates input at 72 bytes, the
password is SHA-256 pre-hashed and base64-encoded first (`api/auth/password.py`), which is
the approach bcrypt's own maintainers recommend. A strength policy is enforced on
registration and password change.

Two abuse paths on the login endpoint are closed. Repeated failures lock the account for a
cooldown window (`api/auth/login_throttle.py`), which stops online brute force and
credential stuffing against a single account. And an unknown email still runs a dummy hash
so a wrong-email response takes the same time as a wrong-password one -- login timing
cannot be used to enumerate which addresses have accounts.

## Session transport (cookies and CSRF)

The browser client keeps no token in JavaScript-readable storage. Login and refresh set the
access and refresh tokens as cookies marked `HttpOnly`, `SameSite=Strict`, and `Secure`
(the `Secure` flag follows the request scheme, so it is on in production behind TLS and off
for the plain-HTTP dev and e2e stacks; see `api/auth/cookies.py`). An XSS payload therefore
cannot read the session the way it could read `localStorage`.

`SameSite=Strict` already stops the session cookies from riding along on cross-site
requests. On top of that, a double-submit CSRF check (`api/middleware/csrf.py`) defends the
same-site case: login also sets a readable `csrf_token` cookie, and every cookie-based
mutation must echo it back in an `X-CSRF-Token` header. An attacker who cannot read the
cookie value cannot forge the matching header. The check only engages when the request
carries the `csrf_token` cookie, so Bearer-token clients and the pre-session auth endpoints
(`login`, `register`, `refresh`, password reset) are unaffected -- a stale cookie left by a
revoked session can never block a fresh login. Logout stays CSRF-protected.

The `Authorization: Bearer` path is kept alongside the cookie path for programmatic clients
and the test suite; it authenticates the same tokens without the cookie or CSRF machinery.

## Authorization and tenant isolation

BeCoMe is multi-tenant: every project-scoped route runs through `RequireProjectAccess`
(`api/dependencies.py`) before it reads or writes anything. A caller who is not a member of
the project gets `404 Not Found` -- the same answer as a project that does not exist -- so
the API never confirms the existence of a project to someone with no business knowing about
it. A member who lacks the required role (an expert attempting an admin action) gets `403`,
since they already know the project is there. Denials are logged with the project and user
id for audit.

## Rate limiting and abuse control

Rate limiting is handled by slowapi backed by Redis, with an in-memory fallback if Redis is
unreachable (`api/middleware/rate_limit.py`). Two global ceilings apply to every route --
`300/minute` and a `20/second` burst -- so no endpoint is unbounded even if it forgot its
own limit. On top of that, routes carry tighter limits by risk:

| Limit | Value | Applied to |
|-------|-------|-----------|
| Auth | `5/minute` | Login, register |
| Password reset | `3/minute` | Forgot / reset password |
| Write | `30/minute` | Mutations that also recalculate |
| Upload | `10/minute` | File uploads |
| Standard | `60/minute` | Everything else |

The limiter keys on the real client IP. Behind Cloudflare and Railway the app trusts the
forwarded protocol and client address only from the proxy hop it is configured for; a
`X-Forwarded-For` header from an untrusted source is ignored, so a client cannot spoof its
way around the per-IP limits. Auth rate limiting fails closed. Request bodies over the
configured ceiling are rejected with `413` before they are buffered, and profile-photo
uploads are streamed and size-capped rather than read whole into memory.

## Input validation

Request DTOs are Pydantic models with `extra="forbid"` (`api/schemas/`), so an unexpected
field is a `422` rather than a silently ignored parameter. String fields carry length caps,
free-text names are HTML-sanitized, and list endpoints clamp their page size
(`MAX_PAGE_SIZE = 100`, `api/pagination.py`) so a single request cannot ask the database for
an unbounded result set. The GDPR export is the one deliberate exception to the list caps --
Article 20 requires the full dataset -- and that is documented at the call site.

## Configuration and profiles

The app runs under one of three profiles selected by `APP_ENV`: `dev`, `test`, `prod`
(`api/config.py`). Deployed profiles are held to invariants that fail startup rather than
boot insecurely (`_validate_deploy_invariants`): the `SECRET_KEY` must be strong, SQLite is
rejected in favor of PostgreSQL, `redis_url` must be set, and `CORS_ORIGINS` may not be
localhost. Production additionally requires `cloudflare_origin_secret`. The pytest runner is
distinguished from a deployed `test` (staging) environment by a `TESTING` flag, so the
invariants guard staging without breaking the local suite. Interactive API docs (`/docs`)
are served only outside production.

## Network and edge

The public origin is `becomify.app`, served through Cloudflare. A Cloudflare Transform Rule
injects a shared secret header that the origin then requires (`cloudflare_origin_secret`),
so the Railway origin cannot be reached directly, bypassing the edge. CORS is configured
with explicit allowed origins and `allow_credentials=True` (required for the cookie
session), and permits the `X-CSRF-Token` header. Standard security response headers are set
by middleware.

## Logging, observability, and privacy

Logs are structured JSON in the deployed profiles. Each request is tagged with an
`X-Request-ID`, and a context filter binds that request id and the acting user id onto every
`api.*` log record through contextvars (`api/logging_context.py`), so a service or security
log line can be traced back to a request without threading identifiers by hand. Personal
data is kept out of the logs: email addresses are recorded as a truncated SHA-256 hash
(`email_hash`), not in the clear. Unhandled errors hit a catch-all `500` handler and, when
`SENTRY_DSN` is configured, Sentry.

Two separate switches keep credentials out of the tracker, and both are needed.
`send_default_pii=False` drops the client IP, cookies, headers, and request bodies.
`include_local_variables=False` drops the frame locals of every traceback frame, which
`send_default_pii` does not cover and which default to on: the auth handlers bind the parsed
request body to a local, so with locals enabled a fault anywhere under `register`,
`change-password`, or `reset-password` would ship `repr()` of that model -- the plaintext
passwords, or a reset token that is still redeemable -- to the tracker. Sentry's own scrubber
does not catch this, because it matches local *names* against a denylist and the leaking
local is called `data`. As a second layer, the credential fields in `api/schemas/auth.py` are
declared `repr=False`, so those values stay out of any `repr()` regardless of who calls it.

## Secrets

Configuration comes from environment variables; the local `.env` is gitignored and never
committed, and deployment secrets live in Railway variables rather than in the image. CI
runs `detect-secrets` against a committed baseline, and the same check runs locally before a
push, so a credential added to the tree is caught before it leaves the machine.

Rotating the `become_app` database password without downtime uses a second credential so
there is never a window where the application cannot connect:

1. Create a replacement login with the same grants -- `CREATE ROLE become_app_v2 LOGIN ...`,
   then apply the `scripts/db/roles.sql` grants to it.
2. Point the environment's `DATABASE_URL` at `become_app_v2` in Railway and redeploy.
3. Confirm health is `200` and that `pg_stat_activity` shows connections from the new role.
4. Drop the old role: `DROP ROLE become_app;`. Rename `become_app_v2` back during a later
   quiet window if you want the canonical name restored.

`SECRET_KEY` rotates the same way: add the new value, redeploy, verify, then remove the old
one. Rotating it invalidates every existing session, which is the point when a leak is
suspected.

## GDPR: export and erasure

Both data-subject rights are served by the API. Export (Article 20) returns the full
personal dataset as JSON from `GET /api/v1/users/me/export`. Erasure (Article 17) is handled
by `DELETE /api/v1/users/me`: the request carries a disposition for every project the user
still admins -- transfer it to another member, or delete it -- and the account is removed
only once each owned project has been dealt with. That keeps one person's erasure from
silently taking a whole panel's opinions with it. The profile-photo blob is deleted from
object storage as part of the same operation, so erasure covers stored media too.

When an admin removes a member from a project, that member's opinion is deleted in the same
transaction and the project result is recalculated without it (`remove_member` in
`api/services/project_membership_service.py`). Otherwise the row would outlive the
membership: it carries the person's name, email, and stated position, it is served to every
remaining member and embedded in every export, and `RequireProjectAccess` would no longer
let the person concerned withdraw it themselves.

## Accepted risks

Two properties are known, deliberate, and reviewed. They are recorded here so a future audit
does not re-litigate them.

**Registration and invitation disclose whether an address has an account.** `POST /auth/register`
answers `409 Email already registered` for a taken address, and inviting by email answers
`404` for an address that has no account. Both are inherent to the flows: registration has to
tell a returning user that they already have an account, and an invitation cannot be created
for a user row that does not exist. Closing them means a deferred-activation signup with
email verification, where the distinguishing branch moves into the mailbox -- a feature, not
a patch. The bit disclosed is one the caller already supplied, and the login path is
separately hardened against enumeration (uniform 401, equalized timing), as is
forgot-password (uniform 202).

**Login and refresh also return the refresh token in the JSON body.** The browser client
never reads it -- it uses the `HttpOnly` cookie -- but programmatic clients can only obtain
the token this way, and `POST /auth/refresh` accepts it in the request body for exactly that
reason. Reading the body value requires script execution on the origin, which the CSP
(`script-src 'self'`), the explicit CORS allow-list, and `SameSite=Strict` are there to
prevent; rotation with reuse detection then caps the value of a token that does leak.

## Database

How the PostgreSQL databases are locked down. This layer sits under the application and is
operated through its own runbooks.

### Roles and least privilege

Every environment's database is reached through two roles, never one:

- **`become_app`** -- the application runtime role behind `DATABASE_URL`. It is a plain login
  role: `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOBYPASSRLS`. Its rights stop at
  `SELECT/INSERT/UPDATE/DELETE` on the application tables plus `USAGE`/`SELECT` on their
  sequences. It cannot run DDL, create objects in `public`, or read another role's data.
- **`postgres`** -- the Railway-provisioned superuser, used only by Alembic for schema changes
  through `MIGRATION_DATABASE_URL`. Railway hands out exactly one superuser, so there is no
  separate `migrator` role; keeping migrations on a distinct URL is what isolates DDL from the
  runtime token, without the overhead of in-session `SET ROLE`.

`scripts/db/roles.sql` is the idempotent source of truth for this setup. Running it against an
environment as `postgres` reconciles the grants, the default privileges that hand every future
Alembic-created table to `become_app`, the `REVOKE CREATE ON SCHEMA public FROM PUBLIC`
lockdown, a pinned `search_path` (`pg_catalog, public`, which closes CVE-2018-1058 for the
exposed role), and the role-level `statement_timeout`/`idle_in_transaction_session_timeout`/
`lock_timeout`. Passwords stay out of the file -- they live in Railway variables.

The connection itself is hardened in `api/db/engine.py`: TLS is required on deployed databases
(`sslmode=require`), each connection is tagged with an `application_name`, and the per-session
statement and idle-in-transaction timeouts are also set client-side through libpq `options`, so
a single runaway query cannot monopolise the database.

### Network exposure

Production and staging databases answer only on Railway's private network
(`*.railway.internal`); their public TCP proxies were removed, so a leaked password is not the
sole barrier between the internet and the data. The dev database is the one exception, and even
there the proxy is normally closed -- it is opened in the Railway dashboard only for a specific
hands-on operation and shut again afterwards. That toggle is the project's substitute for an IP
allowlist, which Railway's platform does not offer.

### Audit logging

Railway's managed Postgres permits `ALTER SYSTEM`, so connection auditing is enabled directly on
each database and reloaded without a restart:

```sql
ALTER SYSTEM SET log_connections = 'on';
ALTER SYSTEM SET log_disconnections = 'on';
ALTER SYSTEM SET log_statement = 'ddl';
ALTER SYSTEM SET log_min_duration_statement = '5000';
SELECT pg_reload_conf();
```

Connections and disconnections are recorded, every DDL statement is logged -- schema changes
should only ever originate from Alembic, so anything else here is a red flag -- and statements
slower than five seconds are captured. The output flows into the Railway service logs. Finer
read/write auditing would need the `pgaudit` extension, but that requires
`shared_preload_libraries`, which Railway's image does not expose; `log_statement = 'ddl'` is the
workable substitute.

### Backups

Railway's managed backups require the Pro plan, so on the current (free) plan the Postgres
volumes are **not** backed up automatically. Until that changes, take manual dumps with
`scripts/db/backup.sh`, which opens a temporary proxy, runs `pg_dump`, and removes the proxy
again:

```bash
./scripts/db/backup.sh prod      # writes backups/prod-<timestamp>.dump
```

Run it before risky migrations and on a regular cadence. The dumps stay out of the repo
(`backups/` is gitignored -- they contain user data). Restore into any database with:

```bash
pg_restore --no-owner --no-privileges -d <target-url> backups/<dump>
```

Upgrading the prod service to the Railway Pro plan would replace this with scheduled backups
plus point-in-time recovery.

## Data integrity and migrations

Deleting a user must not silently destroy other people's work. Most child rows clear
themselves through `ON DELETE CASCADE` (memberships, opinions, sent and received
invitations, reset tokens). A project a user **admins** is shared data, so `projects.admin_id`
uses `ON DELETE RESTRICT`: the database refuses to orphan or silently erase a shared project,
which is why the erasure endpoint requires an explicit disposition for each one (see
[GDPR](#gdpr-export-and-erasure)). Schema changes ship as reversible Alembic migrations run
through the migration-only superuser URL, keeping DDL off the runtime role.
