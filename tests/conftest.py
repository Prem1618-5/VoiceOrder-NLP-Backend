"""
Pytest configuration and shared fixtures.

IMPORTANT — env vars are injected at the very top of this file,
before any app.* imports, so that pydantic-settings picks them up
on first access via the @lru_cache singleton.

Load order:
  1. Generate test RS256 keypair (cryptography library — no network)
  2. os.environ.setdefault() for every required var
  3. get_settings.cache_clear() — forces re-read if settings was already imported
  4. All app imports follow
"""

# ── Step 1 & 2 — keys + env vars (MUST be first) ─────────────────────────────
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _generate_rsa_keypair() -> tuple[str, str]:
    """Return (private_pem, public_pem) as strings."""
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


_PRIV, _PUB = _generate_rsa_keypair()

# setdefault: CI secrets already in env take precedence; local dev uses generated keys
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/voiceorder_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("ENVIRONMENT", "test")
# Direct assignment (not setdefault): CI secrets may be malformed/incompatible
# with test fixtures; generated keypair must always win in the test environment.
os.environ["JWT_PRIVATE_KEY"] = _PRIV
os.environ["JWT_PUBLIC_KEY"] = _PUB
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_HOURS", "1")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("NLP_CONFIDENCE_THRESHOLD", "0.6")
os.environ.setdefault("FUZZY_SCORE_CUTOFF", "75")

# ── Step 3 — clear settings cache so it re-reads env vars ────────────────────
from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

# ── Step 4 — all remaining imports ───────────────────────────────────────────
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from asgi_lifespan import LifespanManager  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth.models import User  # noqa: E402
from app.auth.service import create_access_token, hash_password  # noqa: E402
from app.config import settings  # noqa: E402
from app.dependencies import get_db, get_redis  # noqa: E402
from app.main import app  # noqa: E402
from db.base import Base  # noqa: E402

# Import all models so Base.metadata is fully populated before create_all
from app.orders.models import MenuItem, Order  # noqa: E402, F401
from app.sessions.models import Session  # noqa: E402, F401


# ── Test database engine (separate from production _engine in dependencies.py) ─
from sqlalchemy.pool import NullPool  # noqa: E402

_test_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)
_TestSessionLocal = async_sessionmaker(
    _test_engine, class_=AsyncSession, expire_on_commit=False
)


# ── In-memory Redis substitute ────────────────────────────────────────────────


class _FakeRedis:
    """
    Minimal async Redis substitute for unit / integration tests.
    Implements every method called by the application layer:
      get, set, delete, incr, incrby, ping
    No external dependency — pure Python dict.
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._store[key] = value
        # TTL is silently accepted but not enforced in tests
        return True

    async def delete(self, *keys: str) -> int:
        removed = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                removed += 1
        return removed

    async def incr(self, key: str) -> int:
        current = int(self._store.get(key, "0"))
        self._store[key] = str(current + 1)
        return current + 1

    async def incrby(self, key: str, amount: int) -> int:
        current = int(self._store.get(key, "0"))
        self._store[key] = str(current + amount)
        return current + amount

    async def ping(self) -> bool:
        return True

    def clear(self) -> None:
        self._store.clear()


# ── Session-scoped: create tables once, drop at end of suite ─────────────────


@pytest_asyncio.fixture(scope="session")
async def create_test_tables():
    """Create all ORM tables before the test session; drop them after."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _test_engine.dispose()


# ── Function-scoped: rolled-back transaction per test ────────────────────────


@pytest_asyncio.fixture
async def db_session(create_test_tables) -> AsyncSession:
    """
    Provide a transactional async DB session.
    All writes are rolled back after each test — no data leaks between tests.
    """
    async with _TestSessionLocal() as session:
        yield session
        await session.rollback()


# ── FakeRedis fixture (fresh store per test) ──────────────────────────────────


@pytest.fixture
def mock_redis() -> _FakeRedis:
    """Return a clean in-memory Redis substitute for each test."""
    return _FakeRedis()


# ── Async HTTP test client with dependency overrides ─────────────────────────


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, mock_redis: _FakeRedis) -> AsyncClient:
    """
    Async httpx client wired to the FastAPI app.
    Overrides:
      get_db    → test db_session (rolled back after each test)
      get_redis → _FakeRedis (in-memory, no TTL enforcement)
    """

    async def _override_get_db():
        yield db_session

    async def _override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


# ── Test user fixtures ────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create and persist a test user within the current transaction."""
    user = User(
        email="alice@voiceorder.dev",
        hashed_pw=hash_password("SecurePass123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Return Authorization header dict with a valid JWT for the test user."""
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def second_test_user(db_session: AsyncSession) -> User:
    """A second test user for cross-user isolation tests."""
    user = User(
        email="bob@voiceorder.dev",
        hashed_pw=hash_password("SecurePass123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def second_auth_headers(second_test_user: User) -> dict:
    """Authorization headers for the second test user."""
    token = create_access_token(second_test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def inactive_user(db_session: AsyncSession) -> User:
    """An inactive (disabled) user — used to test 403 Account disabled."""
    user = User(
        email="disabled@voiceorder.dev",
        hashed_pw=hash_password("SecurePass123"),
        is_active=False,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user
