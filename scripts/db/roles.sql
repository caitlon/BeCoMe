-- BeCoMe -- database role provisioning (idempotent, version-controlled source of truth)
--
-- Captures the least-privilege role setup that is provisioned on each Railway Postgres.
-- Safe to re-run. Apply per environment as the Railway superuser (`postgres`), e.g.:
--     psql "$SUPERUSER_DATABASE_URL" -f scripts/db/roles.sql
--
-- Role model -- two connection URLs, no SET ROLE switching:
--   * become_app -- least-privilege RUNTIME role used by DATABASE_URL.
--                   DML only, no DDL: NOSUPERUSER / NOCREATEDB / NOCREATEROLE / NOBYPASSRLS.
--   * postgres   -- the Railway-provisioned superuser, used by MIGRATION_DATABASE_URL for
--                   Alembic DDL. Railway gives exactly one superuser, so we do not add a
--                   separate `migrator` role (it would require an ownership refactor for no
--                   meaningful gain). `postgres` is managed by Railway and is never created
--                   or altered here.
--
-- Passwords are NOT stored in this file -- they live in Railway variables. On a fresh
-- provision, set the password out of band after running this script:
--     ALTER ROLE become_app PASSWORD '<value from Railway>';

-- 1. Least-privilege runtime role -------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'become_app') THEN
    CREATE ROLE become_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
  END IF;
END
$$;

-- Re-assert the privilege flags in case the role pre-existed with different attributes.
ALTER ROLE become_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

-- 2. Connect + schema usage (deliberately NO create) ------------------------------
-- Database name is the Railway default `railway`; adjust if an environment differs.
GRANT CONNECT ON DATABASE railway TO become_app;
GRANT USAGE ON SCHEMA public TO become_app;

-- 3. DML on existing objects ------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO become_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO become_app;

-- 4. DML on FUTURE objects (Alembic creates tables as the `postgres` superuser) ----
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO become_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO become_app;

-- 5. Lock down the public schema (PG15+ default; explicit for reproducibility) -----
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- 6. Deterministic search_path -- CVE-2018-1058 hardening for the exposed app role -
ALTER ROLE become_app SET search_path = pg_catalog, public;

-- 7. Resource limits at the role level (mirrors the client-side options= in engine.py)
ALTER ROLE become_app SET statement_timeout = '30s';
ALTER ROLE become_app SET idle_in_transaction_session_timeout = '60s';
ALTER ROLE become_app SET lock_timeout = '10s';
