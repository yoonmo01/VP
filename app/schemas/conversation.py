# app/schemas/conversation.py
from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from typing import Literal, Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

Role = Literal["offender", "victim"]


class ConversationTurn(BaseModel):
    role: Role
    content: str
    label: Optional[str] = None


# 🔹 Path 버전 전용 바디: 프런트가 보내는 페이로드 (ID 없음)
class ConversationRunBody(BaseModel):
    include_judgement: bool = True
    max_turns: int = 30
    agent_mode: Literal["off", "admin", "police"] = "off"
    case_scenario: Optional[Dict[str, Any]] = None

    @property
    def max_rounds(self) -> int:
        return self.max_turns

    @property
    def scenario(self) -> Dict[str, Any] | None:
        return self.case_scenario


# 🔹 내부 실행용 요청 모델: Path ID + Body 병합 후 사용
class ConversationRunRequest(BaseModel):
    offender_id: int
    victim_id: int
    include_judgement: bool = True
    max_turns: int = 30
    agent_mode: Literal["off", "admin", "police"] = "off"
    case_scenario: Optional[Dict[str, Any]] = None

    @property
    def max_rounds(self) -> int:
        return self.max_turns

    @property
    def scenario(self) -> Dict[str, Any] | None:
        return self.case_scenario


class ConversationRunResult(BaseModel):
    case_id: UUID
    total_turns: int
    phishing: Optional[bool]
    evidence: str


# 조회용(Log 출력)
class ConversationLogOut(BaseModel):
    # 입력 시 'turn' 또는 'turn_index' 모두 허용 (출력 키는 turn_index로 고정)
    turn_index: int = Field(
        ..., validation_alias=AliasChoices("turn_index", "turn"))
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

    # ✅ 신규
    use_agent: Optional[bool] = None
    run: Optional[int] = None
    guidance_type: Optional[str] = None  # 'P'|'A'|None
    guideline: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class ConversationRunLogs(BaseModel):
    case_id: UUID
    total_turns: int
    logs: List[ConversationLogOut]
    phishing: Optional[bool] = None  # ✅ 판단 추가
    evidence: Optional[str] = None  # ✅ 근거 추가
