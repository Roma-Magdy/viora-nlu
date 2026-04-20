import os
import re
import json
import requests
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

# Local project imports
from schemas import NLUResult, Entities
from prompt import SYSTEM_PROMPT 
from validator import validate_nlu_result

# --- INITIALIZATION ---
# Load .env from the root directory
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

FANAR_API_KEY = os.getenv("FANAR_API_KEY")
FANAR_API_URL = "https://api.fanar.qa/v1/chat/completions"

def _clean_json_output(text: str) -> str:
    """Extracts the JSON block from the model's text response."""
    text = text.strip()
    start_idx = text.find('{')
    if start_idx == -1: return text 
    
    end_idx = text.rfind('}')
    if end_idx == -1: return text[start_idx:] 
    return text[start_idx : end_idx + 1]

def _repair_json_string(json_str: str) -> str:
    """Smart Repair for common LLM JSON formatting errors."""
    json_str = re.sub(r'"\s+"(\w+)":', r'", "\1":', json_str)
    json_str = re.sub(r'(\d+|true|false|null)\s+"(\w+)":', r'\1, "\2":', json_str)
    json_str = re.sub(r'"\s+"', '", "', json_str)
    return json_str

def fanar_nlu(text: str) -> NLUResult:
    """
    Main Semantic Engine for Viora.
    Takes English/Arabic text and returns a structured decision.
    """
    if not FANAR_API_KEY:
        print("❌ Error: FANAR_API_KEY not found. Check your .env file.")
        return NLUResult(intent="unknown", confidence=0.0, entities=Entities(), needs_clarification=True)

    headers = {
        "Authorization": f"Bearer {FANAR_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # We use Fanar-2-Prime for high-reasoning text tasks
    payload = {
        "model": "Fanar", 
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        "temperature": 0.1, # Keep it deterministic for JSON output
        "top_p": 0.9,
    }

    try:
        response = requests.post(FANAR_API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ FANAR API ERROR [{response.status_code}]: {response.text}")
            return NLUResult(intent="unknown", confidence=0.0, entities=Entities(), needs_clarification=True)
            
        response_data = response.json()
        raw_output = response_data["choices"][0]["message"]["content"]
        
        # --- JSON PARSING & REPAIR ---
        json_str = _clean_json_output(raw_output)
        repaired_str = _repair_json_string(json_str)
        
        data = None
        # Attempt to fix trailing characters if JSON is cut off
        attempts = ["", "}", "}}", "}}}", '"}', '"}}', '"]}', '"]}}']
        
        for suffix in attempts:
            try:
                data = json.loads(repaired_str + suffix)
                break 
            except json.JSONDecodeError:
                continue 
        
        if data is None:
            print(f"⚠️ JSON Parsing failed. Raw response: {raw_output}")
            return NLUResult(intent="clarification", confidence=0.0, entities=Entities(), needs_clarification=True)

        # --- DATA MAPPING ---
        entities_data = data.get("entities", {}) or {}
        entities_obj = Entities(**entities_data)

        result = NLUResult(
            intent=data.get("intent", "unknown"),
            confidence=float(data.get("confidence", 0.0)),
            entities=entities_obj,
            needs_clarification=data.get("needs_clarification", False),
            viora_response=data.get("viora_response", "اسف مش فاهم طلبك")
        )
        
        # Business Logic: For RAG tasks, ensure the original text is preserved
        if result.intent == "document_qa":
            result.entities.question = text

        return validate_nlu_result(result)

    except Exception as e:
        print(f"🚨 Exception in fanar_nlu: {e}")
        return NLUResult(intent="unknown", confidence=0.0, entities=Entities(), needs_clarification=True)