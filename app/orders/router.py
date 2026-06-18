"""
Orders router.

Routes:
  POST /order/parse       — NLP parse, stateless, persists result
  GET  /orders/history    — paginated history for current user
"""
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dependencies import get_current_user, get_db, limiter
from app.nlp.pipeline import NLPPipeline
from app.orders.schemas import (
    OrderHistoryItem,
    OrderHistoryResponse,
    OrderParseRequest,
    OrderParseResponse,
)
from app.orders.service import get_order_history, get_pipeline, persist_order

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Parse ─────────────────────────────────────────────────────────────────────

@router.post(
    "/order/parse",
    response_model=OrderParseResponse,
    summary="Parse a natural-language order into structured JSON",
    responses={
        401: {"description": "Missing or invalid JWT"},
        422: {"description": "Pydantic validation error"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("20/minute")   # Data Security spec: 20 req/min per JWT sub
async def parse_order(
    request: Request,           # required by slowapi
    body: OrderParseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderParseResponse:
    """
    Run the 6-step NLP pipeline on the provided text.

    - Extracts FOOD / SIZE / MODIFIER / CARDINAL entities
    - Fuzzy-matches against menu_items table (rapidfuzz, cutoff=75)
    - Scores confidence; sets for_review=True when confidence < 0.6
    - Persists order to PostgreSQL
    - Returns structured JSON matching Technical Spec response schema

    Rate limit: **20 requests / minute per authenticated user**.
    """
    pipeline: NLPPipeline = get_pipeline()

    t0 = time.perf_counter()
    try:
        parsed = pipeline.parse(body.text)
    except Exception as exc:
        logger.error("NLP pipeline error: %s", exc, exc_info=True)
        # Data Security spec: no internals in 4xx/5xx responses
        raise HTTPException(status_code=500, detail="Unable to process request")

    # Persist — session_id is None for stateless parse (sessions attach their own)
    try:
        await persist_order(db, parsed, current_user.id, session_id=None)
        await db.commit()
    except Exception as exc:
        logger.error("Order persist error: %s", exc, exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")

    elapsed_ms = (time.perf_counter() - t0) * 1000

    return OrderParseResponse(
        items=[
            {
                "name": item.name,
                "quantity": item.quantity,
                "size": item.size,
                "modifiers": item.modifiers,
                "unit_price": item.unit_price,
                "matched_menu_item_id": item.matched_menu_item_id,
            }
            for item in parsed.items
        ],
        confidence=parsed.confidence,
        for_review=parsed.for_review,
        raw_entities=[e.model_dump() for e in parsed.raw_entities],
        processing_time_ms=round(elapsed_ms, 2),
    )


# ── History ───────────────────────────────────────────────────────────────────

@router.get(
    "/orders/history",
    response_model=OrderHistoryResponse,
    summary="Get paginated order history for the current user",
    responses={
        401: {"description": "Missing or invalid JWT"},
    },
)
async def order_history(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderHistoryResponse:
    """
    Return paginated order history for the authenticated user.
    Results are sorted newest-first.

    Pagination caps: page≥1, size≤100 (Data Security spec).
    """
    try:
        orders, total = await get_order_history(db, current_user.id, page, size)
    except Exception as exc:
        logger.error("History fetch error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")

    return OrderHistoryResponse(
        orders=[OrderHistoryItem.model_validate(o) for o in orders],
        total=total,
        page=page,
        size=size,
    )
