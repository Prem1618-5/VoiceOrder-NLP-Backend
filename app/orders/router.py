"""
Orders router.

Routes:
  POST /order/parse       NLP parse + persist (JWT required, 20 req/min)
  GET  /orders/history    Paginated order history (JWT required)
"""

import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dependencies import get_current_user, get_db, get_redis, limiter
from app.orders.schemas import OrderParseRequest, OrderParseResponse, PaginatedOrders
from app.orders.service import get_history, parse_and_store

logger = logging.getLogger(__name__)
router = APIRouter()


# ── POST /order/parse ─────────────────────────────────────────────────────────


@router.post(
    "/order/parse",
    response_model=OrderParseResponse,
    status_code=200,
    summary="Parse a free-text order via NLP",
    responses={
        401: {"description": "Missing or invalid JWT"},
        422: {"description": "Validation error — text too short/long"},
        429: {"description": "Rate limit exceeded (20 req/min per user)"},
    },
)
@limiter.limit("20/minute")
async def parse_order(
    request: Request,  # required by slowapi
    body: OrderParseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> OrderParseResponse:
    """
    Parse a free-text restaurant order into structured JSON.

    **Rate limit:** 20 requests / minute per authenticated user.

    **Example:**
    ```
    POST /order/parse
    { "text": "I want 2 large pepperoni pizzas with extra cheese" }
    ```

    **Response includes:**
    - `items` — structured line-items with name, qty, size, modifiers, price
    - `confidence` — 0.0–1.0 score
    - `for_review` — true when confidence < 0.6
    - `raw_entities` — spaCy entity spans for debugging
    - `processing_time_ms` — end-to-end NLP latency
    """
    order, parsed = await parse_and_store(
        text=body.text,
        user_id=current_user.id,
        db=db,
    )

    # Best-effort metric instrumentation — never fail the request on Redis error
    try:
        await redis.incr("metrics:orders_today")
        await redis.incrby("metrics:latency_sum", int(parsed.processing_time_ms))
        await redis.incr("metrics:latency_count")
        if parsed.for_review:
            await redis.incr("metrics:for_review_today")
    except Exception:
        pass

    return OrderParseResponse(
        id=order.id,
        items=parsed.items,
        confidence=parsed.confidence,
        for_review=parsed.for_review,
        raw_entities=parsed.raw_entities,
        processing_time_ms=parsed.processing_time_ms,
    )


# ── GET /orders/history ───────────────────────────────────────────────────────


@router.get(
    "/orders/history",
    response_model=PaginatedOrders,
    summary="Paginated order history for the current user",
    responses={
        401: {"description": "Missing or invalid JWT"},
    },
)
async def order_history(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedOrders:
    """
    Return paginated history of parsed orders for the authenticated user.
    Orders are sorted most-recent-first.
    """
    return await get_history(
        user_id=current_user.id,
        page=page,
        size=size,
        db=db,
    )
