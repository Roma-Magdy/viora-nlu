from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class Entities(BaseModel):
    # --- Search Entities ---
    search_query: Optional[str] = Field(default=None, description="The topic to search for")
    file_types: Optional[List[str]] = Field(default=None, description="List of allowed extensions e.g. ['pdf', 'pptx']")
    
    # --- File Access ---
    document_name: Optional[str] = None
    
    # --- Navigation ---
    page_number: Optional[int] = None
    navigation_direction: Optional[Literal["next", "previous", "to", "forward", "back"]] = None
    
    # --- Reading Control ---
    reading_action: Optional[Literal["start", "stop", "pause", "resume"]] = None
    
    # --- Q&A ---
    question: Optional[str] = None
    
    # --- Study Aids ---
    study_aid_type: Optional[Literal["quiz", "flashcards"]] = None
    summary_format: Optional[str] = None
    
    # --- System Control ---
    focus_status: Optional[Literal["enable", "disable"]] = None
    
    # --- NEW: Camera Control ---
    camera_action: Optional[Literal["start", "stop"]] = None 

class NLUResult(BaseModel):
    intent: str
    confidence: float
    entities: Entities
    needs_clarification: bool = False
    viora_response: str = "عذراً، لم أتمكن من معالجة طلبك." # Default fallback