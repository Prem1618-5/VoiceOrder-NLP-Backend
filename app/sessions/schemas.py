"""
Pydantic v2 schemas for the sessions module.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
import re


# ── Session create ────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    """Response after POST /session/start."""
    session_id: uuid.UUID
    status: str
    expires_at: datetime


# ── Message request ───────────────────────────────────────────────────────────

class MessageRequest(BaseModel):
    """
    Request body for POST /session/{id}/message.
    Data Security spec: min_length=1, max_length=500.
    """
    text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        strip_whitespace=True,
        examples=["actually make that 3"],
    )

    @field_validator("text")
    @classmethod
    def sanitize_control_chars(cls, v: str) -> str:
        return re.sub(r"[\x00-\x1F\x7F]", "", v)[:500]


# ── Order item (reused from NLP output) ──────────────────────────────────────

class SessionOrderItem(BaseModel):
    name: str
    quantity: int = Field(ge=1)
    size: Optional[str] = None
    modifiers: List[str] = Field(default_factory=list)
    unit_price: Optional[float] = None
    matched_menu_item_id: Optional[str] = None


class SessionCurrentOrder(BaseModel):
    items: List[SessionOrderItem] = Field(default_factory=list)
    total_price: Optional[float] = None


# ── Message response ──────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    """Response for POST /session/{id}/message — matches Technical Spec."""
    updated_order: SessionCurrentOrder
    turn: int
    context_applied: bool


# ── Session order response ────────────────────────────────────────────────────

class SessionOrderResponse(BaseModel):
    """Response for GET /session/{id}/order."""
    session_id: uuid.UUID
    turn: int
    current_order: SessionCurrentOrder
    status: str
