"""Alembic env.

Alembic itself is synchronous — so we strip the `+asyncpg` suffix off
DATABASE_URL and use psycopg2 instead for the migration run. The
runtime keeps using asyncpg (see app/db/session.py). Both drivers are
listed as dependencies in pyproject.toml.

`target_metadata` points at `Base.metadata` from app.models so
`alembic revision --autogenerate` diffs against every model the app
loads.
"""
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Loading .env here so `alembic` invoked from the shell sees the same
# DATABASE_URL as uvicorn.
load_dotenv()

# Importing app.models registers User + Post on Base.metadata. If you
# add a new model, add it to app/models/__init__.py so Alembic sees it.
from app.models import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url() -> str:
    import os

    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        raise RuntimeError("DATABASE_URL not set — cannot run migrations")
    # postgresql+asyncpg://...  ->  postgresql+psycopg2://...
    return raw.replace("+asyncpg", "+psycopg2")


def run_migrations_offline() -> None:
    """Run migrations without an Engine, emitting raw SQL. Useful for
    generating a SQL bundle to apply by hand on a managed PG service."""
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg_section = config.get_section(config.config_ini_section) or {}
    cfg_section["sqlalchemy.url"] = _sync_url()
    connectable = engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
