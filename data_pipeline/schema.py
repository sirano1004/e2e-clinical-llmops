from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class ParsedHistoryTurn(BaseModel):
    # you are producing: {"role": "user", "content": "DOCTOR: ..."}
    role: Literal["user", "assistant", "system"] = "user"
    content: str

class ParsedEntry(BaseModel):
    """
    Schema for a single unrolled chunk record written to parsed jsonl.
    """
    model_config = ConfigDict(extra="forbid")

    id: str
    session_id: str
    chunk_index: int = Field(ge=0)

    task_type: str = "soap"

    # Inputs
    system_prompt: str = ""
    history: List[ParsedHistoryTurn] = Field(default_factory=list)
    previous_note: Dict[str, Any] = Field(default_factory=dict)
    previous_note_rejected: Dict[str, Any] = Field(default_factory=dict)
    suffix_prompt: str = ""

    # Targets
    completion: Dict[str, Any] = Field(default_factory=dict)
    completion_rejected: Dict[str, Any] = Field(default_factory=dict)

    # Metadata (keep loose if upstream is messy)
    action: Optional[str] = None
    session_start: Optional[datetime] = None
    created_at: Optional[datetime] = None
    data_pipeline_version: Optional[str] = None