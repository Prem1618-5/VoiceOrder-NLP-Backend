"""
Async SQLAlchemy engine and session factory.

Connection: asyncpg + SSL (Supabase enforces TLS)
Pool:        max_size=10, min_size=2 (Data Security spec — prevent connection exhaustion)
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",  # SQL logging in dev only
    pool_size=10,
    max_overflow=0,
    pool_pre_ping=True,   # recycle stale connections gracefully
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,   # avoids implicit lazy-load after commit
    autocommit=False,
    autoflush=False,
)
