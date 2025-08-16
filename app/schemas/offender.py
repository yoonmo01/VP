from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional

class OffenderCreate(BaseModel):
    name: str
    type: Optional[str] = None
    profile: dict[str, Any] = Field(default_factory=dict)  # ✅ 가변 기본값 안전 처리
    is_active: Optional[bool] = True

class OffenderOut(BaseModel):
    id: int
    name: str
    type: Optional[str] = None
    profile: dict
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
