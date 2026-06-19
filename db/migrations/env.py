"""
Alembic migration environment — async engine configuration.

Uses SQLAlchemy's async_engine_from_config so migrations run through
the same asyncpg driver as the application (no separate psycopg2 install).

Model discovery: all ORM models are imported here so Alembic can detect
schema changes via Base.metadata. The import order must follow FK dependencies:
  1. users (no FKs)
  2. menu_items (no FKs)
  3. sessions (FK → users)
  4. orders (FK → users, sessions)
"""
import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Ensure project root is on sys.path ────────────────────────────────────────
# Allows `from db.base import Base` etc. when running `alembic upgrade head`
# from the project root.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Inject DATABASE_URL from environment (overrides alembic.ini placeholder) ─
_db_url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
config.set_main_option("sqlalchemy.url", _db_url)

# ── Model discovery — import ALL models so metadata is populated ──────────────
from db.base import Base             # noqa: E402
from app.auth.models import User     # noqa: E402, F401
from app.orders.models import MenuItem, Order  # noqa: E402, F401
from app.sessions.models import Session        # noqa: E402, F401

target_metadata = Base.metadata


# ── Offline mode (generates SQL without connecting) ───────────────────────────

def run_migrations_offline() -> None:
    """
    Emit SQL to stdout without a live DB connection.
    Useful for dry-run reviews before applying to prod.
    """
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


# ── Online mode (async engine) ────────────────────────────────────────────────

def _do_run_migrations(connection: Connection) -> None:
    """Synchronous inner function passed to run_sync."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Build an async engine and run migrations through it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,   # disposable connection for migrations
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode."""
    asyncio.run(run_async_migrations())


# ── Dispatch ──────────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
