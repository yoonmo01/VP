from pydantic import BaseModel
from typing import Any

class VictimCreate(BaseModel):
    name: str
    meta: dict[str, Any] = {}
    knowledge: dict[str, Any] = {}
    traits: dict[str, Any] = {}

class VictimOut(BaseModel):
    id: int
    name: str
    meta: dict
    knowledge: dict
    traits: dict
    class Config:
        from_attributes = True