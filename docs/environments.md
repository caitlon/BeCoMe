# Environment Profiles

The backend runs under one of three profiles, chosen by the `APP_ENV` variable: `dev`, `test`, or `prod`. A separate flag, `TESTING`, marks an automated test run and works independently of the profile. This page is the reference for both.

## How selection works

`APP_ENV` is read from the process environment (shell, Docker, Railway, CI), not from a dotenv file, because it decides which file to load. Settings load `.env` first, then `.env.<APP_ENV>` on top, so a profile value overrides the shared base. When `APP_ENV` is unset, the dev profile applies.

| Profile | `APP_ENV` | Where it runs | Database | Debug | Rate limiting |
|---------|-----------|---------------|----------|-------|---------------|
| dev | unset or `dev` | Local machine | SQLite | on | on |
| test | `test` | Staging deploy and the test suite | PostgreSQL (staging), in-memory SQLite (tests) | off | on when deployed, off under pytest |
| prod | `prod` | Railway production | PostgreSQL | off | on |

## The two axes

`APP_ENV` and `TESTING` answer different questions and never substitute for each other.

- **`APP_ENV`** (`dev` / `test` / `prod`) is the deployment profile. It drives debug output, CORS origins, the database that is expected, and the production startup guard.
- **`TESTING`** (`1`/`true`) marks an automated test run. Only pytest and CI set it. It disables rate limiting and is never present on a deployed service.

This separation is what lets staging be realistic. A staging deploy sets `APP_ENV=test` with no `TESTING`, so its rate limits match production. The pytest suite sets `APP_ENV=test` together with `TESTING=1`, which keeps tests fast and lets them use in-memory SQLite.

## Profiles in detail

### dev

The default. SQLite, debug on, localhost CORS, no startup validation. Nothing has to be set to use it.

```bash
uv run uvicorn api.main:app --reload
```

### test (staging and the test suite)

Two consumers share this profile. A deployed staging service uses PostgreSQL with debug off and rate limiting on, which mirrors production for manual QA. The automated suite runs the same profile but adds `TESTING=1`, so it uses in-memory SQLite and turns rate limiting off. The test conftests set both variables before any `api` import.

### prod

PostgreSQL, debug off. The profile adds a startup guard: it rejects an empty or default `SECRET_KEY` and any `sqlite` `DATABASE_URL`. A misconfigured deploy fails immediately at startup instead of running with insecure defaults.

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

The `api` service in `docker/docker-compose.yml` reads `APP_ENV` with `${APP_ENV:-dev}`, so local Compose runs as dev unless you override it. `docker/Dockerfile.dev` pins `APP_ENV=dev`. The production `docker/Dockerfile` does not hardcode it; the value comes from the platform.

## CI

`.github/workflows/ci.yml` runs on every push and pull request to `main`, `develop`, and `staging`, so the deploy branches get the same full pipeline as `main`: lint, Python and frontend tests, backend and Playwright end-to-end tests, and SonarCloud (the last on pull requests only). It sets `APP_ENV=test` on the `python-tests`, `backend-e2e`, and `e2e` jobs, including the steps that start a live server. `scripts/ci/e2e-local.sh` sets the same value for local end-to-end runs.

## Development workflow

Each environment tracks one git branch, and a push to that branch redeploys the environment's Railway services.

| Branch | Environment | Profile | Services |
|--------|-------------|---------|----------|
| `develop` | dev | `APP_ENV=dev` | `dev-backend`, `dev-frontend`, `dev-db`, `dev-photos` |
| `staging` | test | `APP_ENV=test` | `test-backend`, `test-frontend`, `test-db`, `test-photos` |
| `main` | production | `APP_ENV=prod` | `prod-backend`, `prod-frontend`, `prod-db`, `prod-photos` |

Work moves in one direction. Cut a feature branch from `develop`, open a pull request back into `develop`, and the merge auto-deploys to dev for a first live check. When a slice is ready for QA, promote `develop` to `staging`; that deploy runs the `test` profile with production-like settings (rate limiting on, debug off), so manual testing is realistic. Promote `staging` to `main` to release, which deploys the `prod` profile and serves the public site. Hotfixes travel the same path instead of landing on `main` directly.

Each environment has its own isolated Railway Postgres (`*-db`) and its own Railway Storage Bucket for profile photos (`*-photos`). Supabase is no longer used for the database or for file storage.

## Railway deployment

The root `railway.toml` carries the API build and deploy settings: it points at `docker/Dockerfile` and the `/api/v1/health` check. Railway reads that file from the repository root for every service in the project, so the frontend cannot share it without trying to build the API image. The frontend service therefore has its own config file, `frontend/railway.json`, chosen per service through the Railway "Railway Config File" setting (the absolute path `/frontend/railway.json`); it pins `frontend/Dockerfile` and a `/` health check. Everything else that differs between environments lives in per-environment service variables.

