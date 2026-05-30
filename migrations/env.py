"""Alembic migration environment for the BeCoMe database.

The database URL is resolved in this order: a direct ``ALEMBIC_DATABASE_URL``
override (handy for ad-hoc runs against one specific database), then application
settings -- ``migration_database_url`` (the privileged role used for DDL) falling
back to ``database_url``. This keeps migrations and the running application aimed
at the same database while allowing a separate privileged connection for schema
changes.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from api.config import get_settings
from api.db import models  # noqa: F401 -- imported so tables register on SQLModel.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _database_url() -> str:
    """Resolve the database URL Alembic should migrate.

    :return: A direct ``ALEMBIC_DATABASE_URL`` override when set, otherwise the
        privileged ``migration_database_url`` or the runtime ``database_url``.
    """
    override = os.environ.get("ALEMBIC_DATABASE_URL")
    if override:
        return override
    settings = get_settings()
    return settings.migration_database_url or settings.database_url


def _render_item(type_, obj, autogen_context):
    """Render SQLModel string types as plain SQLAlchemy strings.

    ``AutoString`` is equivalent to ``sa.String`` for DDL, so rendering it
    directly keeps generated migrations free of a ``sqlmodel`` import that
    linters would strip (leaving an undefined name).
    """
    if type_ == "type" and obj.__class__.__module__.startswith("sqlmodel"):
        length = getattr(obj, "length", None)
        return f"sa.String(length={length})" if length else "sa.String()"
    return False


def run_migrations_offline() -> None:
    """Run migrations in offline mode (emit SQL without a live DBAPI connection)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode against a live connection."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=connection.dialect.name == "sqlite",
            render_item=_render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
