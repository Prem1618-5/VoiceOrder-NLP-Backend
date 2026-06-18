"""
pytest fixtures for VoiceOrder test suite.

Provides:
  - async_client   — TestClient with overridden DB + Redis
  - db_session     — isolated AsyncSession per test (rolled back after)
  - mock_redis     — fakeredis async instance
  - auth_headers   — valid JWT headers for a test user
  - test_pipeline  — real NLP pipeline instance (loaded once)
"""
import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.service import create_access_token, create_user
from app.auth.schemas import UserCreate
from app.config import settings
from app.dependencies import get_db, get_redis
from app.main import app as fastapi_app
from app.nlp.pipeline import NLPPipeline
from app.orders.service import set_pipeline, seed_default_menu
from db.base import Base

# ── In-memory SQLite for tests (async) ───────────────────────────────────────
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """Create all tables once per session, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Isolated DB session — rolls back after each test."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="session")
async def fake_redis() -> FakeRedis:
    """fakeredis async instance — shared across session."""
    return FakeRedis()


@pytest_asyncio.fixture(scope="session")
async def nlp_pipeline() -> NLPPipeline:
    """Load NLP pipeline once per session (expensive)."""
    pipeline = NLPPipeline()
    await pipeline.load()
    set_pipeline(pipeline)
    return pipeline


@pytest_asyncio.fixture
async def async_client(
    db_session: AsyncSession, fake_redis: FakeRedis, nlp_pipeline: NLPPipeline
) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient with dependency overrides:
      - get_db   → test SQLite session
      - get_redis → fakeredis instance
    """
    async def _get_test_db():
        yield db_session

    async def _get_test_redis():
        yield fake_redis

    fastapi_app.dependency_overrides[get_db] = _get_test_db
    fastapi_app.dependency_overrides[get_redis] = _get_test_redis

    # Seed menu for NLP menu matching
    await seed_default_menu(db_session)
    await db_session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as client:
        yield client

    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession):
    """Create and return a test user."""
    user = await create_user(
        db_session,
        UserCreate(email=f"test_{uuid.uuid4().hex[:6]}@example.com", password="testpass123"),
    )
    await db_session.commit()
    return user


@pytest_asyncio.fixture
def auth_headers(test_user) -> dict:
    """Return Authorization headers with a valid JWT for test_user."""
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}
