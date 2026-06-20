"""
FastAPI dependency injection providers.

  get_db()           → async SQLAlchemy session (auto-commit / rollback)
  get_redis()        → shared async Redis client
  get_current_user() → authenticated & active User instance
  limiter            → slowapi Limiter (imported in main.py + routers)
"""

import logging
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from slowapi import Limiter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.requests import Request

from app.config import settings

logger = logging.getLogger(__name__)

# ── Rate-limiter key function ─────────────────────────────────────────────────


def _rate_limit_key(request: Request) -> str:
    """
    Key strategy (per Data Security spec):
      • Authenticated requests  → keyed on JWT `sub` (user UUID)
      • Unauthenticated         → keyed on client IP (X-Forwarded-For or direct)
    This gives per-user limits on protected routes and IP limits on /auth/token.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            # Decode without expiry check (just want the sub for key)
            payload = jwt.decode(
                token,
                settings.JWT_PUBLIC_KEY,
                algorithms=["RS256"],
                options={"verify_exp": False},
            )
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except Exception:
            pass  # fall through to IP
    # IP fallback
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_rate_limit_key)

# ── Async SQLAlchemy engine + session factory ─────────────────────────────────

_engine = None
_AsyncSessionLocal = None


async def init_db():
    global _engine, _AsyncSessionLocal
    _engine = create_async_engine(
        settings.DATABASE_URL,
        echo=not settings.is_production,  # log SQL in dev / test only
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,  # recycle dead connections
        pool_timeout=30,
    )
    _AsyncSessionLocal = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def close_db():
    global _engine
    if _engine is not None:
        await _engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a transactional async DB session.
    Commits on clean exit, rolls back on exception.
    """
    if _AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized")
    async with _AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Redis client ──────────────────────────────────────────────────────────────

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """
    Return a shared async Redis client (lazy-init singleton).
    All responses decoded to str (decode_responses=True).
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _redis_client


# ── JWT Bearer auth ───────────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """
    Authentication middleware chain (Data Security spec, in order):
      1. Extract Authorization: Bearer <token>
      2. Verify RS256 signature with public key
      3. Check exp / iat / sub claims
      4. Load user from DB — verify is_active
      5. Return user (attached to request by FastAPI)

    Failure responses:
      missing token  → 401 "Not authenticated"   (HTTPBearer handles this)
      expired token  → 401 "Token expired"
      invalid sig    → 401 "Invalid token"
      inactive user  → 403 "Account disabled"
    """
    # Late import to avoid circular dependency at module load
    from app.auth.models import User  # noqa: PLC0415

    token = credentials.credentials

    # Steps 2 & 3 — decode and verify signature + claims
    try:
        payload = jwt.decode(
            token,
            settings.JWT_PUBLIC_KEY,
            algorithms=["RS256"],
            options={"require": ["exp", "iat", "sub"]},
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Step 4 — load user from DB
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user: User | None = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    return user
