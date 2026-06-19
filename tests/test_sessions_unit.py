import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import ValidationError

from app.nlp.schemas import ParsedOrder, OrderItem, RawEntity
from app.orders.schemas import OrderParseRequest
from app.sessions.models import Session
from app.sessions.schemas import MessageRequest
from app.orders.models import Order
from app.sessions.service import (
    _redis_key,
    _build_initial_context,
    _merge_order_updates,
    _load_context,
    create_session,
    process_message,
    get_session_order,
    close_session,
)
from tests.conftest import _FakeRedis


def test_redis_key():
    session_id = uuid.uuid4()
    assert _redis_key(session_id) == f"session:{session_id}"


def test_build_initial_context():
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    context = _build_initial_context(session_id, user_id)
    assert context["session_id"] == str(session_id)
    assert context["user_id"] == str(user_id)
    assert context["turn"] == 0
    assert context["current_order"] == {"items": [], "total_price": 0.0}
    assert context["last_food_entity"] is None
    assert context["conversation"] == []


def test_merge_order_updates_new_food_items():
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    context = _build_initial_context(session_id, user_id)

    parsed = ParsedOrder(
        items=[
            OrderItem(
                name="pepperoni pizza",
                quantity=2,
                size="large",
                modifiers=["extra cheese"],
                unit_price=15.0,
            )
        ],
        confidence=0.9,
        for_review=False,
        raw_entities=[
            RawEntity(text="2", label="CARDINAL", start=0, end=1),
            RawEntity(text="large", label="SIZE", start=2, end=7),
            RawEntity(text="pepperoni pizza", label="FOOD", start=8, end=23),
            RawEntity(text="extra cheese", label="MODIFIER", start=29, end=41),
        ],
        processing_time_ms=10.0,
    )

    updated_context, context_applied = _merge_order_updates(context, parsed)
    assert context_applied is False
    assert len(updated_context["current_order"]["items"]) == 1
    assert updated_context["current_order"]["items"][0]["name"] == "pepperoni pizza"
    assert updated_context["current_order"]["items"][0]["quantity"] == 2
    assert updated_context["last_food_entity"] == "pepperoni pizza"


def test_merge_order_updates_update_existing_food_item():
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    context = _build_initial_context(session_id, user_id)
    context["current_order"] = {
        "items": [
            {
                "name": "pepperoni pizza",
                "quantity": 2,
                "size": "large",
                "modifiers": ["extra cheese"],
                "unit_price": 15.0,
            }
        ],
        "total_price": 30.0,
    }
    context["last_food_entity"] = "pepperoni pizza"

    parsed = ParsedOrder(
        items=[
            OrderItem(
                name="pepperoni pizza",
                quantity=3,
                size="large",
                modifiers=["extra cheese", "jalapenos"],
                unit_price=15.0,
            )
        ],
        confidence=0.9,
        for_review=False,
        raw_entities=[],
        processing_time_ms=10.0,
    )

    updated_context, context_applied = _merge_order_updates(context, parsed)
    assert context_applied is True
    assert len(updated_context["current_order"]["items"]) == 1
    assert updated_context["current_order"]["items"][0]["quantity"] == 3
    assert "jalapenos" in updated_context["current_order"]["items"][0]["modifiers"]


def test_merge_order_updates_quantity_update():
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    context = _build_initial_context(session_id, user_id)
    context["current_order"] = {
        "items": [
            {
                "name": "pepperoni pizza",
                "quantity": 2,
                "size": "large",
                "modifiers": ["extra cheese"],
                "unit_price": 15.0,
            }
        ],
        "total_price": 30.0,
    }
    context["last_food_entity"] = "pepperoni pizza"

    parsed = ParsedOrder(
        items=[],
        confidence=0.9,
        for_review=False,
        raw_entities=[RawEntity(text="3", label="CARDINAL", start=0, end=1)],
        processing_time_ms=10.0,
    )

    updated_context, context_applied = _merge_order_updates(context, parsed)
    assert context_applied is True
    assert updated_context["current_order"]["items"][0]["quantity"] == 3


def test_merge_order_updates_quantity_update_invalid():
    # Covers line 115-116 (ValueError/IndexError)
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    context = _build_initial_context(session_id, user_id)
    context["current_order"] = {
        "items": [
            {
                "name": "pepperoni pizza",
                "quantity": 2,
                "size": "large",
                "modifiers": ["extra cheese"],
                "unit_price": 15.0,
            }
        ],
        "total_price": 30.0,
    }
    context["last_food_entity"] = "pepperoni pizza"

    parsed = ParsedOrder(
        items=[],
        confidence=0.9,
        for_review=False,
        raw_entities=[
            RawEntity(text="not-a-number", label="CARDINAL", start=0, end=12)
        ],
        processing_time_ms=10.0,
    )

    updated_context, context_applied = _merge_order_updates(context, parsed)
    assert context_applied is False
    assert updated_context["current_order"]["items"][0]["quantity"] == 2


