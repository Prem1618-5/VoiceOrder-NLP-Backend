"""
Orders endpoint integration tests.
Covers: parse success, validation, confidence, for_review, history pagination.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_parse_order_success(async_client: AsyncClient, auth_headers: dict):
    resp = await async_client.post(
        "/order/parse",
        json={"text": "I want 2 large pepperoni pizzas with extra cheese"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "confidence" in data
    assert "for_review" in data
    assert "processing_time_ms" in data
    assert data["processing_time_ms"] > 0


@pytest.mark.asyncio
async def test_parse_order_items_structure(async_client: AsyncClient, auth_headers: dict):
    resp = await async_client.post(
        "/order/parse",
        json={"text": "3 cokes"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    item = items[0]
    assert "name" in item
    assert "quantity" in item
    assert item["quantity"] >= 1


@pytest.mark.asyncio
async def test_parse_order_no_auth(async_client: AsyncClient):
    resp = await async_client.post(
        "/order/parse",
        json={"text": "I want a pizza"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_parse_order_text_too_short(async_client: AsyncClient, auth_headers: dict):
    resp = await async_client.post(
        "/order/parse",
        json={"text": "a"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_parse_order_text_too_long(async_client: AsyncClient, auth_headers: dict):
    resp = await async_client.post(
        "/order/parse",
        json={"text": "a" * 501},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_order_history_empty(async_client: AsyncClient, auth_headers: dict):
    resp = await async_client.get("/orders/history", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "orders" in data
    assert "total" in data
    assert isinstance(data["orders"], list)


@pytest.mark.asyncio
async def test_order_history_after_parse(async_client: AsyncClient, auth_headers: dict):
    # Parse one order
    await async_client.post(
        "/order/parse",
        json={"text": "2 chicken burgers"},
        headers=auth_headers,
    )
    resp = await async_client.get("/orders/history", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_order_history_pagination_params(async_client: AsyncClient, auth_headers: dict):
    resp = await async_client.get(
        "/orders/history?page=1&size=5", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["size"] == 5


@pytest.mark.asyncio
async def test_order_history_invalid_size(async_client: AsyncClient, auth_headers: dict):
    resp = await async_client.get(
        "/orders/history?size=200", headers=auth_headers
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_for_review_flag(async_client: AsyncClient, auth_headers: dict):
    """Low-signal input should produce for_review=True when confidence<0.6."""
    resp = await async_client.post(
        "/order/parse",
        json={"text": "something completely unclear blorp"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    if data["confidence"] < 0.6:
        assert data["for_review"] is True
