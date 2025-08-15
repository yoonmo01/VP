from pydantic import BaseModel
from typing import Any,Optional

class OffenderCreate(BaseModel):
    name: str
    type: Optional[str] = None
    profile: dict[str, Any] = {}
    is_active: Optional[bool] = True

class OffenderOut(BaseModel):
    id: int
    name: str
    type: Optional[str] = None
    profile: dict
    is_active: bool
    class Config:
        from_attributes = True