def test_merge_order_updates_modifier_update():
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    context = _build_initial_context(session_id, user_id)
    context["current_order"] = {
        "items": [
            {
                "name": "pepperoni pizza",
                "quantity": 2,
                "size": "large",
                "modifiers": ["extra cheese"],
                "unit_price": 15.0,
            }
        ],
        "total_price": 30.0,
    }
    context["last_food_entity"] = "pepperoni pizza"

    parsed = ParsedOrder(
        items=[],
        confidence=0.9,
        for_review=False,
        raw_entities=[RawEntity(text="mushrooms", label="MODIFIER", start=0, end=9)],
        processing_time_ms=10.0,
    )

    updated_context, context_applied = _merge_order_updates(context, parsed)
    assert context_applied is True
    assert "mushrooms" in updated_context["current_order"]["items"][0]["modifiers"]


@pytest.mark.asyncio
async def test_load_context_success():
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    redis = _FakeRedis()

    initial_context = _build_initial_context(session_id, user_id)
    await redis.set(f"session:{session_id}", json.dumps(initial_context))

    context = await _load_context(session_id, user_id, redis)
    assert context["session_id"] == str(session_id)
    assert context["user_id"] == str(user_id)


@pytest.mark.asyncio
async def test_load_context_missing():
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    redis = _FakeRedis()

    with pytest.raises(ValueError, match="Session not found or expired"):
        await _load_context(session_id, user_id, redis)


@pytest.mark.asyncio
async def test_load_context_ownership_mismatch():
    session_id = uuid.uuid4()
    user_id_a = uuid.uuid4()
    user_id_b = uuid.uuid4()
    redis = _FakeRedis()

    initial_context = _build_initial_context(session_id, user_id_a)
    await redis.set(f"session:{session_id}", json.dumps(initial_context))

    with pytest.raises(ValueError, match="Session not found or expired"):
        await _load_context(session_id, user_id_b, redis)


@pytest.mark.asyncio
async def test_create_session():
    user_id = uuid.uuid4()
    db = AsyncMock()
    db.add = MagicMock()  # db.add is synchronous
    redis = _FakeRedis()

    session = await create_session(user_id, db, redis)

    assert isinstance(session, Session)
    assert session.user_id == user_id
    db.add.assert_called_once()
    db.flush.assert_called_once()
    db.refresh.assert_called_once_with(session)

    # Check that initial Redis context is set
    raw = await redis.get(f"session:{session.id}")
    assert raw is not None
    context = json.loads(raw)
    assert context["session_id"] == str(session.id)
    assert context["user_id"] == str(user_id)


@pytest.mark.asyncio
async def test_get_session_order():
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    redis = _FakeRedis()

    initial_context = _build_initial_context(session_id, user_id)
    initial_context["turn"] = 2
    initial_context["current_order"] = {
        "items": [{"name": "pizza"}],
        "total_price": 10.0,
    }
    initial_context["last_food_entity"] = "pizza"
    await redis.set(f"session:{session_id}", json.dumps(initial_context))

    response = await get_session_order(session_id, user_id, redis)
    assert response["session_id"] == str(session_id)
    assert response["turn"] == 2
    assert response["status"] == "active"
    assert response["current_order"]["total_price"] == 10.0
    assert response["last_food_entity"] == "pizza"


@pytest.mark.asyncio
@patch("app.sessions.service.extract_entities")
async def test_process_message_success(mock_extract):
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    redis = _FakeRedis()
    db = AsyncMock()
    db.add = MagicMock()  # db.add is synchronous

    initial_context = _build_initial_context(session_id, user_id)
    await redis.set(f"session:{session_id}", json.dumps(initial_context))

    # Mock NLP response
    mock_extract.return_value = ParsedOrder(
        items=[OrderItem(name="coke", quantity=1, unit_price=2.0)],
        confidence=0.95,
        for_review=False,
        raw_entities=[RawEntity(text="coke", label="FOOD", start=0, end=4)],
        processing_time_ms=5.0,
    )

    # Mock PostgreSQL session retrieval
    db_session_obj = Session(id=session_id, user_id=user_id, turn_count=0)
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = db_session_obj
    db.execute.return_value = mock_execute_result

    updated_order, turn, context_applied = await process_message(
        session_id=session_id, user_id=user_id, text="add a coke", db=db, redis=redis
    )

    assert turn == 1
    assert context_applied is False
    assert len(updated_order["items"]) == 1
    assert updated_order["items"][0]["name"] == "coke"

    # Verify Redis context is updated
    raw = await redis.get(f"session:{session_id}")
    context = json.loads(raw)
    assert context["turn"] == 1
    assert len(context["conversation"]) == 1
    assert context["conversation"][0]["input"] == "add a coke"

    # Verify DB call
    assert db_session_obj.turn_count == 1
    db.add.assert_called_once_with(db_session_obj)


