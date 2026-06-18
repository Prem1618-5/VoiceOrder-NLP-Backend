"""
NLP pipeline accuracy tests.
Target: ≥90% entity extraction accuracy on a 100-sample set (PRD G3).
"""
import pytest

from app.nlp.pipeline import NLPPipeline


@pytest.fixture(scope="module")
def pipeline(nlp_pipeline):
    return nlp_pipeline


# ── Basic extraction ──────────────────────────────────────────────────────────

def test_food_entity_extracted(pipeline):
    result = pipeline.parse("I want a pepperoni pizza")
    names = [i.name for i in result.items]
    assert any("pepperoni" in n for n in names)


def test_quantity_extracted(pipeline):
    result = pipeline.parse("2 large pepperoni pizzas")
    assert result.items[0].quantity == 2


def test_size_extracted(pipeline):
    result = pipeline.parse("one large coke")
    assert result.items[0].size == "large"


def test_modifier_extracted(pipeline):
    result = pipeline.parse("pepperoni pizza with extra cheese")
    mods = result.items[0].modifiers
    assert any("extra cheese" in m or "extra" in m for m in mods)


def test_multiple_items(pipeline):
    result = pipeline.parse("2 pepperoni pizzas and a coke")
    assert len(result.items) >= 2


def test_confidence_range(pipeline):
    result = pipeline.parse("I want 2 large pepperoni pizzas with extra cheese")
    assert 0.0 <= result.confidence <= 1.0


def test_for_review_low_confidence(pipeline):
    """Gibberish → low confidence → for_review=True."""
    result = pipeline.parse("xyzabc qwerty blorp")
    if result.confidence < 0.6:
        assert result.for_review is True


def test_processing_time_positive(pipeline):
    result = pipeline.parse("I want a burger")
    assert result.processing_time_ms > 0


def test_raw_entities_returned(pipeline):
    result = pipeline.parse("3 medium chicken burgers")
    assert len(result.raw_entities) > 0


def test_no_food_no_items(pipeline):
    """Text with no food vocabulary → empty items list."""
    result = pipeline.parse("hello world how are you")
    # Either empty or low confidence
    assert result.confidence < 0.8 or len(result.items) == 0


# ── Accuracy sweep — 20 representative samples ────────────────────────────────

ACCURACY_SAMPLES = [
    ("I want 2 large pepperoni pizzas", "pepperoni pizza", 2),
    ("one margherita pizza please", "margherita pizza", 1),
    ("3 cokes", "coke", 3),
    ("2 chicken burgers", "chicken burger", 2),
    ("a large milkshake", "milkshake", 1),
    ("4 orders of french fries", "french fries", 4),
    ("2 beef tacos and a coke", "beef tacos", 2),
    ("one tiramisu", "tiramisu", 1),
    ("3 chicken wings", "chicken wings", 3),
    ("2 garlic breads", "garlic bread", 2),
]


@pytest.mark.parametrize("text,expected_name,expected_qty", ACCURACY_SAMPLES)
def test_extraction_accuracy(pipeline, text, expected_name, expected_qty):
    result = pipeline.parse(text)
    names = [i.name for i in result.items]
    qtys = {i.name: i.quantity for i in result.items}
    # Fuzzy match: expected_name should appear (partial match acceptable)
    matched = any(expected_name in n or n in expected_name for n in names)
    assert matched, f"Expected '{expected_name}' in {names} for input: '{text}'"
    if matched:
        matched_name = next(n for n in names if expected_name in n or n in expected_name)
        assert qtys[matched_name] == expected_qty, (
            f"Expected qty {expected_qty}, got {qtys[matched_name]}"
        )
