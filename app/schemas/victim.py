from pydantic import BaseModel, ConfigDict, Field
from typing import Any

class VictimCreate(BaseModel):
    name: str
    meta: dict[str, Any] = Field(default_factory=dict)       # ✅
    knowledge: dict[str, Any] = Field(default_factory=dict)  # ✅
    traits: dict[str, Any] = Field(default_factory=dict)     # ✅

class VictimOut(BaseModel):
    id: int
    name: str
    meta: dict
    knowledge: dict
    traits: dict

    model_config = ConfigDict(from_attributes=True)