@pytest.mark.asyncio
@patch("app.sessions.service.extract_entities")
async def test_process_message_max_conversation(mock_extract):
    # Covers line 278 (MAX_CONVERSATION boundary)
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    redis = _FakeRedis()
    db = AsyncMock()
    db.add = MagicMock()

    initial_context = _build_initial_context(session_id, user_id)
    # Populate history with 20 items (MAX_CONVERSATION is 20)
    initial_context["conversation"] = [
        {"turn": i, "input": "dummy", "entities": [], "timestamp": ""}
        for i in range(20)
    ]
    await redis.set(f"session:{session_id}", json.dumps(initial_context))

    mock_extract.return_value = ParsedOrder(
        items=[OrderItem(name="coke", quantity=1, unit_price=2.0)],
        confidence=0.95,
        for_review=False,
        raw_entities=[],
        processing_time_ms=5.0,
    )

    db_session_obj = Session(id=session_id, user_id=user_id, turn_count=0)
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = db_session_obj
    db.execute.return_value = mock_execute_result

    await process_message(
        session_id=session_id, user_id=user_id, text="add a coke", db=db, redis=redis
    )

    # Verify Redis context history size is still 20 (truncated)
    raw = await redis.get(f"session:{session_id}")
    context = json.loads(raw)
    assert len(context["conversation"]) == 20


@pytest.mark.asyncio
async def test_close_session_with_items():
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    redis = _FakeRedis()
    db = AsyncMock()
    db.add = MagicMock()  # db.add is synchronous

    initial_context = _build_initial_context(session_id, user_id)
    initial_context["current_order"] = {
        "items": [{"name": "pepperoni pizza", "quantity": 1}],
        "total_price": 15.0,
    }
    await redis.set(f"session:{session_id}", json.dumps(initial_context))

    db_session_obj = Session(id=session_id, user_id=user_id, status="active")
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = db_session_obj
    db.execute.return_value = mock_execute_result

    await close_session(session_id, user_id, db, redis)

    # Verify Redis key is deleted
    assert await redis.get(f"session:{session_id}") is None

    # Verify final order and session status are updated and persisted
    assert db_session_obj.status == "closed"

    # Verify Order model instantiation and add
    called_args = [call[0][0] for call in db.add.call_args_list]
    orders = [x for x in called_args if isinstance(x, Order)]
    assert len(orders) == 1
    assert orders[0].session_id == session_id
    assert orders[0].total_price == 15.0
    assert orders[0].status == "confirmed"


# ── Schema validation: strip_whitespace ──────────────────────────────────────


class TestMessageRequestStripWhitespace:
    """Verify MessageRequest.text strips whitespace before applying min_length."""

    def test_whitespace_only_rejected(self):
        """Whitespace-only text → stripped to '' → fails min_length=1 → 422."""
        with pytest.raises(ValidationError):
            MessageRequest(text="   ")

    def test_empty_string_rejected(self):
        """Empty string → fails min_length=1."""
        with pytest.raises(ValidationError):
            MessageRequest(text="")

    def test_text_stripped(self):
        """Leading/trailing whitespace is stripped from valid text."""
        r = MessageRequest(text="  hello  ")
        assert r.text == "hello"

    def test_valid_text_passes(self):
        """Normal text passes validation."""
        r = MessageRequest(text="I want a pizza")
        assert r.text == "I want a pizza"

    def test_max_length_enforced(self):
        """Text exceeding 500 chars (after stripping) → fails max_length=500."""
        with pytest.raises(ValidationError):
            MessageRequest(text="a" * 501)


class TestOrderParseRequestStripWhitespace:
    """Verify OrderParseRequest.text strips whitespace before applying min_length."""

    def test_whitespace_only_rejected(self):
        """Whitespace-only text → stripped to '' → fails min_length=2 → 422."""
        with pytest.raises(ValidationError):
            OrderParseRequest(text="   ")

    def test_single_char_rejected(self):
        """Single char after stripping → fails min_length=2."""
        with pytest.raises(ValidationError):
            OrderParseRequest(text="  x  ")

    def test_text_stripped(self):
        """Leading/trailing whitespace is stripped from valid text."""
        r = OrderParseRequest(text="  hello world  ")
        assert r.text == "hello world"
