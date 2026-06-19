"""
Sessions router — multi-turn conversation management.

Routes:
  POST   /session/start           Create session (20 req/min)
  POST   /session/{id}/message    Process utterance (60 req/min per spec)
  GET    /session/{id}/order      Retrieve current compiled order
  DELETE /session/{id}            Close session + persist final order
"""
import logging
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dependencies import get_current_user, get_db, get_redis, limiter
from app.sessions.schemas import (
    MessageRequest,
    MessageResponse,
    SessionOrderResponse,
    SessionStartResponse,
)
from app.sessions.service import (
    close_session,
    create_session,
    get_session_order,
    process_message,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/session")


# ── POST /session/start ───────────────────────────────────────────────────────

@router.post(
    "/start",
    response_model=SessionStartResponse,
    status_code=201,
    summary="Start a new multi-turn ordering session",
    responses={
        401: {"description": "Missing or invalid JWT"},
    },
)
@limiter.limit("20/minute")
async def start_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> SessionStartResponse:
    """
    Create a new multi-turn session.

    Returns a `session_id` to use in subsequent `/session/{id}/message` calls.
    Session expires after 30 minutes of inactivity (Redis TTL resets on each message).
    """
    session = await create_session(
        user_id=current_user.id,
        db=db,
        redis=redis,
    )
    return SessionStartResponse.model_validate(session)


# ── POST /session/{id}/message ────────────────────────────────────────────────

@router.post(
    "/{session_id}/message",
    response_model=MessageResponse,
    summary="Send an utterance and update the session order",
    responses={
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Session not found or expired"},
        429: {"description": "Rate limit exceeded (60 req/min per user)"},
    },
)
@limiter.limit("60/minute")
async def session_message(
    request: Request,
    session_id: uuid.UUID,
    body: MessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> MessageResponse:
    """
    Process a new utterance within an existing session.

    **Rate limit:** 60 requests / minute per authenticated user.

    Supports multi-turn context:
    - **Turn 1:** `"I want 2 large pepperoni with extra cheese"`
    - **Turn 2:** `"and a coke"` → adds Coke to existing order
    - **Turn 3:** `"make that 3"` → updates pepperoni quantity to 3

    Returns the updated order after every turn.
    """
    try:
        updated_order, turn, context_applied = await process_message(
            session_id=session_id,
            user_id=current_user.id,
            text=body.text,
            db=db,
            redis=redis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return MessageResponse(
        updated_order=updated_order,
        turn=turn,
        context_applied=context_applied,
    )


# ── GET /session/{id}/order ───────────────────────────────────────────────────

@router.get(
    "/{session_id}/order",
    response_model=SessionOrderResponse,
    summary="Get the current compiled order for a session",
    responses={
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Session not found or expired"},
    },
)
async def get_order(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> SessionOrderResponse:
    """
    Return the current order state for an active session without modifying it.
    """
    try:
        order_data = await get_session_order(
            session_id=session_id,
            user_id=current_user.id,
            redis=redis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return SessionOrderResponse(
        session_id=session_id,
        turn=order_data["turn"],
        status=order_data["status"],
        current_order=order_data["current_order"],
        last_food_entity=order_data.get("last_food_entity"),
    )


# ── DELETE /session/{id} ──────────────────────────────────────────────────────

@router.delete(
    "/{session_id}",
    status_code=204,
    summary="Close a session and persist the final order",
    responses={
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Session not found or expired"},
    },
)
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> None:
    """
    Close the session:
    - Persists the final compiled order to PostgreSQL as `confirmed`.
    - Marks the session row as `closed`.
    - Removes the session context from Redis.

    Returns 204 No Content on success.
    """
    try:
        await close_session(
            session_id=session_id,
            user_id=current_user.id,
            db=db,
            redis=redis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
