# Environment profiles

The backend runs under one of three profiles, chosen by the `APP_ENV` variable: `dev`, `test`, or `prod`. A separate flag, `TESTING`, marks an automated test run and works independently of the profile. This page is the reference for both.

## How selection works

Settings read `APP_ENV` from the process environment (shell, Docker, Railway, CI), not from a dotenv file, because that value decides which file to load. The loader then reads `.env` first, then `.env.<APP_ENV>` on top, so a profile value overrides the shared base. When `APP_ENV` is unset, the dev profile applies.

| Profile | `APP_ENV` | Where it runs | Database | Debug | Rate limiting |
|---------|-----------|---------------|----------|-------|---------------|
| dev | unset or `dev` | Local machine and the Railway dev service | SQLite locally, PostgreSQL on Railway | off (the `.env.dev.example` template turns it on) | on |
| test | `test` | Staging deploy and the test suite | PostgreSQL (staging), in-memory SQLite (tests) | off | on when deployed, off under pytest |
| prod | `prod` | Railway production | PostgreSQL | off | on |

## The two axes

`APP_ENV` and `TESTING` answer different questions and never substitute for each other.

- **`APP_ENV`** (`dev` / `test` / `prod`) is the deployment profile. It drives debug output, CORS origins, the database it expects, and the deploy startup guard.
- **`TESTING`** (`1`/`true`) marks an automated test run. Only pytest and CI set it. It disables rate limiting and the deploy startup checks, and is never present on a deployed service.

This separation is what lets staging be realistic. A staging deploy sets `APP_ENV=test` with no `TESTING`, so its rate limits match production. The pytest suite sets `APP_ENV=test` together with `TESTING=1`, which keeps tests fast and lets them use in-memory SQLite.

## Profiles in detail

### dev

The default. SQLite, debug on, localhost CORS, no startup validation. It needs no configuration.

```bash
uv run uvicorn api.main:app --reload
```

### test (staging and the test suite)

Two consumers share this profile. A deployed staging service uses PostgreSQL with debug off and rate limiting on, which mirrors production for manual QA. It meets the same startup invariants as production: a strong secret, PostgreSQL, Redis, a privileged `MIGRATION_DATABASE_URL`, the Cloudflare origin secret, non-localhost `CORS_ORIGINS`, a non-loopback `FRONTEND_BASE_URL`, a working email provider, and debug off. The automated suite runs the same profile but adds `TESTING=1`, so it uses in-memory SQLite, turns rate limiting off, and skips the startup guard. The test conftests set both variables before any `api` import.

### prod

PostgreSQL, debug off. Every deployed service runs a startup guard (`_validate_deploy_invariants` in `api/config.py`), the Railway dev service included: the guard keys off the deploy, not the profile name. A weak or default `SECRET_KEY`, a `sqlite` `DATABASE_URL`, a missing `REDIS_URL`, or localhost-only `CORS_ORIGINS` fails startup immediately, rather than running with insecure defaults. So does a missing `CLOUDFLARE_ORIGIN_SECRET`, which proves requests came through the Cloudflare edge. Each deployed environment needs its own value, paired with a Transform Rule for that environment's API host.

## Configuration files

| File | Role |
|------|------|
| `api/config.py` | Defines the `Environment` enum, resolves `APP_ENV`, builds the dotenv list, and runs the prod guard |
| `.env` | Shared base values, loaded first (gitignored) |
| `.env.<stage>` | Per-profile overrides, loaded second (gitignored) |
| `.env.dev.example`, `.env.test.example`, `.env.prod.example` | Tracked templates to copy from |
| `frontend/.env.development`, `.env.production`, `.env.test`, `.env.staging` | Vite per-mode values, mainly `VITE_API_URL` |

## Local use

Copy the template for the profile you want, then fill in the real values:

```bash
cp .env.dev.example .env.dev      # local development
cp .env.test.example .env.test    # staging-like run
cp .env.prod.example .env.prod    # production-like run
```

Pick a profile by exporting `APP_ENV`:

```bash
APP_ENV=dev uv run uvicorn api.main:app --reload
APP_ENV=prod uv run uvicorn api.main:app
```

## Docker

The `api` service in `docker/docker-compose.yml` reads `APP_ENV` with `${APP_ENV:-dev}`, so local Compose runs as dev unless you override it. `docker/Dockerfile.dev` pins `APP_ENV=dev`. The production `docker/Dockerfile` does not hardcode it. The value comes from the platform.

## CI

`.github/workflows/ci.yml` runs on every push and pull request to `main`, `develop`, and `staging`, so the deploy branches get the same full pipeline as `main`. That pipeline covers lint, Python and frontend tests, backend and Playwright end-to-end tests, and SonarCloud (the last on pull requests and on pushes to `main`). It sets `APP_ENV=test` on the `python-tests`, `backend-e2e`, and `e2e` jobs, including the steps that start a live server. `scripts/ci/e2e-local.sh` sets the same value for local end-to-end runs.

## Development workflow

