"""
Pydantic v2 schemas for the sessions module.

SessionStartResponse  → POST /session/start
MessageRequest        → POST /session/{id}/message request body
MessageResponse       → POST /session/{id}/message response
SessionOrderResponse  → GET  /session/{id}/order
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Dict, Optional

from pydantic import BaseModel, Field, StringConstraints


# ── POST /session/start ───────────────────────────────────────────────────────


class SessionStartResponse(BaseModel):
    """Returned when a new session is created."""

    session_id: uuid.UUID
    status: str = "active"
    created_at: datetime
    expires_at: datetime
    message: str = "Session started. Send order utterances to /session/{id}/message."

    model_config = {"from_attributes": True}


# ── POST /session/{id}/message ────────────────────────────────────────────────


class MessageRequest(BaseModel):
    """
    Request body for POST /session/{id}/message.
    Constraints per Data Security spec: min_length=1, max_length=500.
    """

    text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ] = Field(
        description=(
            "Next utterance in the conversation "
            "(e.g. 'make that 3', 'and add a coke', 'extra cheese')"
        ),
    )


class MessageResponse(BaseModel):
    """
    Returned after processing each utterance.
    `context_applied` is True when the new utterance modified the existing order
    (i.e. was understood as an update rather than new input).
    """

    updated_order: Dict[str, Any]  # current_order dict from Redis
    turn: int
    context_applied: bool  # True when "make that 3" style update occurred


# ── GET /session/{id}/order ───────────────────────────────────────────────────


class SessionOrderResponse(BaseModel):
    """Current compiled order for an active session."""

    session_id: uuid.UUID
    turn: int
    status: str
    current_order: Dict[str, Any]  # {"items": [...], "total_price": X}
    last_food_entity: Optional[str] = None  # most recent FOOD entity (for context)
