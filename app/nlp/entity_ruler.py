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

from app.nlp.indian_menu_items import INDIAN_MENU_ITEMS as DEFAULT_MENU_ITEMS

logger = logging.getLogger(__name__)

# ── Hard-coded size / modifier vocab ─────────────────────────────────────────
_SIZE_TOKENS = ["small", "medium", "large", "xl", "extra-large", "regular", "mini", "king", "jumbo", "half", "full"]
_MODIFIER_TOKENS = [
    "extra",
    "no",
    "without",
    "light",
    "well-done",
    "well",
    "done",
    "less",
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

# The 50-item synthetic menu was removed. DEFAULT_MENU_ITEMS now points to INDIAN_MENU_ITEMS.

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

    # ── Quantity patterns ────────────────────────────────────────────────────
    patterns.append({"label": "CARDINAL", "pattern": [{"LIKE_NUM": True}]})

    # ── FOOD patterns from menu ──────────────────────────────────────────────
    for item in items:
        name: str = item["name"].lower()
        # Exact phrase match
        patterns.append({"label": "FOOD", "pattern": name})
        patterns.append({"label": "FOOD", "pattern": name + "s"})

        # Token-level match for multi-word items (catches reordering)
        tokens = name.split()
        if len(tokens) > 1:
            patterns.append(
                {
                    "label": "FOOD",
                    "pattern": [{"LOWER": tok} for tok in tokens],
                }
            )
            # Add plural version of the last token for token-level match
            plural_tokens = tokens[:-1] + [tokens[-1] + "s"]
            patterns.append(
                {
                    "label": "FOOD",
                    "pattern": [{"LOWER": tok} for tok in plural_tokens],
                }
            )

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
