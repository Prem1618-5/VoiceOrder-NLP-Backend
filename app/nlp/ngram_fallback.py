from rapidfuzz import process, fuzz
from app.nlp.schemas import RawEntity

def find_missing_foods(doc_tokens, existing_entities, menu_names):
    occupied_indices = set()
    for ent in existing_entities:
        label = getattr(ent, 'label', ent.get('label') if isinstance(ent, dict) else None)
        if label in ('FOOD', 'CARDINAL', 'SIZE', 'MODIFIER'):
            start = getattr(ent, 'start_token', ent.get('start_token') if isinstance(ent, dict) else None)
            end = getattr(ent, 'end_token', ent.get('end_token') if isinstance(ent, dict) else None)
            if start is not None and end is not None:
                occupied_indices.update(range(start, end))

    new_entities = []
    
    # Extract 3-grams first, then 2-grams to avoid overlapping partial matches
    for n in [3, 2]:
        for i in range(len(doc_tokens) - n + 1):
            start_token = i
            end_token = i + n
            
            if any(j in occupied_indices for j in range(start_token, end_token)):
                continue
                
            from app.nlp.entity_ruler import _MODIFIER_TOKENS
            
            gram_tokens = doc_tokens[start_token:end_token]
            gram_text = " ".join([getattr(t, "text", str(t)) for t in gram_tokens])
            
            # Skip if any word is a modifier
            if any(str(t).lower() in _MODIFIER_TOKENS for t in gram_tokens):
                continue
            
            match = process.extractOne(
                gram_text, 
                menu_names,
                scorer=fuzz.token_sort_ratio, 
                score_cutoff=80
            )
            
            if match:
                matched_name = match[0]
                new_ent = RawEntity(
                    text=matched_name,
                    label='FOOD',
                    start=0,
                    end=0,
                    start_token=start_token,
                    end_token=end_token
                )
                new_entities.append(new_ent)
                occupied_indices.update(range(start_token, end_token))
                
    return new_entities
