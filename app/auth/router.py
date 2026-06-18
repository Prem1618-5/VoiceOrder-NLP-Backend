"""
Auth router — public endpoints (no JWT required).

Routes:
  POST /auth/register  → create account, return UserRead
  POST /auth/token     → verify credentials, return JWT (rate-limited: 5/min)
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import TokenRequest, TokenResponse, UserCreate, UserRead
from app.auth.service import authenticate_user, create_access_token, create_user
from app.dependencies import get_db, limiter

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Register ──────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserRead,
    status_code=201,
    summary="Create a new user account",
)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """
    Register a new user.
    Email must be unique; password is bcrypt-hashed (work factor 12).
    Returns the created user (no token — call /auth/token next).
    """
    try:
        user = await create_user(db, data)
    except ValueError as exc:
        # Email already registered — safe to surface this message
        raise HTTPException(status_code=409, detail=str(exc))

    logger.info("User registered: %s", user.email)
    return UserRead.model_validate(user)


# ── Token ─────────────────────────────────────────────────────────────────────

@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Obtain a JWT access token",
)
@limiter.limit("5/minute")          # Brute-force protection — IP-based
async def get_token(
    request: Request,               # required by slowapi
    data: TokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate with email + password.
    Returns an RS256 JWT valid for `ACCESS_TOKEN_EXPIRE_HOURS`.

    Rate limit: **5 requests / minute per IP** (brute-force protection).
    On failure: generic 401 — no hint about which field is wrong.
    """
    from app.config import settings  # local import to keep top of file clean

    user = await authenticate_user(db, data.email, data.password)
    if user is None:
        # Generic message — do not reveal whether email exists
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.id)
    logger.info("Token issued for user_id=%s", user.id)

    return TokenResponse(
        access_token=token,
        expires_in_hours=settings.ACCESS_TOKEN_EXPIRE_HOURS,
    )
