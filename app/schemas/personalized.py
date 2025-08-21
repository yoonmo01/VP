# app/schemas/personalized.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class PersonalizedOut(BaseModel):
    id: UUID
    case_id: Optional[UUID] = None
    run: Optional[int] = None
    offender_id: Optional[int] = None
    victim_id: Optional[int] = None
    content: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None
    created_at: Optional[datetime] = None