Each environment tracks one git branch, and a push to that branch redeploys the environment's Railway services.

| Branch | Environment | Profile | Services |
|--------|-------------|---------|----------|
| `develop` | dev | `APP_ENV=dev` | `dev-backend`, `dev-frontend`, `dev-db`, `dev-photos` |
| `staging` | test | `APP_ENV=test` | `test-backend`, `test-frontend`, `test-db`, `test-photos` |
| `main` | production | `APP_ENV=prod` | `prod-backend`, `prod-frontend`, `prod-db`, `prod-photos` |

Work moves in one direction. Cut a feature branch from `develop`, open a pull request back into `develop`, and the merge auto-deploys to dev for a first live check. When a slice is ready for QA, promote `develop` to `staging`. That deploy runs the `test` profile with production-like settings (rate limiting on, debug off), so manual testing is realistic. Promote `staging` to `main` to release, which deploys the `prod` profile and serves the public site. Hotfixes travel the same path instead of landing on `main` directly.

Each environment has its own isolated Railway Postgres (`*-db`) and its own Railway Storage Bucket for profile photos (`*-photos`).

## Railway deployment

The root `railway.toml` carries the API build and deploy settings: it points at `docker/Dockerfile` and the `/api/v1/health` check. Railway reads that file from the repository root for every service in the project, so the frontend cannot share it without trying to build the API image. The frontend service therefore has its own config file, `frontend/railway.json`, chosen per service through the Railway "Railway Config File" setting (the absolute path `/frontend/railway.json`). It pins `frontend/Dockerfile` and a `/` health check. Everything else that differs between environments lives in per-environment service variables.

| Variable | dev | staging (test) | production (prod) |
|----------|-----|----------------|-------------------|
| `APP_ENV` | `dev` | `test` | `prod` |
| `SECRET_KEY` | strong value (`openssl rand -hex 32`) | strong value | strong value |
| `DATABASE_URL` | dev `become_app` role | staging `become_app` role | production `become_app` role |
| `MIGRATION_DATABASE_URL` | privileged role, Alembic only | privileged role, Alembic only | privileged role, Alembic only |
| `CORS_ORIGINS` | dev origins | staging origins | production origins |
| `REDIS_URL` | dev Redis | staging Redis | production Redis |
| `CLOUDFLARE_ORIGIN_SECRET` | own secret | own secret | own secret, each matching that environment's Cloudflare Transform Rule |
| `DEBUG` | `false` | `false` | `false` |
| `LOG_LEVEL` | `DEBUG` | `INFO` | `INFO` |
| `API_PUBLIC_URL` | dev API URL | staging API URL | production API URL |
| `VITE_API_URL` / `VITE_SENTRY_DSN` / `VITE_APP_ENV` (frontend build args) | dev values | staging values | production values |
| `BUCKET_NAME` / `BUCKET_ENDPOINT` / `BUCKET_ACCESS_KEY_ID` / `BUCKET_SECRET_ACCESS_KEY` | injected from `dev-photos` | injected from `test-photos` | injected from `prod-photos` |

A deployed service that leaves `APP_ENV` unset falls back to the dev profile. The startup guard still runs there, because it keys off `RAILWAY_ENVIRONMENT_NAME` rather than the profile name, so an unset variable cannot weaken a deploy. Set the profile explicitly anyway (`dev`, `test`, or `prod`), so that the log level, the log format, and the `.env.<APP_ENV>` overlay are the ones you meant.

`LOG_LEVEL` appears as a service variable even though `api/config.py` already defaults it per profile (`DEBUG` on dev, `INFO` on test and prod). The default is the safety net for a service whose variable was never set. The variable is what makes the level visible to whoever opens the service without reading the settings module. An explicit value always wins over the profile default.

Log format follows the deploy, not the profile. `api/logging_config.py` emits human-readable text only when the profile is dev *and* `RAILWAY_ENVIRONMENT_NAME` is absent, i.e. on a laptop. The Railway `dev` service is a deploy, so it emits JSON like staging and production and its `extra` fields stay indexable in the drain.

In `frontend/Dockerfile`, declare an `ARG` and an `ENV` for every `VITE_*` variable the SPA reads. Railway passes service variables to the build as build args, but Docker only exposes the ones the Dockerfile declares. Vite then inlines `undefined` for anything missing at build time, silently and with no build error. That gap left `VITE_SENTRY_DSN` set on all three frontend services while `Sentry.init` was tree-shaken out of every bundle.

## Database schema and access

**Alembic** versions the schema. Migrations live in `migrations/`. `migrations/env.py` reads its target from `ALEMBIC_DATABASE_URL`, then `MIGRATION_DATABASE_URL`, then `DATABASE_URL`, and treats `SQLModel.metadata` as the source of truth. Every deploy runs `alembic upgrade head` once through the `preDeployCommand` in `railway.toml`, before the new version goes live, so a failed migration blocks the release instead of starting a broken one. `create_db_and_tables()` still builds the schema directly, but only for SQLite (local development) and `TESTING=1` runs (the end-to-end PostgreSQL). On a deployed database it is a no-op and Alembic stays in charge.

