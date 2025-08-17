from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional, Dict

class OffenderCreate(BaseModel):
    name: str
    type: Optional[str] = None
    profile: Dict[str, Any] = Field(default_factory=dict)   # 가변 기본값 안전
    source: Dict[str, Any] = Field(default_factory=dict)    # {"title":..., "page":..., "url":...}
    is_active: Optional[bool] = True

class OffenderOut(BaseModel):
    id: int
    name: str
    type: Optional[str] = None
    profile: Dict[str, Any]
    source: Dict[str, Any]                                  # ✅ 응답에도 포함
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
