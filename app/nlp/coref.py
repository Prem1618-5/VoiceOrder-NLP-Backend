from app.nlp.schemas import RawEntity

def resolve_coreferences(doc_tokens, entities):
    updated_entities = list(entities)
    
    occupied_indices = set()
    for ent in entities:
        if ent.label == "FOOD" and ent.start_token is not None and ent.end_token is not None:
            occupied_indices.update(range(ent.start_token, ent.end_token))
    
    for i, token in enumerate(doc_tokens):
        prev_foods = [
            e for e in entities 
            if e.label == "FOOD" and e.end_token is not None and e.end_token <= i
        ]
        if i in occupied_indices:
            continue
            
        for food in reversed(prev_foods):
            words = food.text.split()
            if not words:
                continue
            first_word = words[0]
            if token.lower() == first_word.lower():
                new_entity = RawEntity(
                    text=food.text,
                    label="FOOD",
                    start=0,
                    end=0,
                    start_token=i,
                    end_token=i + 1
                )
                updated_entities.append(new_entity)
                break
                
    return updated_entities
