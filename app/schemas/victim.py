#app/schemas/victim.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional

class VictimCreate(BaseModel):
    name: str
    meta: dict[str, Any] = Field(default_factory=dict)       
    knowledge: dict[str, Any] = Field(default_factory=dict)  
    traits: dict[str, Any] = Field(default_factory=dict)     
    is_active: bool = True                         # ✅ 기본 True
    photo_path: Optional[str] = None               # ✅ 이미지 경로 (선택)

class VictimOut(BaseModel):
    id: int
    name: str
    meta: dict
    knowledge: dict
    traits: dict
    is_active: bool                               # ✅ 출력에도 포함
    photo_path: Optional[str] = None              # ✅ 출력에도 포함

    model_config = ConfigDict(from_attributes=True)





