from schemas import NLUResult
from intents import MASTER_INTENTS

def validate_nlu_result(result: NLUResult) -> NLUResult:
    """
    Sanity Check: 
    If the AI returns high confidence but misses a REQUIRED entity, 
    we forcibly downgrade it to 'needs_clarification'.
    """
    
    intent_def = next((i for i in MASTER_INTENTS if i.name == result.intent), None)
    
    if not intent_def:
        return result 

    missing_keys = []
    entities_dict = result.entities.model_dump()
    
    for req_key in intent_def.required_entities:
        value = entities_dict.get(req_key)
        
        if value is None or value == "" or value == []:
            missing_keys.append(req_key)

    if missing_keys:
        print(f"VALIDATOR: Intent '{result.intent}' missing required fields {missing_keys}. Forcing Clarification.")
        
        result.needs_clarification = True
        result.confidence = 0.5 
        result.viora_response = "معلش مفهمتش قصدك بالظبط، ممكن توضح أكتر؟" # Override with clarification request
    
    return result