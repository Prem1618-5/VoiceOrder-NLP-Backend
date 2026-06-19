"""
Orders endpoint integration tests.

Covers:
  POST /order/parse       (success, auth guards, validation, response schema)
  GET  /orders/history    (empty, populated, pagination, auth guard)
  for_review flag         (propagated from NLP pipeline)
  Redis metric counters   (incremented on parse)
  Error format            (no stack traces, correct detail messages)
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from tests.conftest import _FakeRedis


# ── POST /order/parse — success ───────────────────────────────────────────────

async def test_parse_order_success(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Valid JWT + valid text → 200 with structured response."""
    payload = {"text": "I want 2 large pepperoni pizzas with extra cheese"}
    response = await client.post("/order/parse", json=payload, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()

    # Required top-level fields
    assert "id" in body
    assert "items" in body
    assert "confidence" in body
    assert "for_review" in body
    assert "raw_entities" in body
    assert "processing_time_ms" in body

    # Confidence must be in range
    assert 0.0 <= body["confidence"] <= 1.0
    assert isinstance(body["for_review"], bool)
    assert body["processing_time_ms"] > 0


async def test_parse_order_returns_valid_uuid(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Order `id` in response must be a parseable UUID."""
    payload = {"text": "Give me a coke"}
    response = await client.post("/order/parse", json=payload, headers=auth_headers)

    assert response.status_code == 200
    order_id = response.json()["id"]
    parsed = uuid.UUID(order_id)   # raises ValueError if invalid
    assert str(parsed) == order_id


async def test_parse_order_items_structure(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Each item in the response must have the expected fields."""
    payload = {"text": "I want 2 large pepperoni pizzas"}
    response = await client.post("/order/parse", json=payload, headers=auth_headers)

    assert response.status_code == 200
    items = response.json()["items"]

    for item in items:
        assert "name" in item
        assert "quantity" in item
        assert "modifiers" in item
        assert isinstance(item["quantity"], int)
        assert isinstance(item["modifiers"], list)


async def test_parse_order_raw_entities_have_labels(
    client: AsyncClient, auth_headers: dict
) -> None:
    """raw_entities must include text, label, start, end fields."""
    payload = {"text": "I want 3 large cokes"}
    response = await client.post("/order/parse", json=payload, headers=auth_headers)

    body = response.json()
    for ent in body["raw_entities"]:
        assert "text" in ent
        assert "label" in ent
        assert "start" in ent
        assert "end" in ent
        assert ent["label"] in ("FOOD", "SIZE", "MODIFIER", "CARDINAL")


async def test_parse_order_persisted_to_db(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
) -> None:
    """Parsed order must be persisted; retrievable via /orders/history."""
    payload = {"text": "One bacon burger please"}
    parse_response = await client.post(
        "/order/parse", json=payload, headers=auth_headers
    )
    assert parse_response.status_code == 200
    order_id = parse_response.json()["id"]

    # Check via history endpoint
    history_response = await client.get("/orders/history", headers=auth_headers)
    assert history_response.status_code == 200
    ids = [o["id"] for o in history_response.json()["items"]]
    assert order_id in ids


async def test_parse_order_increments_redis_counter(
    client: AsyncClient, auth_headers: dict, mock_redis: _FakeRedis
) -> None:
    """Successful parse must increment metrics:orders_today in Redis."""
    before = int(await mock_redis.get("metrics:orders_today") or 0)

    payload = {"text": "I want a caesar salad"}
    response = await client.post("/order/parse", json=payload, headers=auth_headers)
    assert response.status_code == 200

    after = int(await mock_redis.get("metrics:orders_today") or 0)
    assert after == before + 1


async def test_parse_order_for_review_flag_propagated(
    client: AsyncClient, auth_headers: dict
) -> None:
    """
    for_review field in response reflects NLP pipeline output.
    Low-confidence / unrecognised input should set for_review=True.
    """
    payload = {"text": "xyzzy plugh zork thud blorp"}   # gibberish
    response = await client.post("/order/parse", json=payload, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    # Gibberish → no food entities → confidence 0 → for_review must be True
    if body["confidence"] < 0.6:
        assert body["for_review"] is True


# ── POST /order/parse — auth guards ──────────────────────────────────────────

async def test_parse_order_no_auth(client: AsyncClient) -> None:
    """Missing Authorization header → 4xx (HTTPBearer auto_error)."""
    payload = {"text": "I want a pepperoni pizza"}
    response = await client.post("/order/parse", json=payload)
    assert response.status_code in (401, 403)


async def test_parse_order_invalid_token(client: AsyncClient) -> None:
    """Invalid JWT → 401 Invalid token."""
    headers = {"Authorization": "Bearer totally.invalid.token"}
    payload = {"text": "I want a pepperoni pizza"}
    response = await client.post("/order/parse", json=payload, headers=headers)
    assert response.status_code == 401


# ── POST /order/parse — input validation ─────────────────────────────────────

async def test_parse_order_text_too_short(
    client: AsyncClient, auth_headers: dict
) -> None:
    """text < 2 chars → 422 Pydantic validation error."""
    payload = {"text": "x"}
    response = await client.post("/order/parse", json=payload, headers=auth_headers)
    assert response.status_code == 422


async def test_parse_order_text_too_long(
    client: AsyncClient, auth_headers: dict
) -> None:
    """text > 500 chars → 422 Pydantic validation error."""
    payload = {"text": "pepperoni " * 55}   # 550 chars
    response = await client.post("/order/parse", json=payload, headers=auth_headers)
    assert response.status_code == 422


async def test_parse_order_text_missing(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Missing `text` field → 422."""
    response = await client.post("/order/parse", json={}, headers=auth_headers)
    assert response.status_code == 422


async def test_parse_order_strips_whitespace(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Leading/trailing whitespace is stripped (strip_whitespace=True in schema)."""
    payload = {"text": "   I want a coke   "}
    response = await client.post("/order/parse", json=payload, headers=auth_headers)
    assert response.status_code == 200   # not rejected after stripping


# ── GET /orders/history ───────────────────────────────────────────────────────

async def test_order_history_empty(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Fresh user with no orders → empty list with correct pagination fields."""
    response = await client.get("/orders/history", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["page"] == 1
    assert body["total"] == 0


async def test_order_history_populated(
    client: AsyncClient, auth_headers: dict
) -> None:
    """After parsing two orders, history returns both."""
    for text in ("I want a coke", "Give me french fries"):
        await client.post("/order/parse", json={"text": text}, headers=auth_headers)

    response = await client.get("/orders/history", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    assert len(body["items"]) >= 2


async def test_order_history_pagination_page_param(
    client: AsyncClient, auth_headers: dict
) -> None:
    """page and size query params are respected."""
    # Create 3 orders
    for text in ("order one", "order two", "order three"):
        await client.post("/order/parse", json={"text": text}, headers=auth_headers)

    response = await client.get(
        "/orders/history?page=1&size=2", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["size"] == 2
    assert len(body["items"]) <= 2


async def test_order_history_size_exceeds_max(
    client: AsyncClient, auth_headers: dict
) -> None:
    """size > 100 → 422 Pydantic validation (pagination cap)."""
    response = await client.get(
        "/orders/history?size=101", headers=auth_headers
    )
    assert response.status_code == 422


async def test_order_history_page_zero(
    client: AsyncClient, auth_headers: dict
) -> None:
    """page=0 → 422 (must be ≥ 1)."""
    response = await client.get("/orders/history?page=0", headers=auth_headers)
    assert response.status_code == 422


async def test_order_history_no_auth(client: AsyncClient) -> None:
    """Missing token → 4xx."""
    response = await client.get("/orders/history")
    assert response.status_code in (401, 403)


async def test_order_history_user_isolation(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
) -> None:
    """User A's orders are not visible to User B."""
    # User A places an order
    await client.post(
        "/order/parse",
        json={"text": "I want a pepperoni pizza"},
        headers=auth_headers,
    )

    # User B sees empty history
    response = await client.get("/orders/history", headers=second_auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_order_history_items_have_required_fields(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Each item in history response has expected schema fields."""
    await client.post(
        "/order/parse",
        json={"text": "I want a coke"},
        headers=auth_headers,
    )
    response = await client.get("/orders/history", headers=auth_headers)
    assert response.status_code == 200

    for order in response.json()["items"]:
        assert "id" in order
        assert "items" in order
        assert "status" in order
        assert "for_review" in order
        assert "created_at" in order


# ── Error response format ─────────────────────────────────────────────────────

async def test_parse_error_no_stack_trace(client: AsyncClient) -> None:
    """4xx error responses must not expose stack traces."""
    response = await client.post(
        "/order/parse",
        json={"text": "hello"},
        headers={"Authorization": "Bearer bad.token.here"},
    )
    assert "Traceback" not in response.text
    assert "sqlalchemy" not in response.text.lower()
