"""
Auth service layer.

Responsibilities:
  • Password hashing / verification (bcrypt work factor 12)
  • RS256 JWT creation (python-jose)
  • User creation and lookup (async SQLAlchemy)
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import UserCreate
from app.config import settings

logger = logging.getLogger(__name__)

# ── Password hashing ──────────────────────────────────────────────────────────
# bcrypt work factor 12 per Data Security spec

_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(password: str) -> str:
    """Return bcrypt hash (work factor 12) of plaintext password."""
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time comparison of plaintext password against stored hash."""
    return _pwd_context.verify(plain_password, hashed_password)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: uuid.UUID) -> str:
    """
    Create an RS256-signed JWT.

    Payload fields:
      sub  — user UUID string (standard claim)
      iat  — issued-at timestamp
      exp  — expiry timestamp (settings.ACCESS_TOKEN_EXPIRE_HOURS from now)
      type — "access" (helps distinguish token types if refresh added later)

    Key: JWT_PRIVATE_KEY env var (PEM — never in repo).
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire,
        "type": "access",
    }

    return jwt.encode(payload, settings.JWT_PRIVATE_KEY, algorithm="RS256")


# ── User CRUD ─────────────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Fetch a single user by email. Returns None if not found."""
    stmt = select(User).where(User.email == email.lower())
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """Fetch a user by primary key UUID. Returns None if not found."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    """
    Create a new user with a bcrypt-hashed password.
    Raises ValueError if the email is already registered.
    """
    existing = await get_user_by_email(db, data.email)
    if existing is not None:
        raise ValueError(f"Email '{data.email}' is already registered")

    user = User(
        email=data.email.lower(),
        hashed_pw=hash_password(data.password),
    )
    db.add(user)
    await db.flush()   # populate user.id before commit
    await db.refresh(user)
    logger.info("Created new user id=%s", user.id)
    return user


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> Optional[User]:
    """
    Verify email + password.
    Returns the User on success, None on failure.
    Always runs verify_password (constant-time) even when user not found
    to resist timing attacks.
    """
    user = await get_user_by_email(db, email)
    if user is None:
        # Run a dummy verify to keep response time constant
        _pwd_context.dummy_verify()
        return None

    if not verify_password(password, user.hashed_pw):
        return None

    if not user.is_active:
        return None

    return user
