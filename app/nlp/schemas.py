"""
Pydantic v2 schemas for the NLP pipeline.
These model the intermediate and final outputs of the 6-step extraction pipeline.
"""
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Raw entity from spaCy ─────────────────────────────────────────────────────

class RawEntity(BaseModel):
    """A single entity span extracted by the spaCy pipeline."""
    text: str
    label: str   # FOOD | SIZE | MODIFIER | CARDINAL
    start: int   # character offset in processed text
    end: int


# ── Assembled order item ──────────────────────────────────────────────────────

class OrderItem(BaseModel):
    """
    A single line-item assembled from raw entities.
    Maps to one row in the `items` JSONB array of the orders table.
    """
    name: str                              # matched menu item name
    quantity: int = Field(default=1, ge=1)
    size: Optional[str] = None            # "small" | "medium" | "large" | "xl"
    modifiers: List[str] = Field(default_factory=list)  # ["extra cheese", ...]
    unit_price: Optional[float] = None    # from menu_items.price
    matched_menu_item_id: Optional[str] = None          # UUID string


# ── Full pipeline output ──────────────────────────────────────────────────────

class ParsedOrder(BaseModel):
    """
    Complete structured output of POST /order/parse.
    Matches the Technical Spec response schema exactly.
    """
    items: List[OrderItem]
    confidence: float = Field(ge=0.0, le=1.0)
    for_review: bool = False             # True when confidence < threshold
    raw_entities: List[RawEntity] = Field(default_factory=list)
    processing_time_ms: float


# ── Pipeline context (used internally) ───────────────────────────────────────

class PipelineContext(BaseModel):
    """
    Intermediate context passed between pipeline steps.
    Not exposed via the API.
    """
    original_text: str
    processed_text: str
    entities: List[RawEntity] = Field(default_factory=list)
    items: List[OrderItem] = Field(default_factory=list)
    fuzzy_scores: List[float] = Field(default_factory=list)
