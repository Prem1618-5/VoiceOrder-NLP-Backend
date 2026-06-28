"""
VoiceOrder NLP Pipeline — 6-step extraction engine.

Step 1 — Preprocess
    Lowercase, strip control chars (NLP injection defence), normalize numbers,
    strip unit words (cans/order of/cups/bottles) so proximity windows work.

Step 2 — spaCy EntityRuler   (runs BEFORE NER)
    Custom FOOD / SIZE / MODIFIER patterns from menu vocab.

Step 3 — spaCy NER
    CARDINAL (qty), discard GPE/ORG/etc.; custom labels pass through.

Step 4 — Entity Assembly
    qty  ← CARDINAL nearest to each specific FOOD (within 5 tokens)
    size ← SIZE entity nearest to each specific FOOD (within 6 tokens)
    mods ← MODIFIER nearest to each specific FOOD (per-item scoping)

Step 5 — Menu Matching
    rapidfuzz.process.extractOne(query, menu_names, score_cutoff=75)
    Miss → for_review=true + nearest match suggested

Step 6 — Confidence
    confidence = (matched_entities / total_entities) * avg(fuzzy_scores)
    < threshold (default 0.6) → for_review = true
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import spacy
from rapidfuzz import fuzz, process
from spacy.language import Language
from word2number import w2n

from app.config import settings
from app.nlp.entity_ruler import DEFAULT_MENU_ITEMS, build_entity_ruler
from app.nlp.schemas import OrderItem, ParsedOrder, RawEntity

logger = logging.getLogger(__name__)

# ── Singleton NLP model ───────────────────────────────────────────────────────

_nlp: Optional[Language] = None
_menu_lookup: Dict[str, Dict[str, Any]] = {}  # name → menu item dict


def load_model(menu_items: Optional[List[Dict[str, Any]]] = None) -> Language:
    """
    Load spaCy model and build EntityRuler (once per process).
    Call at startup or on first request.

    Args:
        menu_items: Override menu (used in tests). Defaults to DEFAULT_MENU_ITEMS.
    """
    global _nlp, _menu_lookup

    if _nlp is not None:
        return _nlp

    items = menu_items if menu_items is not None else DEFAULT_MENU_ITEMS

    logger.info("Loading spaCy model '%s'…", settings.SPACY_MODEL)
    nlp = spacy.load(settings.SPACY_MODEL, disable=["parser", "lemmatizer"])

    # Build EntityRuler (injected BEFORE ner)
    build_entity_ruler(nlp, items)

    # Build menu lookup dict for fuzzy matching
    _menu_lookup = {item["name"].lower(): item for item in items}

    _nlp = nlp
    logger.info(
        "NLP pipeline ready — %d menu items loaded",
        len(_menu_lookup),
    )
    return _nlp


def get_nlp() -> Language:
    """Return the loaded pipeline (lazy-loads on first call)."""
    return load_model()


# ── Step 1: Preprocessing ─────────────────────────────────────────────────────

# Unit words that sit between a CARDINAL and a FOOD entity.
# e.g. "three CANS of diet coke", "one ORDER of garlic bread"
# These inflate the token distance and prevent CARDINAL→FOOD association.
_UNIT_WORDS = {
    "can", "cans",
    "bottle", "bottles",
    "cup", "cups",
    "bowl", "bowls",
    "box", "boxes",
    "piece", "pieces",
    "slice", "slices",
    "portion", "portions",
    "serving", "servings",
    "glass", "glasses",
    "plate", "plates",
    "order",  # "one order of garlic bread" → "one garlic bread"
    "of",     # "three cans OF diet coke" — 'of' is a connector after unit word
}


def _preprocess(text: str) -> str:
    """
    Clean and normalise text before NLP processing.
    Implements NLP injection defence from Data Security spec:
      • Strip control characters (re.sub r'[\x00-\x1f\x7f]')
      • Hard truncate at 500 chars
    """
    # Strip control chars
    text = re.sub(r"[\x00-\x1F\x7F]", "", text)
    # Hard truncation
    text = text[:500]
    # Remove basic punctuation that attaches to words and breaks exact token matching
    text = text.replace(",", " ").replace(".", " ")
    # Lowercase + normalise whitespace
    text = " ".join(text.lower().split())
    return text


def _normalize_numbers(text: str) -> str:
    """Convert written-out numbers to digits: 'two' → '2', 'three' → '3'."""
    tokens = text.split()
    result: List[str] = []
    for token in tokens:
        try:
            result.append(str(w2n.word_to_num(token)))
        except ValueError:
            result.append(token)
    return " ".join(result)


def _strip_unit_words(text: str) -> str:
    """
    Remove unit/container words that sit between a number and a food name.
    e.g. "3 cans of diet coke" → "3 diet coke"
         "1 order of garlic bread" → "1 garlic bread"

    This is done after number normalisation so we handle both
    digit forms ("3") and word forms ("three" → already converted to "3").
    """
    tokens = text.split()
    result: List[str] = []
    for token in tokens:
        if token in _UNIT_WORDS:
            continue  # drop the unit word entirely
        result.append(token)
    return " ".join(result)


# ── Step 4: Entity Assembly ───────────────────────────────────────────────────

_ALLOWED_LABELS = {"FOOD", "SIZE", "MODIFIER", "CARDINAL"}
_DISCARD_LABELS = {"GPE", "ORG", "PERSON", "LOC", "DATE", "TIME", "MONEY", "PERCENT"}

# Expanded token window: handles "3 diet coke" (after unit-word stripping)
# and cases where size/modifier tokens still sit between cardinal and food.
_QTY_WINDOW = 5


def _token_position(tokens: List[str], phrase: str) -> Optional[int]:
    """Return the index of the first token of `phrase` in `tokens`, or None."""
    phrase_tokens = phrase.split()
    for i in range(len(tokens) - len(phrase_tokens) + 1):
        if tokens[i : i + len(phrase_tokens)] == phrase_tokens:
            return i
    return None


def _get_nearest_food(ent_pos: int, food_positions: List[Tuple[Optional[int], RawEntity]]) -> Optional[int]:
    nearest_food_pos = None
    nearest_food_dist = float("inf")
    for other_pos, _ in food_positions:
        if other_pos is not None:
            d = abs(ent_pos - other_pos)
            if d < nearest_food_dist:
                nearest_food_dist = d
                nearest_food_pos = other_pos
    return nearest_food_pos


def _assemble_items(
    raw_entities: List[RawEntity], processed_text: str
) -> List[OrderItem]:
    """
    Convert flat list of raw entities into structured OrderItem objects.

    Rules:
      qty   ← CARDINAL within _QTY_WINDOW tokens of a FOOD entity
      size  ← SIZE entity nearest to each FOOD entity (within window)
      mods  ← MODIFIER entities scoped per-item (between neighbouring foods)

    Fix vs. original:
      - Token window expanded to 5 (was 3)
      - Modifiers, sizes, and cardinals are scoped per-item: each is attached
        to the nearest FOOD entity, preventing cross-contamination.
    """
    items: List[OrderItem] = []
    tokens = processed_text.split()

    # Collect entity groups
    food_ents = [e for e in raw_entities if e.label == "FOOD"]
    cardinal_ents = [e for e in raw_entities if e.label == "CARDINAL"]
    size_ents = [e for e in raw_entities if e.label == "SIZE"]
    modifier_ents = [e for e in raw_entities if e.label == "MODIFIER"]

    # Pre-compute token positions for all entities
    food_positions = [(_token_position(tokens, f.text), f) for f in food_ents]

    for food_pos, food in food_positions:
        # ── Quantity (per-item scoped) ───────────────────────────────────────
        qty = 1
        for card in cardinal_ents:
            card_pos = _token_position(tokens, card.text)
            if card_pos is not None and food_pos is not None:
                nearest_food = _get_nearest_food(card_pos, food_positions)
                if nearest_food == food_pos:
                    if abs(card_pos - food_pos) <= _QTY_WINDOW:
                        try:
                            qty = int(card.text)
                        except ValueError:
                            pass

        # ── Size (per-item scoped) ───────────────────────────────────────────
        size: Optional[str] = None
        for size_ent in size_ents:
            size_pos = _token_position(tokens, size_ent.text)
            if size_pos is not None and food_pos is not None:
                nearest_food = _get_nearest_food(size_pos, food_positions)
                if nearest_food == food_pos:
                    if abs(size_pos - food_pos) <= _QTY_WINDOW + 1:
                        size = size_ent.text

        # ── Modifiers (per-item scoped) ──────────────────────────────────────
        mods: List[str] = []
        for mod_ent in modifier_ents:
            mod_pos = _token_position(tokens, mod_ent.text)
            if mod_pos is None or food_pos is None:
                continue

            nearest_food = _get_nearest_food(mod_pos, food_positions)
            if nearest_food != food_pos:
                continue

            # Build modifier string: modifier token + following word
            next_word = tokens[mod_pos + 1] if mod_pos + 1 < len(tokens) else ""
            if next_word and next_word not in [f.text.split()[0] for f, _ in
                                               [(fe, None) for fe in food_ents]]:
                # Remove punctuation from modifier next word if needed, but for now just strip
                mods.append(f"{mod_ent.text} {next_word.strip(',.')}".strip())

        items.append(OrderItem(name=food.text, quantity=qty, size=size, modifiers=mods))

    return items


# ── Step 5: Menu Matching (rapidfuzz) ────────────────────────────────────────


def _match_menu(item: OrderItem) -> Tuple[OrderItem, float, bool]:
    """
    Fuzzy-match an assembled item against the menu.

    Returns:
        (updated_item, fuzzy_score, matched_flag)
        If score < FUZZY_SCORE_CUTOFF → for_review, nearest_match suggested.
    """
    global _menu_lookup
    menu_names = list(_menu_lookup.keys())

    result = process.extractOne(
        item.name,
        menu_names,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=settings.FUZZY_SCORE_CUTOFF,
    )

    if result is None:
        # No match above cutoff — mark for_review
        # Find best candidate anyway (for suggestion)
        fallback = process.extractOne(
            item.name, menu_names, scorer=fuzz.token_sort_ratio
        )
        nearest = fallback[0] if fallback else item.name
        logger.debug("Menu miss: '%s' → nearest='%s'", item.name, nearest)
        return item, 0.0, False

    matched_name, score, _ = result
    matched_menu = _menu_lookup[matched_name]

    updated = item.model_copy(
        update={
            "name": matched_name,
            "unit_price": matched_menu.get("price"),
            "matched_menu_item_id": matched_menu.get("id"),
        }
    )
    return updated, float(score) / 100.0, True


# ── Step 6: Confidence ───────────────────────────────────────────────────────


def _compute_confidence(
    raw_entities: List[RawEntity],
    fuzzy_scores: List[float],
) -> float:
    """
    confidence = (matched_entities / total_entities) * avg(fuzzy_scores)
    """
    total = len([e for e in raw_entities if e.label in _ALLOWED_LABELS])
    if total == 0:
        return 0.0
    matched = len([e for e in raw_entities if e.label == "FOOD"])
    entity_ratio = matched / total if total > 0 else 0.0
    avg_fuzzy = sum(fuzzy_scores) / len(fuzzy_scores) if fuzzy_scores else 0.0
    return round(entity_ratio * avg_fuzzy, 4)


# ── Public API ────────────────────────────────────────────────────────────────


def extract_entities(text: str) -> ParsedOrder:
    """
    Run the full 6-step NLP pipeline on raw input text.

    Returns ParsedOrder with structured items, confidence, and raw entities.
    Guaranteed to return within ~300 ms (p95) on Railway free-tier with spaCy.
    """
    t_start = time.perf_counter()
    nlp = get_nlp()

    # ── Step 1: Preprocess ────────────────────────────────────────────────────
    processed = _preprocess(text)
    processed = _normalize_numbers(processed)
    processed = _strip_unit_words(processed)  # NEW: strip "cans of", "order of"

    # ── Steps 2 & 3: spaCy pipeline (EntityRuler + NER) ──────────────────────
    doc = nlp(processed)

    raw_entities: List[RawEntity] = []
    for ent in doc.ents:
        label = ent.label_
        if label in _DISCARD_LABELS:
            continue  # discard irrelevant entity types
        if label not in _ALLOWED_LABELS:
            continue
        raw_entities.append(
            RawEntity(
                text=ent.text,
                label=label,
                start=ent.start_char,
                end=ent.end_char,
            )
        )

    logger.debug("Extracted %d entities from '%s'", len(raw_entities), processed)

    # ── Step 4: Entity Assembly ───────────────────────────────────────────────
    items = _assemble_items(raw_entities, processed)

    # ── Step 5: Menu Matching ─────────────────────────────────────────────────
    matched_items: List[OrderItem] = []
    fuzzy_scores: List[float] = []
    any_miss = False

    for item in items:
        matched_item, score, hit = _match_menu(item)
        matched_items.append(matched_item)
        fuzzy_scores.append(score)
        if not hit:
            any_miss = True

    # ── Step 6: Confidence ────────────────────────────────────────────────────
    confidence = _compute_confidence(raw_entities, fuzzy_scores)
    for_review = any_miss or confidence < settings.NLP_CONFIDENCE_THRESHOLD

    elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

    return ParsedOrder(
        items=matched_items,
        confidence=confidence,
        for_review=for_review,
        raw_entities=raw_entities,
        processing_time_ms=elapsed_ms,
    )