The application connects through a **least-privilege role**, `become_app`. It reads and writes the application tables but cannot create, alter, or drop objects, is not a superuser, and cannot bypass row-level security. Each backend therefore carries two database URLs: `DATABASE_URL` points at `become_app` for the running app, while `MIGRATION_DATABASE_URL` points at the privileged role that Alembic uses for DDL. `api/db/engine.py` hardens the connection: it requires TLS on deployed databases, tags each connection with an `application_name`, and sets per-session statement and idle-in-transaction timeouts so one query cannot monopolize the database. The schema also carries domain `CHECK` constraints (fuzzy-number ordering, positive expert counts, scale bounds) so the database rejects invalid rows on its own.

On production and staging each Postgres instance is reachable only over Railway's internal network: the public TCP proxies are gone, so the internet cannot reach those databases. A proxy can be recreated briefly when a laptop needs direct access for a migration or a dump.

## Photo storage

Profile photos live in a per-environment Railway Storage Bucket (`dev-photos`, `test-photos`, `prod-photos`), reached over the S3 API. Buckets are private, so the backend serves each image itself through the public proxy `GET /api/v1/users/{id}/photo`. The `users.photo_url` column stores the object key, and responses carry the proxy URL built from `API_PUBLIC_URL`. Attaching a bucket to a service auto-injects `BUCKET_NAME`, `BUCKET_ENDPOINT`, `BUCKET_ACCESS_KEY_ID`, and `BUCKET_SECRET_ACCESS_KEY`. When they are absent (plain local runs), photo upload switches off and the rest of the API keeps working.

## Email delivery

Registration and password reset both send mail through `EMAIL_PROVIDER` (`console`, which logs the link, or `http`, a Resend-style API, described in `api/README.md`). Registration now depends on delivery in a way password reset never did: the account is created unverified, and nobody can log in to it until someone opens its activation link. A deployment whose mail provider is broken or misconfigured therefore creates accounts nobody can activate. The deploy guard already required a working provider for password reset (`_validate_deploy_invariants` in `api/config.py` fails startup on a deployed service without one). That same check now also gates whether a fresh signup is usable.

Two settings gate the address checks in `api/services/email_policy.py` that run before a registration reaches the database, both on by default. `DISPOSABLE_EMAIL_BLOCKING_ENABLED` rejects a vendored list of known disposable-mail domains. `MX_CHECK_ENABLED` rejects a domain with no MX, A, or AAAA record, and a resolver timeout or other inconclusive result fails open rather than rejecting. Either check can be turned off with a Railway variable, no redeploy needed, if it starts rejecting real signups. `EMAIL_VERIFICATION_TOKEN_TTL_HOURS` (default `24`) sets how long an activation link stays redeemable. That is longer than the one-hour password-reset window, because people routinely open an activation email the next morning.

## Current status

All three environments run entirely on Railway, each with its own isolated Postgres and photo bucket. The database layer is hardened the same way across them: Alembic owns the schema, the app connects as the least-privilege `become_app` role, and the production and staging databases are internal-only.

- **prod** is live: https://www.becomify.app (frontend) and https://api.becomify.app (API), `APP_ENV=prod`. Database is **Railway Postgres** (`prod-db`). Profile photos live in a **Railway Storage Bucket** (`prod-photos`) served through the API photo proxy.
- **test / staging** is live from `staging`: https://harbor.becomify.app (frontend) and https://api-harbor.becomify.app (API), on its own Railway Postgres (`test-db`) and bucket (`test-photos`), `APP_ENV=test`.
- **dev** deploys from `develop`: https://atelier.becomify.app (frontend) and https://api-atelier.becomify.app (API), on its own Railway Postgres (`dev-db`) and bucket (`dev-photos`). It also runs locally with no setup, since dev is the default profile.

Dev and staging moved off their generated `*.up.railway.app` hosts on 2026-07-31. They had to. `up.railway.app` is on the Public Suffix List, so a frontend and an API on two of those hosts count as different sites. The browser never sent the `SameSite=Strict` session cookies between them. Login answered `200` and the next request answered `401`, which looked like a broken session rather than a domain-topology problem. Production was never affected, since `www.becomify.app` and `api.becomify.app` share one registrable domain. The names avoid `dev` and `staging` so guessing does not find the environments. Certificate Transparency logs publish the certificates anyway, so that is a speed bump rather than access control. Adding a domain, the `_railway-verify` TXT record a proxied CNAME needs, and the cutover order are covered by the `cloudflare-operations` skill.

## Where the code lives

The selector and guard live in `api/config.py`: `Environment` (the enum), `_resolve_environment()` (reads `APP_ENV`), `_env_files_for()` (builds the `.env` plus `.env.<stage>` list), and the `_validate_deploy_invariants` model validator, which guards `prod` and a deployed `test`. Rate limiting reads `settings.testing` in `api/middleware/rate_limit.py`.
