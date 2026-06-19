"""
Sessions service layer — multi-turn conversation context via Redis.

Redis key format : session:{session_id}   (UUID string)
Redis value      : JSON-serialised context dict (see _build_initial_context)
TTL              : SESSION_TTL seconds (1800 = 30 min), reset on every message

Context dict shape (mirrors Technical Spec Redis Session Schema):
{
  "session_id"      : "uuid-string",
  "user_id"         : "uuid-string",
  "turn"            : 3,
  "current_order"   : {"items": [...], "total_price": 38.97},
  "last_food_entity": "pepperoni pizza",
  "conversation"    : [
      {"turn": 1, "input": "...", "entities": [...], "timestamp": "..."},
      ...
  ]
}

Security (Data Security spec):
  session_id is validated against user_id from JWT before every Redis read/write.
  Users cannot read or write another user's session.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.nlp.pipeline import extract_entities
from app.nlp.schemas import ParsedOrder
from app.orders.models import Order
from app.orders.service import _compute_total
from app.sessions.models import Session

logger = logging.getLogger(__name__)

SESSION_TTL = 1800  # 30 minutes in seconds
MAX_CONVERSATION = 20  # cap stored turns to limit Redis value size


# ── Redis key helper ──────────────────────────────────────────────────────────


def _redis_key(session_id: uuid.UUID) -> str:
    """Return the Redis key for a session. Format: session:{uuid}"""
    return f"session:{session_id}"


# ── Context builder ───────────────────────────────────────────────────────────


def _build_initial_context(session_id: uuid.UUID, user_id: uuid.UUID) -> Dict[str, Any]:
    """Create the blank Redis context for a freshly created session."""
    return {
        "session_id": str(session_id),
        "user_id": str(user_id),
        "turn": 0,
        "current_order": {"items": [], "total_price": 0.0},
        "last_food_entity": None,
        "conversation": [],
    }


# ── Entity merging (core multi-turn logic) ────────────────────────────────────


def _merge_order_updates(
    context: Dict[str, Any], parsed: ParsedOrder
) -> Tuple[Dict[str, Any], bool]:
    """
    Merge NLP results from a new utterance into the existing session order.

    Handles three cases:
      1. New FOOD entities  → add to order, or update qty/mods if already present
      2. Only CARDINAL, no FOOD  → "make that 3" updates qty of last_food_entity
      3. Only MODIFIER, no FOOD  → applies modifier to last_food_entity

    Returns:
        (updated context, context_applied flag)
        context_applied=True means the utterance modified the existing order
        rather than starting fresh.
    """
    current_order: Dict[str, Any] = context.get(
        "current_order", {"items": [], "total_price": 0.0}
    )
    last_food: Optional[str] = context.get("last_food_entity")
    items: List[Dict[str, Any]] = current_order.get("items", [])
    context_applied = False

    has_food = bool(parsed.items)

    if not has_food:
        # ── Case 2: quantity update ("make that 3", "change that to 2") ───────
        cardinal_ents = [e for e in parsed.raw_entities if e.label == "CARDINAL"]
        modifier_ents = [e for e in parsed.raw_entities if e.label == "MODIFIER"]

        if cardinal_ents and last_food:
            try:
                new_qty = int(cardinal_ents[0].text)
                for item in items:
                    if item.get("name") == last_food:
                        item["quantity"] = new_qty
                        context_applied = True
                        logger.debug(
                            "Multi-turn qty update: '%s' → qty=%d", last_food, new_qty
                        )
                        break
            except (ValueError, IndexError):
                pass

        # ── Case 3: modifier update ("extra cheese", "no onions") ─────────────
        if modifier_ents and last_food:
            for item in items:
                if item.get("name") == last_food:
                    existing_mods: List[str] = item.setdefault("modifiers", [])
                    for mod in modifier_ents:
                        mod_text = mod.text
                        if mod_text not in existing_mods:
                            existing_mods.append(mod_text)
                            context_applied = True
                    break

    else:
        # ── Case 1: new food items ────────────────────────────────────────────
        for new_item in parsed.items:
            new_item_dict = new_item.model_dump()
            existing = next((i for i in items if i.get("name") == new_item.name), None)
            if existing:
                # Update in-place (quantity + modifiers may have changed)
                existing["quantity"] = new_item.quantity
                existing["modifiers"] = new_item.modifiers
                if new_item.size:
                    existing["size"] = new_item.size
                if new_item.unit_price is not None:
                    existing["unit_price"] = new_item.unit_price
                context_applied = True
                logger.debug("Multi-turn update existing item: '%s'", new_item.name)
            else:
                items.append(new_item_dict)
                logger.debug("Multi-turn new item: '%s'", new_item.name)

            last_food = new_item.name

    # Recompute running total
    total = _compute_total(items)
    current_order["items"] = items
    current_order["total_price"] = total
    context["current_order"] = current_order
    context["last_food_entity"] = last_food

    return context, context_applied


# ── Internal context loader with ownership check ──────────────────────────────


async def _load_context(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    redis: aioredis.Redis,
) -> Dict[str, Any]:
    """
    Load session context from Redis and verify user ownership.

    Redis Security spec:
        session_id validated against user_id from JWT before Redis read.
        Returns generic error to avoid information leakage.

    Raises:
        ValueError: if session missing, expired, or owned by a different user.
    """
    key = _redis_key(session_id)
    raw = await redis.get(key)

    if raw is None:
        raise ValueError("Session not found or expired")

    context = json.loads(raw)

    # Ownership check — users cannot access other sessions
    if context.get("user_id") != str(user_id):
        raise ValueError("Session not found or expired")

    return context


# ── Public service functions ──────────────────────────────────────────────────


async def create_session(
    user_id: uuid.UUID,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> Session:
    """
    Create a new multi-turn session.

    1. Insert Session row into PostgreSQL.
    2. Initialise blank context in Redis with SESSION_TTL.

    Returns the ORM Session instance (contains id, created_at, expires_at).
    """
    session = Session(user_id=user_id)
    db.add(session)
    await db.flush()
    await db.refresh(session)

    context = _build_initial_context(session.id, user_id)
    await redis.set(_redis_key(session.id), json.dumps(context), ex=SESSION_TTL)

    logger.info("Session created | id=%s user=%s", session.id, user_id)
    return session


async def process_message(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    text: str,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> Tuple[Dict[str, Any], int, bool]:
    """
    Process a new utterance within an existing session.

    Multi-turn flow:
      1. Load context from Redis (with ownership check)
      2. Run NLP pipeline on new utterance
      3. Merge new entities into existing order
      4. Increment turn counter
      5. Append to conversation history (capped at MAX_CONVERSATION)
      6. Save back to Redis with reset TTL
      7. Update turn_count in PostgreSQL session record

    Args:
        session_id: UUID of the target session.
        user_id:    Authenticated user's UUID (for ownership check).
        text:       New utterance text.
        db:         Active async DB session.
        redis:      Async Redis client.

    Returns:
        (updated_order dict, turn number, context_applied flag)

    Raises:
        ValueError: if session not found, expired, or ownership mismatch.
    """
    # Step 1 — load + ownership check
    context = await _load_context(session_id, user_id, redis)

    # Step 2 — NLP
    parsed: ParsedOrder = extract_entities(text)

    # Step 3 — merge
    context, context_applied = _merge_order_updates(context, parsed)

    # Step 4 — increment turn
    context["turn"] = context.get("turn", 0) + 1
    turn = context["turn"]

    # Step 5 — conversation history (bounded)
    conversation: List[Dict[str, Any]] = context.get("conversation", [])
    conversation.append(
        {
            "turn": turn,
            "input": text,
            "entities": [e.model_dump() for e in parsed.raw_entities],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    if len(conversation) > MAX_CONVERSATION:
        conversation = conversation[-MAX_CONVERSATION:]
    context["conversation"] = conversation

    # Step 6 — save back to Redis (reset TTL on every message)
    await redis.set(_redis_key(session_id), json.dumps(context), ex=SESSION_TTL)

    # Step 7 — update PostgreSQL session metadata
    stmt = select(Session).where(Session.id == session_id)
    result = await db.execute(stmt)
    db_session: Optional[Session] = result.scalar_one_or_none()
    if db_session is not None:
        db_session.turn_count = turn
        db.add(db_session)

    logger.info(
        "Session message processed | id=%s turn=%d context_applied=%s items=%d",
        session_id,
        turn,
        context_applied,
        len(context["current_order"].get("items", [])),
    )
    return context["current_order"], turn, context_applied


async def get_session_order(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    redis: aioredis.Redis,
) -> Dict[str, Any]:
    """
    Return the current compiled order for an active session.
    Raises ValueError if session not found, expired, or ownership mismatch.
    """
    context = await _load_context(session_id, user_id, redis)
    return {
        "session_id": str(session_id),
        "turn": context.get("turn", 0),
        "status": "active",
        "current_order": context.get("current_order", {}),
        "last_food_entity": context.get("last_food_entity"),
    }


async def close_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> None:
    """
    Close and finalise a session:

    1. Load context from Redis (ownership check).
    2. Persist final order to PostgreSQL as 'confirmed' (if items exist).
    3. Mark Session row as 'closed' in PostgreSQL.
    4. Delete Redis key.

    Raises ValueError if session not found, expired, or ownership mismatch.
    """
    # Step 1
    context = await _load_context(session_id, user_id, redis)
    current_order: Dict[str, Any] = context.get(
        "current_order", {"items": [], "total_price": 0.0}
    )

    # Step 2 — persist final order only if items were collected
    items = current_order.get("items", [])
    if items:
        final_order = Order(
            user_id=user_id,
            session_id=session_id,
            items=items,
            total_price=current_order.get("total_price", 0.0),
            status="confirmed",
            confidence=None,  # aggregate confidence not tracked at session level
            for_review=False,
        )
        db.add(final_order)
        logger.info(
            "Final order persisted for session | session=%s items=%d total=%.2f",
            session_id,
            len(items),
            current_order.get("total_price", 0.0),
        )

    # Step 3 — close session row
    stmt = select(Session).where(Session.id == session_id)
    result = await db.execute(stmt)
    db_session: Optional[Session] = result.scalar_one_or_none()
    if db_session is not None:
        db_session.status = "closed"
        db_session.turn_count = context.get("turn", 0)
        db.add(db_session)

    # Step 4 — evict from Redis
    await redis.delete(_redis_key(session_id))

    logger.info("Session closed | id=%s turns=%d", session_id, context.get("turn", 0))
