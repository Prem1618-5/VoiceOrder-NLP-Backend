"""
spaCy EntityRuler builder.

Loads menu vocabulary patterns from the database at application startup
(called once from pipeline.py::load_model()).

Entity labels used:
  FOOD      — matched menu item names (e.g. "pepperoni pizza")
  SIZE      — size modifiers (small / medium / large / xl)
  MODIFIER  — quantity-style modifiers (extra / no / without / add / light)
  CARDINAL  — handled natively by spaCy NER for quantity integers

The EntityRuler is inserted BEFORE the NER component so that custom
patterns take priority over spaCy's default entity classification.
"""

import logging
from typing import Any, Dict, List, Optional

from spacy.language import Language
from spacy.pipeline import EntityRuler

logger = logging.getLogger(__name__)

# ── Hard-coded size / modifier vocab ─────────────────────────────────────────
_SIZE_TOKENS = ["small", "medium", "large", "xl", "extra-large", "regular", "mini", "king", "jumbo"]
_MODIFIER_TOKENS = [
    "extra",
    "no",
    "without",
    "add",
    "light",
    "well-done",
    "half",
    "double",
    "triple",
    "side",
    "easy",
    "crispy",
    "grilled",
    "fried",
    "spicy",
    "mild",
]

# ── 50-item synthetic menu (from PRD OQ2 recommendation) ─────────────────────
DEFAULT_MENU_ITEMS: List[Dict[str, Any]] = [
    # Pizzas
    {"id": "pizza-001", "name": "pepperoni pizza", "price": 12.99, "category": "pizza"},
    {"id": "pizza-002", "name": "margherita pizza", "price": 11.99, "category": "pizza"},
    {"id": "pizza-003", "name": "bbq chicken pizza", "price": 13.99, "category": "pizza"},
    {"id": "pizza-004", "name": "veggie pizza", "price": 11.49, "category": "pizza"},
    {"id": "pizza-005", "name": "hawaiian pizza", "price": 12.49, "category": "pizza"},
    {"id": "pizza-006", "name": "meat lovers pizza", "price": 14.99, "category": "pizza"},
    {"id": "pizza-007", "name": "mushroom pizza", "price": 11.49, "category": "pizza"},
    # Burgers
    {"id": "burger-001", "name": "classic cheeseburger", "price": 8.99, "category": "burger"},
    {"id": "burger-002", "name": "bacon burger", "price": 9.99, "category": "burger"},
    {"id": "burger-003", "name": "veggie burger", "price": 8.49, "category": "burger"},
    {"id": "burger-004", "name": "double smash burger", "price": 11.99, "category": "burger"},
    # Sides
    {"id": "side-001", "name": "french fries", "price": 3.49, "category": "side"},
    {"id": "side-002", "name": "onion rings", "price": 3.99, "category": "side"},
    {"id": "side-003", "name": "mozzarella sticks", "price": 5.49, "category": "side"},
    {"id": "side-004", "name": "coleslaw", "price": 2.49, "category": "side"},
    {"id": "side-005", "name": "garlic bread", "price": 2.99, "category": "side"},
    {"id": "side-006", "name": "breadsticks", "price": 2.49, "category": "side"},
    {"id": "side-007", "name": "loaded fries", "price": 4.99, "category": "side"},
    {"id": "side-008", "name": "sweet potato fries", "price": 3.99, "category": "side"},
    # Drinks
    {"id": "drink-001", "name": "coke", "price": 2.49, "category": "drink"},
    {"id": "drink-002", "name": "diet coke", "price": 2.49, "category": "drink"},
    {"id": "drink-003", "name": "coke zero", "price": 2.49, "category": "drink"},
    {"id": "drink-004", "name": "sprite", "price": 2.49, "category": "drink"},
    {"id": "drink-005", "name": "orange juice", "price": 2.99, "category": "drink"},
    {"id": "drink-006", "name": "lemonade", "price": 2.99, "category": "drink"},
    {"id": "drink-007", "name": "water", "price": 1.00, "category": "drink"},
    {"id": "drink-008", "name": "iced tea", "price": 2.49, "category": "drink"},
    {"id": "drink-009", "name": "coffee", "price": 3.49, "category": "drink"},
    {"id": "drink-010", "name": "milkshake", "price": 4.99, "category": "drink"},
    {"id": "drink-011", "name": "pepsi", "price": 2.49, "category": "drink"},
    {"id": "drink-012", "name": "root beer", "price": 2.49, "category": "drink"},
    {"id": "drink-013", "name": "mountain dew", "price": 2.49, "category": "drink"},
    # Pasta
    {"id": "pasta-001", "name": "spaghetti bolognese", "price": 10.99, "category": "pasta"},
    {"id": "pasta-002", "name": "fettuccine alfredo", "price": 10.49, "category": "pasta"},
    {"id": "pasta-003", "name": "penne arrabbiata", "price": 9.99, "category": "pasta"},
    # Salads
    {"id": "salad-001", "name": "caesar salad", "price": 7.99, "category": "salad"},
    {"id": "salad-002", "name": "greek salad", "price": 7.49, "category": "salad"},
    {"id": "salad-003", "name": "garden salad", "price": 6.49, "category": "salad"},
    # Sandwiches
    {"id": "sandwich-001", "name": "chicken club sandwich", "price": 8.99, "category": "sandwich"},
    {"id": "sandwich-002", "name": "blt sandwich", "price": 7.49, "category": "sandwich"},
    {"id": "sandwich-003", "name": "tuna melt", "price": 7.99, "category": "sandwich"},
    # Wings
    {"id": "wings-001", "name": "buffalo wings", "price": 10.99, "category": "wings"},
    {"id": "wings-002", "name": "honey garlic wings", "price": 10.99, "category": "wings"},
    {"id": "wings-003", "name": "bbq wings", "price": 10.99, "category": "wings"},
    # Desserts
    {"id": "dessert-001", "name": "chocolate cake", "price": 5.99, "category": "dessert"},
    {"id": "dessert-002", "name": "cheesecake", "price": 5.49, "category": "dessert"},
    {"id": "dessert-003", "name": "ice cream", "price": 4.49, "category": "dessert"},
    {"id": "dessert-004", "name": "brownie", "price": 3.99, "category": "dessert"},
    # Breakfast
    {"id": "breakfast-001", "name": "pancakes", "price": 7.99, "category": "breakfast"},
    {"id": "breakfast-002", "name": "eggs benedict", "price": 8.99, "category": "breakfast"},
    {"id": "breakfast-003", "name": "french toast", "price": 7.49, "category": "breakfast"},
    # Wraps
    {"id": "wrap-001", "name": "chicken caesar wrap", "price": 8.49, "category": "wrap"},
    {"id": "wrap-002", "name": "veggie wrap", "price": 7.49, "category": "wrap"},
    {"id": "wrap-003", "name": "beef wrap", "price": 8.99, "category": "wrap"},
    # Soups
    {"id": "soup-001", "name": "tomato soup", "price": 5.49, "category": "soup"},
    {"id": "soup-002", "name": "chicken noodle soup", "price": 5.99, "category": "soup"},
    # Shakes
    {"id": "shake-001", "name": "chocolate milkshake", "price": 5.49, "category": "shake"},
    {"id": "shake-002", "name": "vanilla milkshake", "price": 5.49, "category": "shake"},
    {"id": "shake-003", "name": "strawberry milkshake", "price": 5.49, "category": "shake"},
]

