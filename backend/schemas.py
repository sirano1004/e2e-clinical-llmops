from pydantic import BaseModel, Field, model_validator
from typing import List, Literal, Optional, Dict, Union, Any
from datetime import datetime
import uuid

# --- 0. Building Block ---
class DialogueTurn(BaseModel):
    role: str = Field(..., description="Role: doctor, patient, system, or SPEAKER_XX")
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)

# --- 1. Audio transcription ---
class WordInfo(BaseModel):
    word: str
    start: float
    end: float
    is_unclear: bool

class SegmentInfo(BaseModel):
    id: int
    start: float
    end: float
    text: str
    speaker: str = Field(default="UNKNOWN", description="Speaker ID from Diarization")
    avg_confidence: float
    words: List[WordInfo]

class TranscriptionResponse(BaseModel):
    # This goes to the LLM (It has the "(unclear: word)" tags)
    conversation: List[DialogueTurn] = Field(..., description="Structured transcript")

    # This goes to the UI (For red underlines)
    raw_segments: List[SegmentInfo] = Field(..., description="Metadata for UI highlighting")

# --- HELPER: Strict SOAP Structure ---
# This ensures your SOAP note always has these 4 keys.
class SOAPNote(BaseModel):
    # Using List[str] for bullet points as requested
    subjective: List[str] = Field(default_factory=list)
    objective: List[str] = Field(default_factory=list)
    assessment: List[str] = Field(default_factory=list)
    plan: List[str] = Field(default_factory=list)

# --- 2. Input ---
class ScribeRequest(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dialogue_history: List[DialogueTurn]
    
    # The existing SOAP note state to be updated
    # Can be a JSON string or raw text
    existing_notes: Optional[SOAPNote] = None
    
    # Task determines output format
    task_type: Literal["soap", "soap_final", "referral", "certificate"] = "soap"
    temperature: float = 0.7

# --- 3. Output (Dynamic) ---
class ScribeResponse(BaseModel):
    interaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    
    # It can be a simple String OR a structured SOAP object
    generated_summary: Union[str, SOAPNote, Dict[str, Any]]
    
    # Safety & Quality Checks
    safety_warnings: List[str] = []
    hallucination_warnings: List[str] = []
    citations: Optional[Dict[str, int]] = None

    # Metadata
    model_used: str
    adapter_used: Optional[str] = None
    processing_time_ms: float
    created_at: datetime = Field(default_factory=datetime.now)

# --- 4. Feedback (Training Data) ---
class FeedbackRequest(BaseModel):
    interaction_id: str
    feedback_type: Literal["thumbs_up", "thumbs_down", "edit"]
    
    # If SOAP, user might edit the JSON structure, so we allow Dict here too
    edited_summary: Optional[Union[str, SOAPNote, Dict[str, Any]]] = None
    
    # Context (Smart Denormalization)
    original_model_id: str 
    task_type: str         

    @model_validator(mode='after')
    def check_edit_requirements(self):
        # Access the object itself using 'self'
        if self.feedback_type == 'edit' and not self.edited_summary:
            raise ValueError('Edited summary is required when feedback_type is edit')
        return self