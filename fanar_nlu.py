import sys
import os
# Ensure Python can find the other files in the same folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
import json
import re
from typing import Dict, Any, Optional

from schemas import NLUResult, Entities
from prompt import SYSTEM_PROMPT 
from validator import validate_nlu_result

# --- AUTHENTICATION ---
FANAR_API_KEY = "EAwYyPhpNKiiAV9mguCtBSBij9iayirt" 
FANAR_API_URL = "https://api.fanar.qa/v1/chat/completions"

def _clean_json_output(text: str) -> str:
    """Robust extraction of the main JSON block."""
    text = text.strip()
    start_idx = text.find('{')
    if start_idx == -1: return text 
    
    end_idx = text.rfind('}')
    if end_idx == -1: return text[start_idx:] 
    return text[start_idx : end_idx + 1]

def _repair_json_string(json_str: str) -> str:
    """Smart Repair for missing commas."""
    json_str = re.sub(r'"\s+"(\w+)":', r'", "\1":', json_str)
    json_str = re.sub(r'(\d+|true|false|null)\s+"(\w+)":', r'\1, "\2":', json_str)
    json_str = re.sub(r'"\s+"', '", "', json_str)
    return json_str

def fanar_nlu(text: str, image_base64: Optional[str] = None) -> NLUResult:
    headers = {
        "Authorization": f"Bearer {FANAR_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # --- CONDITIONAL PAYLOAD FORMATTING ---
    if image_base64:
        # Multimodal format for Scene Description / OCR
        user_content = [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
        ]
        model_name = "Fanar" 
    else:
        # Standard string format for normal voice commands
        user_content = text
        model_name = "Fanar"
        
    payload = {
        "model": model_name, 
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.1,
        "top_p": 0.9,
    }

    try:
        response = requests.post(FANAR_API_URL, headers=headers, json=payload, timeout=45)
        
        # --- CATCH SPECIFIC API ERRORS ---
        if response.status_code != 200:
            print(f"❌ FANAR API ERROR [{response.status_code}]: {response.text}")
            response.raise_for_status() 
            
        response_data = response.json()
        raw_output = response_data["choices"][0]["message"]["content"]
        
        json_str = _clean_json_output(raw_output)
        
        # --- SMART PARSING LOGIC ---
        data = None
        repaired_str = _repair_json_string(json_str)
        attempts = ["", "}", "}}", "}}}", '"}', '"}}', '"]}', '"]}}']
        
        for suffix in attempts:
            try:
                data = json.loads(repaired_str + suffix)
                break 
            except json.JSONDecodeError:
                continue 
        
        if data is None:
            print(f"\n JSON CRASH (Unfixable). Full Output:\n{raw_output}\n")
            return NLUResult(intent="clarification", confidence=0.0, entities=Entities(), needs_clarification=True)

        entities_data = data.get("entities", {}) or {}
        entities_obj = Entities(**entities_data)

        result = NLUResult(
            intent=data.get("intent", "unknown"),
            confidence=float(data.get("confidence", 0.0)),
            entities=entities_obj,
            needs_clarification=data.get("needs_clarification", False),
            viora_response=data.get("viora_response", "حاضر، جاري معالجة طلبك.")
        )
        
        if result.intent == "document_qa":
            result.entities.question = text

        return validate_nlu_result(result)

    except Exception as e:
        print(f"Error processing NLU via Fanar: {e}")
        return NLUResult(intent="clarification", confidence=0.0, entities=Entities(), needs_clarification=True)