# ── Drink aliases — common ways customers name drinks ─────────────────────────
# These map colloquial phrases to canonical menu items.
_DRINK_ALIASES: List[Dict[str, Any]] = [
    # Coke family
    {"alias": "coca cola", "canonical": "coke"},
    {"alias": "cola", "canonical": "coke"},
    {"alias": "diet cola", "canonical": "diet coke"},
    {"alias": "diet pepsi", "canonical": "diet coke"},  # closest match
    # Generic
    {"alias": "soda", "canonical": "coke"},
    {"alias": "pop", "canonical": "coke"},
    {"alias": "soft drink", "canonical": "coke"},
    # Water
    {"alias": "bottled water", "canonical": "water"},
    {"alias": "still water", "canonical": "water"},
    {"alias": "sparkling water", "canonical": "water"},
    # Tea
    {"alias": "sweet tea", "canonical": "iced tea"},
    {"alias": "ice tea", "canonical": "iced tea"},
    # Juice
    {"alias": "oj", "canonical": "orange juice"},
    {"alias": "juice", "canonical": "orange juice"},
]


def build_entity_ruler(
    nlp: Language,
    menu_items: Optional[List[Dict[str, Any]]] = None,
) -> EntityRuler:
    """
    Build a spaCy EntityRuler from menu items and hard-coded vocab.

    Args:
        nlp:        The loaded spaCy Language object.
        menu_items: List of dicts with at least a 'name' key.
                    If None, DEFAULT_MENU_ITEMS is used.

    Returns:
        Configured EntityRuler ready to be added to the pipeline.
    """
    items = menu_items if menu_items is not None else DEFAULT_MENU_ITEMS

    ruler: EntityRuler = nlp.add_pipe(
        "entity_ruler",
        before="ner",
        config={"overwrite_ents": True},
    )

    patterns: List[Dict[str, Any]] = []

    # ── FOOD patterns from menu ──────────────────────────────────────────────
    for item in items:
        name: str = item["name"].lower()
        # Exact phrase match
        patterns.append({"label": "FOOD", "pattern": name})

        # Token-level match for multi-word items (catches reordering)
        tokens = name.split()
        if len(tokens) > 1:
            patterns.append(
                {
                    "label": "FOOD",
                    "pattern": [{"LOWER": tok} for tok in tokens],
                }
            )

        # Single-word core (e.g. "pepperoni" → FOOD, "garlic" → FOOD)
        if len(tokens) >= 2:
            # Add first word as alias (most distinctive usually)
            patterns.append({"label": "FOOD", "pattern": tokens[0]})
            # Also add last word for items like "garlic bread" → "bread" alias
            if tokens[-1] not in {"pizza", "burger", "sandwich", "salad", "soup",
                                   "wrap", "cake", "shake", "milkshake"}:
                patterns.append({"label": "FOOD", "pattern": tokens[-1]})

    # ── Drink alias patterns ─────────────────────────────────────────────────
    for alias_entry in _DRINK_ALIASES:
        alias = alias_entry["alias"].lower()
        alias_tokens = alias.split()
        if len(alias_tokens) == 1:
            patterns.append({"label": "FOOD", "pattern": alias})
        else:
            patterns.append(
                {
                    "label": "FOOD",
                    "pattern": [{"LOWER": tok} for tok in alias_tokens],
                }
            )

    # ── SIZE patterns ────────────────────────────────────────────────────────
    patterns.append(
        {
            "label": "SIZE",
            "pattern": [{"LOWER": {"IN": _SIZE_TOKENS}}],
        }
    )

    # ── MODIFIER patterns ─────────────────────────────────────────────────────
    patterns.append(
        {
            "label": "MODIFIER",
            "pattern": [{"LOWER": {"IN": _MODIFIER_TOKENS}}],
        }
    )

    ruler.add_patterns(patterns)
    logger.info(
        "EntityRuler built: %d food patterns + %d drink aliases, "
        "%d size tokens, %d modifier tokens",
        len(items),
        len(_DRINK_ALIASES),
        len(_SIZE_TOKENS),
        len(_MODIFIER_TOKENS),
    )
    return ruler