| Variable | staging (test) | production (prod) |
|----------|----------------|-------------------|
| `APP_ENV` | `test` | `prod` |
| `SECRET_KEY` | strong value (`openssl rand -hex 32`) | strong value |
| `DATABASE_URL` | staging `become_app` role | production `become_app` role |
| `MIGRATION_DATABASE_URL` | privileged role, Alembic only | privileged role, Alembic only |
| `CORS_ORIGINS` | staging origin(s) | production origin(s) |
| `DEBUG` | `false` | `false` |
| `API_PUBLIC_URL` | staging API URL | production API URL |
| `VITE_API_URL` (frontend build arg) | staging API URL | production API URL |
| `BUCKET_NAME` / `BUCKET_ENDPOINT` / `BUCKET_ACCESS_KEY_ID` / `BUCKET_SECRET_ACCESS_KEY` | injected from `test-photos` | injected from `prod-photos` |

If `APP_ENV` is left unset on a deployed service, it falls back to dev, which turns debug on and opens CORS. Production must set `APP_ENV=prod` so the startup guard runs.

## Database schema and access

The schema is versioned with **Alembic**. Migrations live in `migrations/`; `migrations/env.py` reads its target from `MIGRATION_DATABASE_URL` (falling back to `DATABASE_URL`) and treats `SQLModel.metadata` as the source of truth. Every deploy runs `alembic upgrade head` once through the `preDeployCommand` in `railway.toml`, before the new version goes live, so a failed migration blocks the release instead of starting a broken one. `create_db_and_tables()` still builds the schema directly, but only for SQLite (local development) and `TESTING=1` runs (the end-to-end PostgreSQL); on a deployed database it is a no-op and Alembic stays in charge.

The application connects through a **least-privilege role**, `become_app`. It reads and writes the application tables but cannot create, alter, or drop objects, is not a superuser, and cannot bypass row-level security. Each backend therefore carries two database URLs: `DATABASE_URL` points at `become_app` for the running app, while `MIGRATION_DATABASE_URL` points at the privileged role that Alembic uses for DDL. The connection is hardened in `api/db/engine.py` -- TLS is required on deployed databases, each connection is tagged with an `application_name`, and per-session statement and idle-in-transaction timeouts stop a single query from monopolising the database. The schema also carries domain `CHECK` constraints (fuzzy-number ordering, positive expert counts, scale bounds) so the database rejects invalid rows on its own.

On production and staging each Postgres instance is reachable only over Railway's internal network: the public TCP proxies were removed, so those databases are no longer exposed to the internet. A proxy can be recreated briefly when a laptop needs direct access for a migration or a dump.

## Photo storage

Profile photos live in a per-environment Railway Storage Bucket (`dev-photos`, `test-photos`, `prod-photos`), reached over the S3 API. Buckets are private, so the backend serves each image itself through the public proxy `GET /api/v1/users/{id}/photo`; the `users.photo_url` column stores the object key, and responses carry the proxy URL built from `API_PUBLIC_URL`. Attaching a bucket to a service auto-injects `BUCKET_NAME`, `BUCKET_ENDPOINT`, `BUCKET_ACCESS_KEY_ID`, and `BUCKET_SECRET_ACCESS_KEY`; when they are absent (plain local runs), photo upload is disabled and the rest of the API keeps working.

## Current status

All three environments run entirely on Railway, each with its own isolated Postgres and photo bucket. The database layer is hardened the same way across them: Alembic owns the schema, the app connects as the least-privilege `become_app` role, and the production and staging databases are internal-only.

- **prod** is live: https://www.becomify.app (frontend) and https://api.becomify.app (API), `APP_ENV=prod`. Database is **Railway Postgres** (`prod-db`); profile photos live in a **Railway Storage Bucket** (`prod-photos`) served through the API photo proxy. Supabase is fully retired -- neither the database nor file storage uses it anymore.
- **test / staging** is live from `staging`: https://test-backend-staging.up.railway.app (API) and https://test-frontend-staging.up.railway.app, on its own Railway Postgres (`test-db`) and bucket (`test-photos`), `APP_ENV=test`.
- **dev** is deployed from `develop`: https://become-dev.up.railway.app (API) plus the dev frontend, on its own Railway Postgres (`dev-db`) and bucket (`dev-photos`). It also runs locally with no setup, since dev is the default profile.

## Where the code lives

The selector and guard are in `api/config.py`: `Environment` (the enum), `_resolve_environment()` (reads `APP_ENV`), `_env_files_for()` (builds the `.env` plus `.env.<stage>` list), and the `_validate_production_invariants` model validator (the prod guard). Rate limiting reads `settings.testing` in `api/middleware/rate_limit.py`.
