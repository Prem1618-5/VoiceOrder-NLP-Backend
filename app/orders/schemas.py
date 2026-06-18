"""
Pydantic v2 schemas for the orders module.

Covers:
  - OrderParseRequest   — POST /order/parse request body
  - OrderParseResponse  — POST /order/parse response
  - OrderHistoryItem    — single item in GET /orders/history
  - OrderHistoryResponse — paginated history wrapper
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Request ───────────────────────────────────────────────────────────────────

class OrderParseRequest(BaseModel):
    """
    Data Security spec constraints:
      text: min_length=2, max_length=500, strip_whitespace=True
    """
    text: str = Field(
        ...,
        min_length=2,
        max_length=500,
        strip_whitespace=True,
        examples=["I want 2 large pepperoni pizzas with extra cheese"],
    )
    menu_id: str = Field(default="default", examples=["default"])

    @field_validator("text")
    @classmethod
    def sanitize_control_chars(cls, v: str) -> str:
        """Strip ASCII control characters — NLP injection defense (Data Security spec)."""
        import re
        return re.sub(r"[\x00-\x1F\x7F]", "", v)[:500]


# ── Nested response types ─────────────────────────────────────────────────────

class RawEntityOut(BaseModel):
    text: str
    label: str
    start: int
    end: int


class OrderItemOut(BaseModel):
    name: str
    quantity: int = Field(ge=1)
    size: Optional[str] = None
    modifiers: List[str] = Field(default_factory=list)
    unit_price: Optional[float] = None
    matched_menu_item_id: Optional[str] = None


# ── Response ──────────────────────────────────────────────────────────────────

class OrderParseResponse(BaseModel):
    """
    Matches Technical Spec POST /order/parse 200 response schema exactly.
    """
    items: List[OrderItemOut]
    confidence: float = Field(ge=0.0, le=1.0)
    for_review: bool
    raw_entities: List[RawEntityOut] = Field(default_factory=list)
    processing_time_ms: float


# ── History ───────────────────────────────────────────────────────────────────

class OrderHistoryItem(BaseModel):
    """Single order entry in paginated history response."""
    id: uuid.UUID
    session_id: Optional[uuid.UUID]
    items: List[Dict[str, Any]]
    total_price: Optional[float]
    status: str
    confidence: Optional[float]
    for_review: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderHistoryResponse(BaseModel):
    orders: List[OrderHistoryItem]
    total: int
    page: int
    size: int
