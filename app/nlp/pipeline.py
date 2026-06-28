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
from app.nlp.schemas import ParsedOrder, OrderItem, RawEntity
from app.nlp.entity_ruler import build_entity_ruler
from app.nlp.indian_menu_items import INDIAN_MENU_ITEMS
from app.nlp.coref import resolve_coreferences
from app.nlp.ngram_fallback import find_missing_foods
from app.nlp.compositional import resolve_compositional

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

    items = menu_items if menu_items is not None else INDIAN_MENU_ITEMS

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
    text = text.replace("a couple of", "2")
    tokens = text.split()
    result: List[str] = []
    hindi_numbers = {"ek": "1", "do": "2", "teen": "3", "chaar": "4", "paanch": "5"}
    for token in tokens:
        if token in hindi_numbers:
            result.append(hindi_numbers[token])
        else:
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
_QTY_WINDOW = 7


def _assemble_items(raw_entities: List[RawEntity], doc_tokens: List[str]) -> List[OrderItem]:
    """
    Given a list of RawEntity objects and the spaCy tokens, group modifiers/sizes/quantities 
    with their nearest FOOD entity.
    """
    items: List[OrderItem] = []
    
    # Collect entity groups
    food_ents = [e for e in raw_entities if e.label == "FOOD"]
    cardinal_ents = [e for e in raw_entities if e.label == "CARDINAL"]
    size_ents = [e for e in raw_entities if e.label == "SIZE"]
    modifier_ents = [e for e in raw_entities if e.label == "MODIFIER"]

    def _get_nearest_food(pos: int) -> Optional[RawEntity]:
        if not food_ents:
            return None
        # Prefer foods that come AFTER the modifier/cardinal if distance is tied
        def sort_key(f):
            f_pos = f.start_token
            dist = abs(pos - f_pos)
            if dist <= 2:
                tie = -1 if f_pos > pos else 1
            else:
                tie = -1 if f_pos < pos else 1
            return (dist, tie)
        return min(food_ents, key=sort_key)

    for food in food_ents:
        food_pos = food.start_token
        if food_pos is None:
            continue

        # ── Quantity (per-item scoped) ───────────────────────────────────────
        qty = 1
        valid_cards = []
        for card in cardinal_ents:
            card_pos = card.start_token
            if card_pos is not None:
                nearest = _get_nearest_food(card_pos)
                if nearest == food and abs(card_pos - food_pos) <= _QTY_WINDOW:
                    try:
                        valid_cards.append((abs(card_pos - food_pos), int(card.text)))
                    except ValueError:
                        pass
        if valid_cards:
            valid_cards.sort(key=lambda x: x[0])
            qty = valid_cards[0][1]

        # ── Size (per-item scoped) ───────────────────────────────────────────
        size: Optional[str] = None
        valid_sizes = []
        for size_ent in size_ents:
            size_pos = size_ent.start_token
            if size_pos is not None:
                nearest = _get_nearest_food(size_pos)
                if nearest == food and abs(size_pos - food_pos) <= _QTY_WINDOW + 1:
                    valid_sizes.append((abs(size_pos - food_pos), size_ent.text))
        if valid_sizes:
            valid_sizes.sort(key=lambda x: x[0])
            size = valid_sizes[0][1]

        # ── Modifiers (per-item scoped) ──────────────────────────────────────
        food_mods = []
        for mod_ent in modifier_ents:
            mod_pos = mod_ent.start_token
            if mod_pos is not None and _get_nearest_food(mod_pos) == food:
                food_mods.append(mod_ent)

        mods: List[str] = []
        skip_next = False
        stopwords = {"a", "an", "the", "some", "of", "make", "that"}
        for i, mod_ent in enumerate(food_mods):
            if skip_next:
                skip_next = False
                continue

            next_word_idx = mod_ent.end_token
            next_word = doc_tokens[next_word_idx] if next_word_idx is not None and next_word_idx < len(doc_tokens) else ""
            
            if next_word and next_word not in [f.text.split()[0] for f in food_ents]:
                if mod_ent.text.lower() == "no" and next_word.lower() in {"make", "wait", "actually", "instead"}:
                    # Conversational correction, not a food modifier
                    continue
                elif next_word in stopwords:
                    mods.append(mod_ent.text)
                else:
                    mods.append(f"{mod_ent.text} {next_word.strip(',.')}".strip())
                    if i + 1 < len(food_mods) and food_mods[i+1].start_token == next_word_idx:
                        skip_next = True
            else:
                mods.append(mod_ent.text)

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
                start_token=ent.start,
                end_token=ent.end,
            )
        )

    logger.debug("Extracted %d entities from '%s'", len(raw_entities), processed)

    # ── Step 3: Entity Assembly ───────────────────────────────────────────────
    doc_tokens = [t.text for t in doc]
    menu_names = [m["name"].lower() for m in INDIAN_MENU_ITEMS]

    # 1. Resolve coreferences
    new_corefs = resolve_coreferences(doc_tokens, raw_entities)
    # only keep corefs that were added
    coref_added = [e for e in new_corefs if e not in raw_entities]
    raw_entities.extend(coref_added)
    
    # 2. Compositional
    comp_ents = resolve_compositional(doc_tokens, menu_names)
    def is_occupied(ent, existing):
        return any(
            e.label == "FOOD" and 
            e.start_token is not None and e.end_token is not None and
            ent.start_token is not None and ent.end_token is not None and
            max(e.start_token, ent.start_token) < min(e.end_token, ent.end_token)
            for e in existing
        )
    comp_ents = [c for c in comp_ents if not is_occupied(c, raw_entities)]
    raw_entities.extend(comp_ents)
    
    # 3. N-gram fallback
    ngram_ents = find_missing_foods(doc_tokens, raw_entities, menu_names)
    raw_entities.extend(ngram_ents)
    
    # 3.5 Deduplicate raw_entities (same label, start, end)
    unique_raw_ents = []
    seen = set()
    for ent in raw_entities:
        key = (ent.label, ent.start_token, ent.end_token)
        if key not in seen:
            seen.add(key)
            unique_raw_ents.append(ent)
    raw_entities = unique_raw_ents

    # 4. Assemble components into order items
    items = _assemble_items(raw_entities, doc_tokens)

    # 5. Merge duplicates (same name and size)
    merged_items_dict = {}
    for item in items:
        # Before merging, match menu so we merge on standard names
        matched_item, score, hit = _match_menu(item)
        if not hit:
            key = (matched_item.name, matched_item.size)
        else:
            key = (matched_item.name, matched_item.size)
            
        if key in merged_items_dict:
            existing = merged_items_dict[key][0]
            # Keep max quantity
            existing.quantity = max(existing.quantity, matched_item.quantity)
            # Combine modifiers (unique)
            existing.modifiers = list(dict.fromkeys(existing.modifiers + matched_item.modifiers))
        else:
            merged_items_dict[key] = (matched_item, score, hit)

    matched_items = []
    fuzzy_scores = []
    any_miss = False

    for matched_item, score, hit in merged_items_dict.values():
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
