from pydantic import BaseModel
from typing import Literal
from uuid import UUID
from datetime import datetime

Role = Literal["offender","victim"]

class ConversationTurn(BaseModel):
    role: Role
    content: str
    label: str | None = None

class ConversationRunRequest(BaseModel):
    offender_id: int
    victim_id: int
    case_scenario: dict
    max_rounds: int = 3

class ConversationRunResult(BaseModel):
    case_id: UUID
    total_turns: int
    phishing: bool | None
    evidence: str

# ✅ 조회용(Log 출력)
class ConversationLogOut(BaseModel):
    turn: int
    role: Role
    content: str
    created_at: datetime

    class Config:
        from_attributes = True