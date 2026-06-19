"""
Orders service layer.

Responsibilities:
  • Run NLP pipeline on raw text and persist the structured result
  • Calculate total price from assembled items
  • Return paginated order history for a user
"""
import logging
import uuid
from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.nlp.pipeline import extract_entities
from app.nlp.schemas import ParsedOrder
from app.orders.models import Order
from app.orders.schemas import OrderSummary, PaginatedOrders

logger = logging.getLogger(__name__)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _compute_total(items: list) -> float:
    """
    Calculate total order price from assembled JSONB items.
    Each item: {"name": ..., "quantity": N, "unit_price": P, ...}
    Returns 0.0 if no items have a unit_price.
    """
    total = 0.0
    for item in items:
        price = item.get("unit_price") or 0.0
        qty = item.get("quantity", 1)
        total += float(price) * int(qty)
    return round(total, 2)


# ── Core service functions ────────────────────────────────────────────────────

async def parse_and_store(
    text: str,
    user_id: uuid.UUID,
    db: AsyncSession,
    session_id: Optional[uuid.UUID] = None,
) -> Tuple[Order, ParsedOrder]:
    """
    Run the NLP pipeline on `text` and persist the structured result.

    Args:
        text:       Raw order text from the user.
        user_id:    Authenticated user's UUID.
        db:         Active async DB session.
        session_id: Optional session UUID (for multi-turn orders).

    Returns:
        (Order ORM instance, ParsedOrder from NLP pipeline)
    """
    # ── NLP extraction ────────────────────────────────────────────────────────
    parsed: ParsedOrder = extract_entities(text)

    # ── Serialise items for JSONB storage ────────────────────────────────────
    items_json = [item.model_dump() for item in parsed.items]
    total = _compute_total(items_json)

    # ── Persist to PostgreSQL ─────────────────────────────────────────────────
    order = Order(
        user_id=user_id,
        session_id=session_id,
        items=items_json,
        total_price=total if total > 0 else None,
        status="pending",
        confidence=parsed.confidence,
        for_review=parsed.for_review,
    )
    db.add(order)
    await db.flush()       # populate order.id before commit
    await db.refresh(order)

    logger.info(
        "Order persisted | id=%s user=%s confidence=%.2f for_review=%s "
        "items=%d latency_ms=%.1f",
        order.id,
        user_id,
        parsed.confidence,
        parsed.for_review,
        len(parsed.items),
        parsed.processing_time_ms,
    )
    return order, parsed


async def get_history(
    user_id: uuid.UUID,
    page: int,
    size: int,
    db: AsyncSession,
) -> PaginatedOrders:
    """
    Return a paginated list of orders for the authenticated user.

    Args:
        user_id: Authenticated user's UUID.
        page:    1-indexed page number (enforced ≥ 1 by schema).
        size:    Items per page (enforced ≤ 100 by schema).
        db:      Active async DB session.
    """
    offset = (page - 1) * size

    # Total count (for pagination metadata)
    count_stmt = select(func.count(Order.id)).where(Order.user_id == user_id)
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    # Paginated data — most recent first
    data_stmt = (
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    data_result = await db.execute(data_stmt)
    orders = data_result.scalars().all()

    return PaginatedOrders(
        items=[OrderSummary.model_validate(o) for o in orders],
        page=page,
        size=size,
        total=total,
    )
