"""
Sessions service layer.

Responsibilities:
  - Create / close DB session records
  - Manage multi-turn order state in Redis (TTL=1800s)
  - Merge new NLP entities into existing order context
  - Handle "make that 3" style quantity updates via last_food_entity
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.nlp.pipeline import NLPPipeline
from app.nlp.schemas import OrderItem, ParsedOrder
from app.orders.service import get_pipeline
from app.sessions.models import Session
from app.sessions.schemas import SessionCurrentOrder, SessionOrderItem

logger = logging.getLogger(__name__)

SESSION_TTL = 1800  # 30 minutes — matches PRD R07


# ── Redis key helpers ─────────────────────────────────────────────────────────

def _session_key(session_id: uuid.UUID) -> str:
    return f"session:{session_id}"


# ── DB helpers ────────────────────────────────────────────────────────────────

async def create_session(db: AsyncSession, user_id: uuid.UUID) -> Session:
    """Create a new active session row and return it."""
    session = Session(user_id=user_id, status="active", turn_count=0)
    db.add(session)
    await db.flush()
    await db.refresh(session)
    logger.info("Session created id=%s user=%s", session.id, user_id)
    return session


async def get_session(
    db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID
) -> Optional[Session]:
    """
    Fetch a session verifying it belongs to user_id.
    Redis Security spec: session_id validated against user_id before any read.
    """
    stmt = select(Session).where(
        Session.id == session_id,
        Session.user_id == user_id,
        Session.status == "active",
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def close_session(db: AsyncSession, session: Session) -> None:
    """Mark session as closed."""
    session.status = "closed"
    await db.flush()


# ── Redis context management ──────────────────────────────────────────────────

async def load_context(
    redis: Redis, session_id: uuid.UUID, user_id: uuid.UUID
) -> Dict[str, Any]:
    """
    Load session context from Redis.
    Returns empty context dict if key missing (first turn).
    Security: caller must have already validated session ownership via DB.
    """
    key = _session_key(session_id)
    raw = await redis.get(key)
    if raw is None:
        return {
            "session_id": str(session_id),
            "user_id": str(user_id),
            "turn": 0,
            "current_order": {"items": [], "total_price": None},
            "last_food_entity": None,
            "conversation": [],
        }
    return json.loads(raw)


async def save_context(
    redis: Redis, session_id: uuid.UUID, context: Dict[str, Any]
) -> None:
    """Persist context back to Redis with reset TTL."""
    key = _session_key(session_id)
    await redis.setex(key, SESSION_TTL, json.dumps(context))


async def delete_context(redis: Redis, session_id: uuid.UUID) -> None:
    """Remove session context from Redis (on DELETE /session/{id})."""
    await redis.delete(_session_key(session_id))


# ── Order merging logic ───────────────────────────────────────────────────────

def _merge_order(
    context: Dict[str, Any],
    parsed: ParsedOrder,
    raw_text: str,
) -> Dict[str, Any]:
    """
    Merge new parsed entities INTO existing session order.

    Rules (Technical Spec multi-turn context):
      1. If no FOOD entities found but CARDINAL found → update qty of last_food_entity
      2. If new FOOD entity matches existing item → update that item
      3. Otherwise append new items
    """
    current_items: List[Dict] = context["current_order"].get("items", [])
    last_food = context.get("last_food_entity")

    text_lower = raw_text.lower()

    # Detect "make that N" / "change to N" / qty-only update patterns
    qty_only_keywords = ["make that", "change to", "actually", "update", "change it"]
    is_qty_update = (
        any(kw in text_lower for kw in qty_only_keywords)
        and not parsed.items  # no new FOOD entities extracted
        and last_food is not None
    )

    if is_qty_update:
        # Extract CARDINAL from raw entities
        cardinals = [e for e in parsed.raw_entities if e.label == "CARDINAL"]
        if cardinals:
            try:
                new_qty = int(cardinals[0].text)
                for item in current_items:
                    if item.get("name") == last_food:
                        item["quantity"] = new_qty
                        logger.debug(
                            "Updated qty of '%s' to %d", last_food, new_qty
                        )
                        break
            except ValueError:
                pass
    else:
        for new_item in parsed.items:
            matched = False
            for existing in current_items:
                if existing.get("name") == new_item.name:
                    # Update existing — prefer new values
                    existing["quantity"] = new_item.quantity
                    if new_item.size:
                        existing["size"] = new_item.size
                    if new_item.modifiers:
                        existing["modifiers"] = new_item.modifiers
                    matched = True
                    break
            if not matched:
                current_items.append(new_item.model_dump())

        # Update last_food_entity to most recent FOOD
        if parsed.items:
            context["last_food_entity"] = parsed.items[-1].name

    # Recompute total_price
    total: Optional[float] = None
    if all(i.get("unit_price") is not None for i in current_items):
        total = round(
            sum((i.get("unit_price") or 0) * i.get("quantity", 1) for i in current_items),
            2,
        )

    context["current_order"] = {"items": current_items, "total_price": total}
    return context


# ── Public API used by router ─────────────────────────────────────────────────

async def process_message(
    db: AsyncSession,
    redis: Redis,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    text: str,
) -> Dict[str, Any]:
    """
    Core multi-turn logic:
      1. Verify session ownership via DB
      2. Load Redis context
      3. Run NLP pipeline
      4. Merge new entities into context
      5. Increment turn + save back to Redis
      6. Update turn_count in DB session row

    Returns updated context dict.
    Raises ValueError on session not found / expired.
    """
    session = await get_session(db, session_id, user_id)
    if session is None:
        raise ValueError("Session not found or not active")

    context = await load_context(redis, session_id, user_id)

    pipeline: NLPPipeline = get_pipeline()
    parsed: ParsedOrder = pipeline.parse(text)

    context = _merge_order(context, parsed, text)
    context["turn"] += 1
    context["conversation"].append({
        "turn": context["turn"],
        "input": text,
        "entities": [e.model_dump() for e in parsed.raw_entities],
    })

    await save_context(redis, session_id, context)

    # Sync turn_count to DB
    session.turn_count = context["turn"]
    await db.flush()

    return context


async def get_session_order(
    db: AsyncSession,
    redis: Redis,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Dict[str, Any]:
    """
    Return current compiled order for a session.
    Validates ownership via DB before touching Redis.
    """
    session = await get_session(db, session_id, user_id)
    if session is None:
        raise ValueError("Session not found or not active")
    context = await load_context(redis, session_id, user_id)
    context["status"] = session.status
    return context
