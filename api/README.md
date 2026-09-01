# BeCoMe REST API

FastAPI-based REST API for the BeCoMe group decision-making method.

## Contents

- [Quick start](#quick-start)
- [Module structure](#module-structure)
- [API endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Testing](#testing)
- [Related documentation](#related-documentation)

## Quick start

```bash
uv sync --extra api
uv run uvicorn api.main:app --reload
```

The API runs at `http://localhost:8000`. Interactive documentation:
- Swagger UI: `/docs`
- ReDoc: `/redoc`

## Module structure

```text
api/
├── auth/               # Authentication & authorization
│   ├── jwt.py              # Token creation/validation (rotation family / sid)
│   ├── password.py         # Password hashing (bcrypt)
│   ├── cookies.py          # HttpOnly session cookies + CSRF token helpers
│   ├── dependencies.py     # CurrentUser dependency (cookie or Bearer)
│   ├── revocation_store.py # Token revocation store (in-memory / Redis)
│   ├── login_throttle.py   # Per-account lockout after failed logins
│   ├── email_throttle.py   # Per-address cooldown for reset and activation emails
│   └── logging.py          # Auth event logging
├── db/                 # Database layer
│   ├── models.py           # SQLModel entities
│   ├── engine.py           # Database engine setup
│   ├── session.py          # Session dependency
│   └── utils.py            # UTC helpers, email regex
├── middleware/         # Request processing
│   ├── rate_limit.py       # SlowAPI rate limiting (logs violations)
│   ├── csrf.py             # Session-bound CSRF check on cookie mutations
│   ├── body_size.py        # Request body size limit (413)
│   ├── security_headers.py # Security response headers
│   ├── request_logging.py  # Request/response logging + X-Request-ID
│   └── exception_handlers.py  # Centralized errors + catch-all 500
├── routes/             # HTTP endpoints
│   ├── auth.py             # /api/v1/auth/*
│   ├── users.py            # /api/v1/users/*
│   ├── projects.py         # /api/v1/projects/*
│   ├── opinions.py         # /api/v1/projects/{id}/opinions
│   ├── invitations.py      # /api/v1/invitations/*
│   ├── calculate.py        # /api/v1/calculate
│   └── health.py           # /api/v1/health
├── schemas/            # Pydantic DTOs
│   ├── auth.py             # Login, register, tokens
│   ├── project.py          # Project CRUD
│   ├── opinion.py          # Expert opinions
│   ├── invitation.py       # Project invitations
│   ├── calculation.py      # BeCoMe calculation I/O
│   └── ...
├── services/           # Business logic
│   ├── user_service.py
│   ├── project_service.py         # + membership / query services
│   ├── opinion_service.py
│   ├── invitation_service.py
│   ├── calculation_service.py
│   ├── password_reset_service.py
│   ├── data_export_service.py     # GDPR export
│   ├── email/              # Email delivery (console / HTTP provider)
│   ├── export/             # Result export renderers
│   └── storage/            # File storage (Railway bucket, S3)
├── utils/              # Utilities
│   ├── sanitization.py     # HTML sanitization
│   ├── client_ip.py        # Real client IP behind trusted proxies
│   ├── upload.py           # Size-capped streaming reads
│   └── photo_links.py      # Photo proxy URL builder
├── config.py           # Settings (Pydantic Settings) + deploy invariants
├── pagination.py       # Shared limit/offset params (cap 100)
├── logging_config.py   # Centralized logging + JSON formatter (test/prod)
├── logging_context.py  # Request-scoped correlation (request_id/user_id) via contextvars
├── dependencies.py     # DI factories + authorization
├── exceptions.py       # API exception hierarchy
└── main.py             # FastAPI application (+ setup_logging, Sentry init)
```

## API endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user, email an activation link |
| POST | `/api/v1/auth/verify-email` | Confirm an address with an activation token and its password |
| POST | `/api/v1/auth/resend-verification` | Request a fresh activation link for an address |
| POST | `/api/v1/auth/login` | Login, get tokens |
| POST | `/api/v1/auth/logout` | Revoke refresh token |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/forgot-password` | Request a password reset email |
| POST | `/api/v1/auth/reset-password` | Reset password using a token |
| GET | `/api/v1/auth/me` | Get current user profile, plus the session's CSRF token as a header |

**Registration and activation.** `POST /auth/register` always answers `202` with the same
body, whether the address is free, already registered but unverified, or already registered
and verified. The response never reveals which. The account it creates cannot log in until
someone redeems the emailed link through `POST /auth/verify-email`. Until then
`POST /auth/login` answers `403` with a distinct `detail`, so a client can offer a resend.

A submission takes effect only when someone follows its own link *and* restates its own
password. The password hash and names travel on the activation token, so registering an
unconfirmed address twice leaves two working links, and whichever one someone redeems
first decides
the credentials the account opens with. `POST /auth/verify-email` therefore takes
`{token, password}`: an unknown, spent, or expired token gets one opaque `400`, while a
password that does not match the token gets a `403` with its own `detail`, so a client can
ask the user to retype instead of sending them off for a new link. Mismatches count against
their own per-token lockout, namespaced apart from login's. A run of failed logins can never
deny someone their own activation, and burning one token's budget can never lock a different,
freshly resent token for the same account. The two budgets are independent, so
they add up: 10 failures each per 15 minutes, and only a caller already holding a live
emailed token can spend the activation half. A mismatch also spends from the login lockout,
which costs the guesser rather than capping the pair. A completed password reset clears the
login lockout, and answers the same opaque `400` an unusable token gets when an activation
confirmed the account while the reset was in flight. `POST /auth/resend-verification` takes
`{email, password}` and answers `202` for any address. The link it mails carries the submitted
password like any other. See `docs/security.md` for why each branch behaves as it
does.

**Session transport.** Login and refresh set the access and refresh tokens as
`Secure; HttpOnly; SameSite=Strict` cookies (the refresh cookie stays scoped to
`/api/v1/auth`) plus a readable `csrf_token` cookie. The response body carries the same tokens,
so programmatic clients can keep using the `Authorization: Bearer` header.
A cookie-authenticated mutating request (POST/PUT/PATCH/DELETE) must send that value back
in an `X-CSRF-Token` header. Bearer-header requests are exempt. `/auth/refresh` reads the
refresh token from the cookie or the body, and logout revokes the session and clears the
cookies.

The token is **derived from the session**, not compared against the cookie: it is an HMAC
of the session's `sid` under `SECRET_KEY`, and the middleware recomputes the expected value
from the session cookie the request authenticates as. Anyone able to write cookies for this
host can plant a `csrf_token` they know, or one minted for a session they hold. That includes a
page on a sibling `becomify.app` subdomain, which `SameSite` counts as same-site. Neither
cookie matches what the server derives for the victim's session. The check also keys on the
*session* cookie, so omitting the CSRF cookie cannot waive it.

Login and refresh return the value in an `X-CSRF-Token` **response** header, and
`GET /auth/me` reports the token for the session it authenticates as, so a page reload
recovers it, and a request with no session cookie gets no header. The header is not redundant.
The cookie has no `Domain` attribute, so it belongs to the API host, and a browser app served
from any other host cannot read it out of `document.cookie` even though the browser keeps
sending it. The header is that app's only copy of the value, which is why
`CORSMiddleware` lists it under `expose_headers` as well as `allow_headers`. A refresh
stays in the same rotation family, so the token does not change across refreshes. A fresh login
starts a new family and a new token. See `docs/security.md` for why the cookie is not
widened with a `Domain` instead, and for what this does not cover.

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users/me` | Get profile |
| GET | `/api/v1/users/me/export` | Export all personal data as JSON (GDPR Art. 20) |
| PUT | `/api/v1/users/me` | Update profile |
| PUT | `/api/v1/users/me/password` | Change password |
| POST | `/api/v1/users/me/photo` | Upload photo (JPEG/PNG/GIF/WebP, max 5 MB and 4096x4096 px) |
| DELETE | `/api/v1/users/me/photo` | Delete photo |
| GET | `/api/v1/users/{id}/photo` | Serve a profile photo from the private bucket (public) |
| DELETE | `/api/v1/users/me` | Delete account, handling each owned project (GDPR Art. 17) |

The photo proxy is public, because an `<img>` tag cannot send an auth header. It passes
the bucket's response straight through to the client instead of downloading the object
first, so the wait before the first byte is one bucket round trip rather than a full
download. The URL that reaches it carries a `?v=` token taken from the stored object key, and
every upload mints a new key.

The route always serves whichever photo the account holds now, so the cache header depends on
whether the request named that photo. A `v` matching the current key describes bytes that
cannot change under it, so the route serves it with
`Cache-Control: public, max-age=31536000, immutable`. Anything else gets `max-age=300`: no
token, a stale one, or an invented one. Those URLs already resolve to different bytes than they
once did, and they will again. Pinning one for a
year would leave a shared cache handing out a replaced avatar to everyone who asked for it.

Deleting the account (`DELETE /api/v1/users/me`) accepts an optional body that says what
to do with every project the user still admins: `transfer` it to another member, or `delete`
it. Erasure then never silently drops other experts' contributions:

```json
{ "project_dispositions": [
  { "project_id": "<uuid>", "action": "transfer", "new_admin_id": "<member-uuid>" },
  { "project_id": "<uuid>", "action": "delete" }
] }
```

An owned project left without a disposition returns `409`, and a transfer to a non-member
returns `422`. Erasure also removes the profile photo blob from object storage.

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/projects` | List user's projects |
| POST | `/api/v1/projects` | Create project |
| GET | `/api/v1/projects/{id}` | Get project details |
| PATCH | `/api/v1/projects/{id}` | Update project |
| DELETE | `/api/v1/projects/{id}` | Delete project |
| GET | `/api/v1/projects/{id}/members` | List members |
| DELETE | `/api/v1/projects/{id}/members/{user_id}` | Remove member (discards their opinion and recalculates) |
| POST | `/api/v1/projects/{id}/transfer-ownership` | Transfer ownership to another member |
| POST | `/api/v1/projects/{id}/invite` | Invite user |
| GET | `/api/v1/projects/{id}/invitations` | List the project's pending invitations |

### Opinions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/projects/{id}/opinions` | List opinions |
| POST | `/api/v1/projects/{id}/opinions` | Submit opinion |
| DELETE | `/api/v1/projects/{id}/opinions` | Delete own opinion |

### Invitations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/invitations` | List pending invitations |
| POST | `/api/v1/invitations/{id}/accept` | Accept invitation |
| POST | `/api/v1/invitations/{id}/decline` | Decline invitation |

### Calculation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/calculate` | Calculate BeCoMe (standalone) |
| GET | `/api/v1/projects/{id}/result` | Get project calculation result |
| GET | `/api/v1/projects/{id}/result/export` | Download the result as PDF or CSV |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | API health check |

**Pagination.** List endpoints (projects, opinions, members, invitations) accept optional
`limit` and `offset` query parameters. `limit` tops out at 100 and defaults to the first page,
so responses stay bounded. The GDPR export is the one exception: it always returns the full
dataset.

## Configuration

Environment variables (a `.env` file works too):

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `dev` | Deployment profile: `dev`, `test`, or `prod`. Selects the `.env.<APP_ENV>` overlay; deployed profiles reject a weak secret, SQLite, a missing Redis, or localhost CORS at startup. See [docs/environments.md](../docs/environments.md). |
| `DATABASE_URL` | `sqlite:///./become.db` | Database connection string. On deployed environments this is the least-privilege `become_app` role. |
| `MIGRATION_DATABASE_URL` | *required when deployed* | Privileged connection used only by Alembic migrations (DDL); falls back to `DATABASE_URL` locally, but startup fails without it on a deployed service so the least-privilege split is never silently lost. |
| `SECRET_KEY` | *required* | JWT signing key (generate with `openssl rand -hex 32`) |
| `LOG_HASH_KEY` | *optional* | Key for the email tags in security logs; falls back to `SECRET_KEY`. Set it separately to keep tags comparable across a secret rotation. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `DEBUG` | `false` | Debug mode; must stay off on a deployed service (startup fails otherwise) |
| `API_VERSION` | `1.0.0b1` | API version (auto-read from pyproject.toml) |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:8080` | Allowed CORS origins |
| `REDIS_URL` | *required when deployed* | Redis for rate limiting, token revocation, and auth throttles |
| `CLOUDFLARE_ORIGIN_SECRET` | *required when deployed* | Shared secret proving the request came through Cloudflare; every deployed environment sits behind it, so each needs its own value paired with a Transform Rule for that environment's API host |
| `EMAIL_PROVIDER` | `console` | Password-reset email delivery: `console` (log) or `http` (Resend) |
| `EMAIL_API_KEY` | *required when deployed* | API key for the `http` email provider; startup fails without it on every deployed service, where the console fallback would print reset links to stdout instead of sending them |
| `API_PUBLIC_URL` | `http://localhost:8000` | Public base URL of this API, used to build profile photo proxy links |
| `BUCKET_NAME` | *optional* | Railway Storage Bucket name (auto-injected when a bucket is attached) |
| `BUCKET_ENDPOINT` | *optional* | S3-compatible bucket endpoint |
| `BUCKET_ACCESS_KEY_ID` | *optional* | Bucket access key |
| `BUCKET_SECRET_ACCESS_KEY` | *optional* | Bucket secret key |
| `LOG_LEVEL` | per profile: `DEBUG` on dev, `INFO` on test and prod | Log verbosity (`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`); an explicit value always wins. A local shell emits text, every deployed service emits JSON |
| `LOG_FILE` | *optional* | Path for a rotating log file (console logging is always on) |
| `SENTRY_DSN` | *optional* | Sentry DSN for backend error tracking (disabled when unset) |
| `BETTERSTACK_SOURCE_TOKEN` | *optional* | Better Stack log source token (ships `api.*` logs when set together with the host below) |
| `BETTERSTACK_INGESTING_HOST` | *optional* | Better Stack ingesting host for log shipping (per-environment source) |

Profile photos live in a private Railway Storage Bucket (S3-compatible), served through the
`GET /api/v1/users/{id}/photo` proxy. When the bucket variables are absent, photo upload is
disabled and every other feature keeps working.

**Migrations.** Alembic owns the PostgreSQL schema (`migrations/`), and `alembic upgrade head`
runs before each Railway deploy. To apply it by hand against one database, run
`ALEMBIC_DATABASE_URL=<url> uv run alembic upgrade head`. SQLite (local development and the test
suite) keeps using `create_all`, so it needs no migration step.

**Observability.** Every request gets an `X-Request-ID` response header for log correlation,
either generated or echoed from the client's header. A `ContextFilter` binds that ID and the
acting user through contextvars, so every `api.*` record carries `request_id` and `user_id`,
service and security logs included, not just the request line.

Under the `api.*` loggers, the API logs:

- each request and its timing
- every mutating domain action (`api.service.*` and `api.route.*`)
- every refusal, whether it is a CSRF rejection, an over-large body, a rejected token, a denied
  invitation, or a refused photo upload
- at `DEBUG`, the reads and the outbound calls to Redis, S3, and the email provider, with their
  timings

Records carry structured `extra` fields under an `event` name rather than free text. Output is
JSON on every deployed service, the Railway `dev` service included, since it is a deploy and not
a laptop. A drain can then index `event`, `request_id`, `status_code`, and `duration_ms`.

Five third-party loggers share those handlers at pinned levels (`_EXTERNAL_LOG_LEVELS` in
`api/logging_config.py`). `uvicorn.error` sits at INFO, so a boot that never finished is visible
in the drain. `httpx` and `botocore` sit at WARNING, since `email_sent` and `s3_upload` already
cover their successful calls. `uvicorn.access` stays silent on purpose, because `api.request`
logs the same requests with more fields. **`sqlalchemy.engine` is pinned at WARNING and must
stay there:** its DEBUG level prints bound query parameters, which on this schema means password
hashes, addresses, and reset-token hashes going to the drain in the clear. The read services log
query shape and timing instead. If drain volume from dev's DEBUG stream becomes a problem, call
`logtail_handler.setLevel(logging.INFO)` in `_build_handlers`, where the handler is built. The
console keeps DEBUG, the drain does not.

Unhandled exceptions return an opaque 500 and reach Sentry when `SENTRY_DSN` carries a value.
With the `BETTERSTACK_*` variables in place, the API also ships its logs to Better Stack through
`logtail-python`, one source per environment.

## Testing

The test suite includes:
- Unit tests: auth, middleware, schemas, services, utilities (`tests/unit/api/`)
- Integration tests: auth flows, database, route handlers (`tests/integration/api/`)
- End-to-end tests: full API workflows (`tests/e2e/`)

```bash
# Run all API tests
uv run pytest tests/unit/api/ tests/integration/api/ -v

# Run with coverage
uv run pytest tests/unit/api/ tests/integration/api/ --cov=api --cov-report=term-missing
```

## Related documentation

- [Main README](../README.md): project overview
- [docs/security.md](../docs/security.md): application and database security posture
- [docs/environments.md](../docs/environments.md): the dev, test, and prod profiles, Railway
  deployment, and database topology
