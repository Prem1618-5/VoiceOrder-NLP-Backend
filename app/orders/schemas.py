"""
Pydantic v2 schemas for the orders module.

OrderParseRequest   → POST /order/parse body
OrderParseResponse  → POST /order/parse response (includes NLP artefacts)
OrderSummary        → single item in GET /orders/history list
PaginatedOrders     → full paginated response for GET /orders/history
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.nlp.schemas import OrderItem, RawEntity


# ── Request ───────────────────────────────────────────────────────────────────


class OrderParseRequest(BaseModel):
    """
    Request body for POST /order/parse.
    Constraints (Data Security spec):
      text: min_length=2, max_length=500, strip_whitespace=True
    """

    text: str = Field(
        min_length=2,
        max_length=500,
        strip_whitespace=True,
        description=(
            "Free-text restaurant order "
            "(e.g. 'I want 2 large pepperoni pizzas with extra cheese')"
        ),
    )
    menu_id: str = Field(
        default="default",
        description="Menu identifier — V1 supports single restaurant per deploy",
    )


# ── Response ──────────────────────────────────────────────────────────────────


class OrderParseResponse(BaseModel):
    """
    Response from POST /order/parse.
    Matches the Technical Spec response schema exactly.
    """

    id: uuid.UUID
    items: List[OrderItem]
    confidence: float = Field(ge=0.0, le=1.0)
    for_review: bool
    raw_entities: List[RawEntity]
    processing_time_ms: float


# ── History ───────────────────────────────────────────────────────────────────


class OrderSummary(BaseModel):
    """Single order row in paginated history. ORM-compatible via from_attributes."""

    id: uuid.UUID
    session_id: Optional[uuid.UUID] = None
    items: List[Dict[str, Any]]
    total_price: Optional[float] = None
    status: str
    confidence: Optional[float] = None
    for_review: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedOrders(BaseModel):
    """Paginated response for GET /orders/history."""

    items: List[OrderSummary]
    page: int = Field(ge=1)
    size: int = Field(ge=1, le=100)
    total: int
