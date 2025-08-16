from pydantic import BaseModel, ConfigDict
from typing import Literal
from uuid import UUID
from datetime import datetime

Role = Literal["offender", "victim"]

class ConversationTurn(BaseModel):
    role: Role
    content: str
    label: str | None = None

class ConversationRunRequest(BaseModel):
    offender_id: int
    victim_id: int
    case_scenario: dict
    max_rounds: int = 3  # 필요 시 범위 검증 추가 가능

class ConversationRunResult(BaseModel):
    case_id: UUID
    total_turns: int
    phishing: bool | None
    evidence: str

# 조회용(Log 출력)
class ConversationLogOut(BaseModel):
    turn_index: int                 # DB 컬럼명과 정합성 맞춤을 권장
    role: Role
    content: dict | str             # TEXT/JSONB 혼용 대응
    label: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
