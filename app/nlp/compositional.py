import rapidfuzz
from rapidfuzz import process, fuzz
from app.nlp.schemas import RawEntity

def resolve_compositional(doc_tokens, menu_names):
    base_meats = {"chicken", "mutton", "paneer"}
    bread_modifiers = {"garlic", "butter", "cheese", "plain", "aloo", "tandoori", "masala"}
    primary_keywords = base_meats.union(bread_modifiers)
    secondary_keywords = {"biryani", "tikka", "curry", "naan", "roti", "paratha", "kulcha", "dosa"}
    
    new_entities = []
    
    for i, token in enumerate(doc_tokens):
        # Handle string or spacy-like token
        token_text = str(token) if isinstance(token, str) else getattr(token, "text", str(token))
        token_text_lower = token_text.lower()
        
        if token_text_lower in primary_keywords:
            for j in range(i + 1, min(i + 12, len(doc_tokens))):
                ahead_token = doc_tokens[j]
                ahead_text = str(ahead_token) if isinstance(ahead_token, str) else getattr(ahead_token, "text", str(ahead_token))
                ahead_text_lower = ahead_text.lower()
                
                if ahead_text_lower in secondary_keywords:
                    combined = f"{token_text_lower} {ahead_text_lower}"
                    
                    match = process.extractOne(
                        combined, 
                        menu_names,
                        scorer=fuzz.WRatio,
                        score_cutoff=80
                    )
                    
                    if match:
                        matched_name = match[0]
                        anchor = j if token_text_lower in base_meats else i
                        new_entities.append(
                            RawEntity(
                                text=matched_name,
                                label='FOOD',
                                start=0,
                                end=0,
                                start_token=anchor,
                                end_token=anchor + 1
                            )
                        )
                        
    return new_entities
