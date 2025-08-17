from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from typing import Literal, Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

Role = Literal["offender", "victim"]

class ConversationTurn(BaseModel):
    role: Role
    content: str
    label: Optional[str] = None

class ConversationRunRequest(BaseModel):
    offender_id: int
    victim_id: int
    case_scenario: Optional[Dict[str, Any]] = None
    max_rounds: int = 15  # 필요 시 범위 검증 추가 가능

class ConversationRunResult(BaseModel):
    case_id: UUID
    total_turns: int
    phishing: Optional[bool]
    evidence: str

# 조회용(Log 출력)
class ConversationLogOut(BaseModel):
    # 입력 시 'turn' 또는 'turn_index' 모두 허용 (출력 키는 turn_index로 고정)
    turn_index: int = Field(..., validation_alias=AliasChoices("turn_index", "turn"))
    role: Role
    content: str
    label: Optional[str] = None
    offender_name: Optional[str] = None
    victim_name: Optional[str] = None

    # created_kst가 기본 출력 키.
    # 입력은 created_kst 또는 created_at 어느 쪽이 와도 허용.
    created_kst: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("created_kst", "created_at"),
    )

    model_config = ConfigDict(populate_by_name=True)

class ConversationRunLogs(BaseModel):
    case_id: UUID
    total_turns: int
    logs: List[ConversationLogOut]   # ✅ 판단은 제외