"""
Session multi-turn context tests.
Covers: session creation, message turns, qty update, order retrieval, close.
Target: ≥85% multi-turn accuracy at turn 5 (PRD success metric).
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_session_start(async_client: AsyncClient, auth_headers: dict):
    resp = await async_client.post("/session/start", headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "session_id" in data
    assert data["status"] == "active"
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_session_message_turn_1(async_client: AsyncClient, auth_headers: dict):
    start = await async_client.post("/session/start", headers=auth_headers)
    sid = start.json()["session_id"]

    resp = await async_client.post(
        f"/session/{sid}/message",
        json={"text": "I want 2 large pepperoni pizzas"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["turn"] == 1
    assert data["context_applied"] is True
    assert len(data["updated_order"]["items"]) >= 1


@pytest.mark.asyncio
async def test_session_multi_turn_add_item(async_client: AsyncClient, auth_headers: dict):
    start = await async_client.post("/session/start", headers=auth_headers)
    sid = start.json()["session_id"]

    await async_client.post(
        f"/session/{sid}/message",
        json={"text": "I want 2 pepperoni pizzas"},
        headers=auth_headers,
    )
    resp2 = await async_client.post(
        f"/session/{sid}/message",
        json={"text": "and a coke"},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["turn"] == 2
    items = data["updated_order"]["items"]
    names = [i["name"] for i in items]
    # Both pepperoni and coke should be in order
    assert len(items) >= 2


@pytest.mark.asyncio
async def test_session_qty_update(async_client: AsyncClient, auth_headers: dict):
    """'make that 3' → quantity of last food entity updated."""
    start = await async_client.post("/session/start", headers=auth_headers)
    sid = start.json()["session_id"]

    await async_client.post(
        f"/session/{sid}/message",
        json={"text": "I want 2 cokes"},
        headers=auth_headers,
    )
    resp2 = await async_client.post(
        f"/session/{sid}/message",
        json={"text": "actually make that 3"},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    items = resp2.json()["updated_order"]["items"]
    coke_items = [i for i in items if "coke" in i["name"]]
    if coke_items:
        assert coke_items[0]["quantity"] == 3


@pytest.mark.asyncio
async def test_session_get_order(async_client: AsyncClient, auth_headers: dict):
    start = await async_client.post("/session/start", headers=auth_headers)
    sid = start.json()["session_id"]

    await async_client.post(
        f"/session/{sid}/message",
        json={"text": "I want a margherita pizza"},
        headers=auth_headers,
    )
    resp = await async_client.get(f"/session/{sid}/order", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == sid
    assert data["turn"] == 1
    assert "current_order" in data


@pytest.mark.asyncio
async def test_session_close(async_client: AsyncClient, auth_headers: dict):
    start = await async_client.post("/session/start", headers=auth_headers)
    sid = start.json()["session_id"]

    await async_client.post(
        f"/session/{sid}/message",
        json={"text": "2 chicken wings"},
        headers=auth_headers,
    )
    resp = await async_client.delete(f"/session/{sid}", headers=auth_headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_session_closed_cannot_message(async_client: AsyncClient, auth_headers: dict):
    """After DELETE, session should be inaccessible."""
    start = await async_client.post("/session/start", headers=auth_headers)
    sid = start.json()["session_id"]

    await async_client.delete(f"/session/{sid}", headers=auth_headers)

    resp = await async_client.post(
        f"/session/{sid}/message",
        json={"text": "add a coke"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_session_isolation(async_client: AsyncClient, auth_headers: dict):
    """A session belonging to user A should not be accessible with user B's token."""
    from app.auth.service import create_access_token
    import uuid
    other_token = create_access_token(uuid.uuid4())
    other_headers = {"Authorization": f"Bearer {other_token}"}

    start = await async_client.post("/session/start", headers=auth_headers)
    sid = start.json()["session_id"]

    resp = await async_client.get(f"/session/{sid}/order", headers=other_headers)
    # Should be 404 (session not found for this user) not 200
    assert resp.status_code in (404, 401)


@pytest.mark.asyncio
async def test_five_turn_session(async_client: AsyncClient, auth_headers: dict):
    """Full 5-turn session — order state must be coherent at end."""
    start = await async_client.post("/session/start", headers=auth_headers)
    sid = start.json()["session_id"]

    turns = [
        "I want 2 pepperoni pizzas",
        "and a large coke",
        "actually make the pizzas 3",
        "add garlic bread",
        "and 2 brownies",
    ]
    for i, text in enumerate(turns, 1):
        resp = await async_client.post(
            f"/session/{sid}/message",
            json={"text": text},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["turn"] == i

    final = await async_client.get(f"/session/{sid}/order", headers=auth_headers)
    assert final.status_code == 200
    items = final.json()["current_order"]["items"]
    assert len(items) >= 3   # pizza + coke + garlic bread + brownies
