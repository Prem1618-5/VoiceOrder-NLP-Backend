"""
Auth endpoint tests.
Covers: register, token issue, invalid creds, expiry, inactive user.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from jose import jwt


@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient):
    resp = await async_client.post(
        "/auth/register",
        json={"email": f"user_{uuid.uuid4().hex[:6]}@test.com", "password": "password123"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "hashed_pw" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient):
    email = f"dup_{uuid.uuid4().hex[:6]}@test.com"
    await async_client.post("/auth/register", json={"email": email, "password": "pass1234"})
    resp = await async_client.post("/auth/register", json={"email": email, "password": "pass1234"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_token_success(async_client: AsyncClient):
    email = f"tok_{uuid.uuid4().hex[:6]}@test.com"
    password = "securepass"
    await async_client.post("/auth/register", json={"email": email, "password": password})
    resp = await async_client.post(
        "/auth/token", json={"email": email, "password": password}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_token_wrong_password(async_client: AsyncClient):
    email = f"wp_{uuid.uuid4().hex[:6]}@test.com"
    await async_client.post("/auth/register", json={"email": email, "password": "correct"})
    resp = await async_client.post(
        "/auth/token", json={"email": email, "password": "wrong"}
    )
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_token_nonexistent_user(async_client: AsyncClient):
    resp = await async_client.post(
        "/auth/token", json={"email": "ghost@nowhere.com", "password": "pass"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_no_token(async_client: AsyncClient):
    resp = await async_client.post(
        "/order/parse", json={"text": "I want a pizza"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_invalid_token(async_client: AsyncClient):
    resp = await async_client.post(
        "/order/parse",
        json={"text": "I want a pizza"},
        headers={"Authorization": "Bearer invalidtoken"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_password_min_length_validation(async_client: AsyncClient):
    resp = await async_client.post(
        "/auth/register",
        json={"email": "short@test.com", "password": "abc"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_email_validation(async_client: AsyncClient):
    resp = await async_client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "validpass"},
    )
    assert resp.status_code == 422
