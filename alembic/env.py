"""
Alembic async migration environment.

Imports all SQLAlchemy models so autogenerate can detect schema changes.
Uses asyncpg driver configured in alembic.ini via DATABASE_URL env var.
"""
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Import ALL models here so Alembic sees them ───────────────────────────────
from db.base import Base
from app.auth.models import User          # noqa: F401
from app.orders.models import MenuItem, Order  # noqa: F401
from app.sessions.models import Session   # noqa: F401

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url from environment (Railway env var — never hardcoded)
database_url = os.environ.get("DATABASE_URL", "")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ── Offline migrations ────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Generate SQL script without connecting to DB."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations (async) ─────────────────────────────────────────────────

def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Connect to DB and run migrations using asyncpg."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

That's all 17 files. The full project is now complete and coherent end-to-end. Every file syncs with the previously generated code: same Base import path, same dependencies.py (get_db, get_redis, get_current_user, limiter), same NLPPipeline interface from pipeline.py, same config.settings fields, and same security rules from the Data Security spec throughout.
