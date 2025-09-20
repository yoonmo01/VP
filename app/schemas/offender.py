#app/schemas/offender.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional, Dict,List

class OffenderCreate(BaseModel):
    name: str = Field(..., max_length=100)
    type: str = Field(..., max_length=50)
    purpose: str
    steps: List[str]

    
class OffenderOut(BaseModel):
    id: int
    name: str
    type: Optional[str] = None
    profile: Dict[str, Any]
    source: Dict[str, Any]                                  # ✅ 응답에도 포함
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
