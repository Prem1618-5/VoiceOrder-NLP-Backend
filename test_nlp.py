import asyncio
from app.nlp.pipeline import extract_entities

def test_pipeline():
    text = "I'd like to order two large pepperoni pizzas, one order of garlic bread with extra cheese, and three cans of Diet Coke."
    print(f"Testing: {text}\n")
    
    result = extract_entities(text)
    
    print("Parsed Items:")
    for item in result.items:
        print(f"  - {item.quantity}x {item.size or ''} {item.name} {item.modifiers}")
        
    print(f"\nConfidence: {result.confidence}")
    print(f"For Review: {result.for_review}")

if __name__ == "__main__":
    test_pipeline()
