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

`.github/workflows/ci.yml` sets `APP_ENV=test` on the `python-tests`, `backend-e2e`, and `e2e` jobs, including the steps that start a live server. `scripts/ci/e2e-local.sh` sets the same value for local end-to-end runs.

## Development workflow

Each environment tracks one git branch, and a push to that branch redeploys the environment's Railway services.

| Branch | Environment | Profile | Services |
|--------|-------------|---------|----------|
| `develop` | dev | `APP_ENV=dev` | `dev-backend`, `dev-frontend`, `dev-db` |
| `staging` | test | `APP_ENV=test` | staging backend, frontend, Postgres |
| `main` | production | `APP_ENV=prod` | `prod-backend`, `prod-frontend` (database on Supabase) |

Work moves in one direction. Cut a feature branch from `develop`, open a pull request back into `develop`, and the merge auto-deploys to dev for a first live check. When a slice is ready for QA, promote `develop` to `staging`; that deploy runs the `test` profile with production-like settings (rate limiting on, debug off), so manual testing is realistic. Promote `staging` to `main` to release, which deploys the `prod` profile and serves the public site. Hotfixes travel the same path instead of landing on `main` directly.

dev and test each use their own Railway Postgres, isolated from one another and from production. Production keeps its external Supabase database.

## Railway deployment

The root `railway.toml` carries the API build and deploy settings: it points at `docker/Dockerfile` and the `/api/v1/health` check. Railway reads that file from the repository root for every service in the project, so the frontend cannot share it without trying to build the API image. The frontend service therefore has its own config file, `frontend/railway.json`, chosen per service through the Railway "Railway Config File" setting (the absolute path `/frontend/railway.json`); it pins `frontend/Dockerfile` and a `/` health check. Everything else that differs between environments lives in per-environment service variables.

| Variable | staging (test) | production (prod) |
|----------|----------------|-------------------|
| `APP_ENV` | `test` | `prod` |
| `SECRET_KEY` | strong value (`openssl rand -hex 32`) | strong value |
| `DATABASE_URL` | staging PostgreSQL | production PostgreSQL |
| `CORS_ORIGINS` | staging origin(s) | production origin(s) |
| `DEBUG` | `false` | `false` |
| `VITE_API_URL` (frontend build arg) | staging API URL | production API URL |

If `APP_ENV` is left unset on a deployed service, it falls back to dev, which turns debug on and opens CORS. Production must set `APP_ENV=prod` so the startup guard runs.

## Current status

All three environments run on Railway, each with its own isolated Railway Postgres:

- **prod** is live: https://www.becomify.app (frontend) and https://api.becomify.app (API), `APP_ENV=prod`. Its database is **Railway Postgres** (`prod-db`), migrated off Supabase with `pg_dump`/`pg_restore`. Supabase is retained only for file storage (user photos), not for the database.
- **test / staging** is live from `staging`: https://test-backend-staging.up.railway.app (API) and https://test-frontend-staging.up.railway.app, on its own Railway Postgres (`test-db`), `APP_ENV=test`.
- **dev** is deployed from `develop`: https://become-dev.up.railway.app (API) plus the dev frontend, on its own Railway Postgres (`dev-db`). It also runs locally with no setup, since dev is the default profile.

## Where the code lives

The selector and guard are in `api/config.py`: `Environment` (the enum), `_resolve_environment()` (reads `APP_ENV`), `_env_files_for()` (builds the `.env` plus `.env.<stage>` list), and the `_validate_production_invariants` model validator (the prod guard). Rate limiting reads `settings.testing` in `api/middleware/rate_limit.py`.
