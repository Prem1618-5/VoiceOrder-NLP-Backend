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
_SIZE_TOKENS = ["small", "medium", "large", "xl", "extra-large", "regular", "mini"]
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
]

# ── 50-item synthetic menu (from PRD OQ2 recommendation) ─────────────────────
DEFAULT_MENU_ITEMS: List[Dict[str, Any]] = [
    # Pizzas
    {"name": "pepperoni pizza", "price": 12.99, "category": "pizza"},
    {"name": "margherita pizza", "price": 11.99, "category": "pizza"},
    {"name": "bbq chicken pizza", "price": 13.99, "category": "pizza"},
    {"name": "veggie pizza", "price": 11.49, "category": "pizza"},
    {"name": "hawaiian pizza", "price": 12.49, "category": "pizza"},
    {"name": "meat lovers pizza", "price": 14.99, "category": "pizza"},
    {"name": "mushroom pizza", "price": 11.49, "category": "pizza"},
    # Burgers
    {"name": "classic cheeseburger", "price": 8.99, "category": "burger"},
    {"name": "bacon burger", "price": 9.99, "category": "burger"},
    {"name": "veggie burger", "price": 8.49, "category": "burger"},
    {"name": "double smash burger", "price": 11.99, "category": "burger"},
    # Sides
    {"name": "french fries", "price": 3.49, "category": "side"},
    {"name": "onion rings", "price": 3.99, "category": "side"},
    {"name": "mozzarella sticks", "price": 5.49, "category": "side"},
    {"name": "coleslaw", "price": 2.49, "category": "side"},
    {"name": "garlic bread", "price": 2.99, "category": "side"},
    # Drinks
    {"name": "coke", "price": 2.49, "category": "drink"},
    {"name": "diet coke", "price": 2.49, "category": "drink"},
    {"name": "sprite", "price": 2.49, "category": "drink"},
    {"name": "orange juice", "price": 2.99, "category": "drink"},
    {"name": "lemonade", "price": 2.99, "category": "drink"},
    {"name": "water", "price": 1.00, "category": "drink"},
    {"name": "iced tea", "price": 2.49, "category": "drink"},
    # Pasta
    {"name": "spaghetti bolognese", "price": 10.99, "category": "pasta"},
    {"name": "fettuccine alfredo", "price": 10.49, "category": "pasta"},
    {"name": "penne arrabbiata", "price": 9.99, "category": "pasta"},
    # Salads
    {"name": "caesar salad", "price": 7.99, "category": "salad"},
    {"name": "greek salad", "price": 7.49, "category": "salad"},
    {"name": "garden salad", "price": 6.49, "category": "salad"},
    # Sandwiches
    {"name": "chicken club sandwich", "price": 8.99, "category": "sandwich"},
    {"name": "blt sandwich", "price": 7.49, "category": "sandwich"},
    {"name": "tuna melt", "price": 7.99, "category": "sandwich"},
    # Wings
    {"name": "buffalo wings", "price": 10.99, "category": "wings"},
    {"name": "honey garlic wings", "price": 10.99, "category": "wings"},
    {"name": "bbq wings", "price": 10.99, "category": "wings"},
    # Desserts
    {"name": "chocolate cake", "price": 5.99, "category": "dessert"},
    {"name": "cheesecake", "price": 5.49, "category": "dessert"},
    {"name": "ice cream", "price": 4.49, "category": "dessert"},
    {"name": "brownie", "price": 3.99, "category": "dessert"},
    # Breakfast
    {"name": "pancakes", "price": 7.99, "category": "breakfast"},
    {"name": "eggs benedict", "price": 8.99, "category": "breakfast"},
    {"name": "french toast", "price": 7.49, "category": "breakfast"},
    # Wraps
    {"name": "chicken caesar wrap", "price": 8.49, "category": "wrap"},
    {"name": "veggie wrap", "price": 7.49, "category": "wrap"},
    {"name": "beef wrap", "price": 8.99, "category": "wrap"},
    # Soups
    {"name": "tomato soup", "price": 5.49, "category": "soup"},
    {"name": "chicken noodle soup", "price": 5.99, "category": "soup"},
    # Shakes
    {"name": "chocolate milkshake", "price": 5.49, "category": "shake"},
    {"name": "vanilla milkshake", "price": 5.49, "category": "shake"},
    {"name": "strawberry milkshake", "price": 5.49, "category": "shake"},
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

        # Single-word core (e.g. "pepperoni" → FOOD)
        if len(tokens) >= 2:
            # Add the most distinctive word (usually first or last) as alias
            patterns.append({"label": "FOOD", "pattern": tokens[0]})

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
        "EntityRuler built: %d food patterns, %d size tokens, %d modifier tokens",
        len(items),
        len(_SIZE_TOKENS),
        len(_MODIFIER_TOKENS),
    )
    return ruler
