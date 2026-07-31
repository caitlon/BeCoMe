# BeCoMe REST API

FastAPI-based REST API for the BeCoMe group decision-making method.

## Quick Start

```bash
uv sync --extra api
uv run uvicorn api.main:app --reload
```

The API runs at `http://localhost:8000`. Interactive documentation:
- Swagger UI: `/docs`
- ReDoc: `/redoc`

## Module Structure

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
│   ├── csrf.py             # Double-submit CSRF check on cookie mutations
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

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user, email an activation link |
| POST | `/api/v1/auth/verify-email` | Confirm an address using an activation token |
| POST | `/api/v1/auth/resend-verification` | Request a fresh activation link |
| POST | `/api/v1/auth/login` | Login, get tokens |
| POST | `/api/v1/auth/logout` | Revoke refresh token |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/forgot-password` | Request a password reset email |
| POST | `/api/v1/auth/reset-password` | Reset password using a token |
| GET | `/api/v1/auth/me` | Get current user profile |

**Registration and activation.** `POST /auth/register` always answers `202` with the same
body, whether the address is free, already registered but unverified, or already registered
and verified -- the response never reveals which. The account it creates cannot log in until
the emailed link is redeemed through `POST /auth/verify-email`; until then `POST /auth/login`
answers `403` with a distinct `detail` so a client can offer a resend. `POST
/auth/resend-verification` answers `202` for any address. A submission takes effect only when
its own link is followed: the password and names travel on the activation token, so
registering an unconfirmed address twice leaves two working links, and whichever is redeemed
first decides the credentials the account opens with. See `docs/security.md` for why each
branch behaves as it does.

**Session transport.** Login and refresh set the access and refresh tokens as
`Secure; HttpOnly; SameSite=Strict` cookies (the refresh cookie is scoped to
`/api/v1/auth`) plus a readable `csrf_token` cookie; the tokens are also returned in the
response body so programmatic clients can keep using the `Authorization: Bearer` header.
A cookie-authenticated mutating request (POST/PUT/PATCH/DELETE) must echo the
`csrf_token` cookie back in an `X-CSRF-Token` header (double-submit CSRF); Bearer-header
requests are exempt. `/auth/refresh` reads the refresh token from the cookie or the body,
and logout revokes the session and clears the cookies.

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users/me` | Get profile |
| GET | `/api/v1/users/me/export` | Export all personal data as JSON (GDPR Art. 20) |
| PUT | `/api/v1/users/me` | Update profile |
| PUT | `/api/v1/users/me/password` | Change password |
| POST | `/api/v1/users/me/photo` | Upload photo (JPEG/PNG/GIF/WebP, max 5 MB and 4096x4096 px) |
| DELETE | `/api/v1/users/me/photo` | Delete photo |
| DELETE | `/api/v1/users/me` | Delete account, handling each owned project (GDPR Art. 17) |

Deleting the account (`DELETE /api/v1/users/me`) accepts an optional body that says what
to do with every project the user still admins -- `transfer` it to another member or
`delete` it -- so erasure never silently drops other experts' contributions:

```json
{ "project_dispositions": [
  { "project_id": "<uuid>", "action": "transfer", "new_admin_id": "<member-uuid>" },
  { "project_id": "<uuid>", "action": "delete" }
] }
```

An owned project left without a disposition returns `409`; a transfer to a non-member
returns `422`. The profile photo blob is removed from object storage as part of erasure.

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

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | API health check |

**Pagination.** List endpoints (projects, opinions, members, invitations) accept optional
`limit`/`offset` query parameters; `limit` is capped at 100 and defaults to the first page,
so responses stay bounded. The GDPR export is the one exception -- it always returns the
full dataset.

## Configuration

Environment variables (can use `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `dev` | Deployment profile: `dev`, `test`, or `prod`. Selects the `.env.<APP_ENV>` overlay; deployed profiles reject a weak secret, SQLite, a missing Redis, or localhost CORS at startup. See the root README "Environment profiles". |
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
| `CLOUDFLARE_ORIGIN_SECRET` | *required in prod* | Shared secret proving the request came through Cloudflare |
| `EMAIL_PROVIDER` | `console` | Password-reset email delivery: `console` (log) or `http` (Resend) |
| `EMAIL_API_KEY` | *required when deployed* | API key for the `http` email provider; startup fails without it on the staging and production profiles, where the console fallback would print reset links to stdout instead of sending them |
| `API_PUBLIC_URL` | `http://localhost:8000` | Public base URL of this API, used to build profile photo proxy links |
| `BUCKET_NAME` | *optional* | Railway Storage Bucket name (auto-injected when a bucket is attached) |
| `BUCKET_ENDPOINT` | *optional* | S3-compatible bucket endpoint |
| `BUCKET_ACCESS_KEY_ID` | *optional* | Bucket access key |
| `BUCKET_SECRET_ACCESS_KEY` | *optional* | Bucket secret key |
| `LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`/`INFO`/`WARNING`/`ERROR`); dev emits text, test/prod emit JSON |
| `LOG_FILE` | *optional* | Path for a rotating log file (console logging is always on) |
| `SENTRY_DSN` | *optional* | Sentry DSN for backend error tracking (disabled when unset) |
| `BETTERSTACK_SOURCE_TOKEN` | *optional* | Better Stack log source token (ships `api.*` logs when set together with the host below) |
| `BETTERSTACK_INGESTING_HOST` | *optional* | Better Stack ingesting host for log shipping (per-environment source) |

**Note:** Profile photos are stored in a private Railway Storage Bucket (S3-compatible) and served through the `GET /api/v1/users/{id}/photo` proxy. When the bucket variables are absent, photo upload is disabled and the API continues to function with all other features available.

**Migrations:** The PostgreSQL schema is managed by Alembic (`migrations/`). `alembic upgrade head` runs automatically before each Railway deploy; to apply it manually against a specific database use `ALEMBIC_DATABASE_URL=<url> uv run alembic upgrade head`. SQLite (local development and the test suite) keeps using `create_all`, so no migration step is needed there.

**Observability:** Every request gets an `X-Request-ID` response header (generated, or echoed from the client's header) for log correlation. A `ContextFilter` binds that ID and the acting user through contextvars, so every `api.*` record -- service and security logs included -- carries `request_id` and `user_id`, not just the request line. Requests, unhandled exceptions, and rate-limit violations are logged under the `api.*` loggers; in `test`/`prod` the output is JSON so a log drain can index fields like `request_id` and `status_code`. Unhandled exceptions return an opaque 500 and are reported to Sentry when `SENTRY_DSN` is set. When the `BETTERSTACK_*` variables are set, the `api.*` logs are also shipped to Better Stack (a per-environment source) via `logtail-python`.

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

## Related Documentation

- [Main README](../README.md) — project overview
- [docs/security.md](../docs/security.md) — application and database security posture
- [docs/environments.md](../docs/environments.md) — dev/test/prod profiles, Railway deployment, database topology
- [CLAUDE.md](../CLAUDE.md) — development guidelines
