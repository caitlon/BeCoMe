# Database Security

How BeCoMe's PostgreSQL databases are locked down, and the runbooks for operating them.
Deployment topology -- which service connects to which database -- lives in
[`environments.md`](environments.md); this file covers roles, network exposure, auditing,
backups, and secret rotation.

## Roles and least privilege

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

## Network exposure

Production and staging databases answer only on Railway's private network
(`*.railway.internal`); their public TCP proxies were removed, so a leaked password is not the
sole barrier between the internet and the data. The dev database is the one exception, and even
there the proxy is normally closed -- it is opened in the Railway dashboard only for a specific
hands-on operation and shut again afterwards. That toggle is the project's substitute for an IP
allowlist, which Railway's platform does not offer.

## Audit logging

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

## Backups

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

## Secret rotation

Rotating the `become_app` password without downtime uses a second credential so there is never a
window where the application cannot connect:

1. Create a replacement login with the same grants -- `CREATE ROLE become_app_v2 LOGIN ...`,
   then apply the `scripts/db/roles.sql` grants to it (or set its password and copy the grants).
2. Point the environment's `DATABASE_URL` at `become_app_v2` in Railway and redeploy.
3. Confirm health is 200 and that `pg_stat_activity` shows connections from the new role.
4. Drop the old role: `DROP ROLE become_app;`. Rename `become_app_v2` back during a later quiet
   window if you want the canonical name restored.

`SECRET_KEY` rotates the same way: add the new value, redeploy, verify, then remove the old one.
