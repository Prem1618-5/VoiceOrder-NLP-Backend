"""
Auth tests — covers:
  POST /auth/register  (register, duplicate, weak password)
  POST /auth/token     (valid, wrong password, inactive user)
  JWT lifecycle        (valid token accepted, expired/invalid rejected)
  Protected route      (missing/bad token → 4xx)
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from jose import jwt

from app.auth.models import User
from app.auth.service import create_access_token, hash_password
from app.config import settings


# ── POST /auth/register ───────────────────────────────────────────────────────

async def test_register_success(client: AsyncClient) -> None:
    """New user registration returns 201 with correct fields."""
    payload = {"email": "newuser@test.dev", "password": "StrongPass99"}
    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newuser@test.dev"
    assert "id" in body
    assert "hashed_pw" not in body          # never exposed in response
    assert "password" not in body
    assert body["is_active"] is True


async def test_register_duplicate_email(client: AsyncClient, test_user: User) -> None:
    """Registering with an already-taken email returns 409."""
    payload = {"email": test_user.email, "password": "AnotherPass99"}
    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


async def test_register_password_too_short(client: AsyncClient) -> None:
    """Password shorter than 8 chars triggers 422 Pydantic validation."""
    payload = {"email": "short@test.dev", "password": "abc"}
    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 422


async def test_register_invalid_email(client: AsyncClient) -> None:
    """Malformed email triggers 422 Pydantic validation."""
    payload = {"email": "not-an-email", "password": "ValidPass99"}
    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 422


async def test_register_password_max_length(client: AsyncClient) -> None:
    """Password > 72 chars (bcrypt limit) triggers 422."""
    payload = {"email": "long@test.dev", "password": "A" * 73}
    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 422


# ── POST /auth/token ──────────────────────────────────────────────────────────

async def test_token_valid_credentials(client: AsyncClient, test_user: User) -> None:
    """
    Correct email + password returns 200 with an RS256 JWT.
    Token payload must contain `sub`, `exp`, `iat`.
    """
    payload = {"email": test_user.email, "password": "SecurePass123"}
    response = await client.post("/auth/token", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in_hours"] == int(settings.ACCESS_TOKEN_EXPIRE_HOURS)

    # Decode and validate claims
    decoded = jwt.decode(
        body["access_token"],
        settings.JWT_PUBLIC_KEY,
        algorithms=["RS256"],
    )
    assert decoded["sub"] == str(test_user.id)
    assert "exp" in decoded
    assert "iat" in decoded
    assert decoded["type"] == "access"


async def test_token_wrong_password(client: AsyncClient, test_user: User) -> None:
    """Wrong password returns 401 — no hint about which field is wrong."""
    payload = {"email": test_user.email, "password": "WrongPassword!"}
    response = await client.post("/auth/token", json=payload)

    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]
    # Confirm no internal details are leaked
    assert "password" not in response.text
    assert "hash" not in response.text


async def test_token_nonexistent_email(client: AsyncClient) -> None:
    """Non-existent email returns 401 with the same generic message (timing attack resistance)."""
    payload = {"email": "nobody@nowhere.dev", "password": "SomePass99"}
    response = await client.post("/auth/token", json=payload)

    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


async def test_token_inactive_user(
    client: AsyncClient, inactive_user: User
) -> None:
    """
    Inactive (disabled) user cannot obtain a token.
    authenticate_user() returns None for inactive users → 401.
    """
    payload = {"email": inactive_user.email, "password": "SecurePass123"}
    response = await client.post("/auth/token", json=payload)

    # authenticate_user returns None for inactive → 401 generic message
    assert response.status_code == 401


# ── JWT lifecycle tests (direct decode, no HTTP) ─────────────────────────────

def test_jwt_is_rs256(test_user: User) -> None:
    """create_access_token must produce an RS256 token."""
    token = create_access_token(test_user.id)
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "RS256"


def test_jwt_contains_required_claims(test_user: User) -> None:
    """Token payload must contain sub, exp, iat, type."""
    token = create_access_token(test_user.id)
    payload = jwt.decode(token, settings.JWT_PUBLIC_KEY, algorithms=["RS256"])
    assert payload["sub"] == str(test_user.id)
    assert "exp" in payload
    assert "iat" in payload
    assert payload["type"] == "access"


def test_jwt_expiry_is_correct(test_user: User) -> None:
    """Token expiry is ACCESS_TOKEN_EXPIRE_HOURS hours from now (±60s tolerance)."""
    before = datetime.now(timezone.utc)
    token = create_access_token(test_user.id)
    after = datetime.now(timezone.utc)

    payload = jwt.decode(token, settings.JWT_PUBLIC_KEY, algorithms=["RS256"])
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    expected_exp = before + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)

    assert abs((exp - expected_exp).total_seconds()) < 60


# ── Protected-route access ────────────────────────────────────────────────────

async def test_protected_route_no_token(client: AsyncClient) -> None:
    """Missing Authorization header → HTTPBearer raises 4xx (403 in FastAPI default)."""
    response = await client.get("/orders/history")
    assert response.status_code in (401, 403)


async def test_protected_route_invalid_token(client: AsyncClient) -> None:
    """Garbage token string → 401 Invalid token."""
    headers = {"Authorization": "Bearer not.a.valid.jwt"}
    response = await client.get("/orders/history", headers=headers)
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


async def test_protected_route_expired_token(
    client: AsyncClient, test_user: User
) -> None:
    """Manually crafted expired token → 401 Token expired."""
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": str(test_user.id),
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),   # already expired
        "type": "access",
    }
    expired_token = jwt.encode(
        expired_payload, settings.JWT_PRIVATE_KEY, algorithm="RS256"
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = await client.get("/orders/history", headers=headers)

    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


async def test_protected_route_wrong_algorithm_token(
    client: AsyncClient, test_user: User
) -> None:
    """
    Token signed with a different key but claiming RS256 → 401 Invalid token.
    Uses a freshly generated key that the server does not trust.
    """
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa as _rsa

    rogue_key = _rsa.generate_private_key(65537, 2048, default_backend())
    rogue_pem = rogue_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()

    from cryptography.hazmat.primitives import serialization
    rogue_pem = rogue_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()

    payload = {
        "sub": str(test_user.id),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "type": "access",
    }
    rogue_token = jwt.encode(payload, rogue_pem, algorithm="RS256")
    headers = {"Authorization": f"Bearer {rogue_token}"}
    response = await client.get("/orders/history", headers=headers)

    assert response.status_code == 401


async def test_protected_route_inactive_user_token(
    client: AsyncClient, inactive_user: User
) -> None:
    """
    Valid JWT for an inactive user → get_current_user raises 403 Account disabled.
    The token itself is valid, but the user.is_active check fails.
    """
    token = create_access_token(inactive_user.id)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/orders/history", headers=headers)

    assert response.status_code == 403
    assert "Account disabled" in response.json()["detail"]


# ── Error response format (Data Security spec) ───────────────────────────────

async def test_error_responses_have_no_stack_traces(client: AsyncClient) -> None:
    """
    4xx error responses must not contain stack traces or internal details.
    """
    response = await client.post("/auth/token", json={"email": "x@y.com", "password": "wrong"})
    body_text = response.text
    assert "Traceback" not in body_text
    assert "sqlalchemy" not in body_text.lower()
    assert "Exception" not in body_text
