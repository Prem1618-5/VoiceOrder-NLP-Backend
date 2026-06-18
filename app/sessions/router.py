"""
Sessions router.

Routes:
  POST   /session/start              — create session
  POST   /session/{id}/message       — multi-turn utterance
  GET    /session/{id}/order         — current compiled order
  DELETE /session/{id}               — close + persist final order
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dependencies import get_current_user, get_db, get_redis, limiter
from app.orders.service import persist_order
from app.sessions.schemas import (
    MessageRequest,
    MessageResponse,
    SessionCreate,
    SessionCurrentOrder,
    SessionOrderItem,
    SessionOrderResponse,
)
from app.sessions.service import (
    close_session,
    create_session,
    delete_context,
    get_session,
    get_session_order,
    process_message,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Start ─────────────────────────────────────────────────────────────────────

@router.post(
    "/session/start",
    response_model=SessionCreate,
    status_code=201,
    summary="Start a new multi-turn ordering session",
)
async def start_session(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionCreate:
    """
    Create a new session row in PostgreSQL.
    Returns session_id, status, and expires_at.
    Redis context is initialised lazily on first message.
    """
    try:
        session = await create_session(db, current_user.id)
        await db.commit()
    except Exception as exc:
        logger.error("Session create error: %s", exc, exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")

    return SessionCreate(
        session_id=session.id,
        status=session.status,
        expires_at=session.expires_at,
    )


# ── Message ───────────────────────────────────────────────────────────────────

@router.post(
    "/session/{session_id}/message",
    response_model=MessageResponse,
    summary="Send a message turn to an active session",
    responses={
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Session not found or not active"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("60/minute")   # Data Security spec: 60 req/min
async def send_message(
    request: Request,
    session_id: uuid.UUID,
    body: MessageRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Process a new utterance in the context of an existing session.
    Merges entities into the running order; handles qty-only updates.

    Rate limit: **60 requests / minute per authenticated user**.
    """
    try:
        context = await process_message(
            db, redis, session_id, current_user.id, body.text
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Message process error: %s", exc, exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Unable to process request")

    order_data = context["current_order"]
    items = [SessionOrderItem(**i) for i in order_data.get("items", [])]
    updated_order = SessionCurrentOrder(
        items=items, total_price=order_data.get("total_price")
    )

    return MessageResponse(
        updated_order=updated_order,
        turn=context["turn"],
        context_applied=True,
    )


# ── Get current order ─────────────────────────────────────────────────────────

@router.get(
    "/session/{session_id}/order",
    response_model=SessionOrderResponse,
    summary="Get the current compiled order for a session",
    responses={
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Session not found or not active"},
    },
)
async def get_order(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> SessionOrderResponse:
    """
    Return the compiled order state from Redis for the given session.
    Validates session ownership before reading Redis (security isolation).
    """
    try:
        context = await get_session_order(db, redis, session_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Get order error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Session service unavailable")

    order_data = context["current_order"]
    items = [SessionOrderItem(**i) for i in order_data.get("items", [])]
    current_order = SessionCurrentOrder(
        items=items, total_price=order_data.get("total_price")
    )

    return SessionOrderResponse(
        session_id=session_id,
        turn=context["turn"],
        current_order=current_order,
        status=context.get("status", "active"),
    )


# ── Delete / close ────────────────────────────────────────────────────────────

@router.delete(
    "/session/{session_id}",
    status_code=204,
    summary="Close a session and persist the final order",
    responses={
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Session not found or not active"},
    },
)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Close the session:
      1. Load final order from Redis
      2. Persist final order to PostgreSQL with session_id attached
      3. Mark session as closed in DB
      4. Delete Redis context key
    """
    session = await get_session(db, session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or not active")

    try:
        from app.sessions.service import load_context
        from app.nlp.schemas import ParsedOrder, OrderItem

        context = await load_context(redis, session_id, current_user.id)
        order_data = context.get("current_order", {})
        items_raw = order_data.get("items", [])

        if items_raw:
            # Reconstruct ParsedOrder for persist_order
            order_items = [OrderItem(**i) for i in items_raw]
            fake_parsed = ParsedOrder(
                items=order_items,
                confidence=0.0,
                for_review=False,
                raw_entities=[],
                processing_time_ms=0.0,
            )
            await persist_order(db, fake_parsed, current_user.id, session_id=session_id)

        await close_session(db, session)
        await db.commit()
        await delete_context(redis, session_id)

        logger.info("Session closed id=%s user=%s", session_id, current_user.id)

    except Exception as exc:
        logger.error("Session close error: %s", exc, exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")
