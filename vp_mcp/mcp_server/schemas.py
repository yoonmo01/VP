from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal

class RolePrompt(BaseModel):
    system: str = Field(min_length=1)

class GuidanceInput(BaseModel):
    type: Literal["A", "P"]
    text: str = Field(min_length=1)

class SimulationInput(BaseModel):
    # app의 prompt builder가 채워서 보냄
    attacker: RolePrompt
    victim: RolePrompt
    max_turns: int = Field(default=15, ge=1, le=30)

    # 이어달리기/지침
    case_id_override: Optional[str] = None
    round_no: Optional[int] = None
    guidance: Optional[GuidanceInput] = None  # {"type": "P"|"A", "text": "..."}

    # 메타
    offender_id: int
    victim_id: int

    # ✅ 가변 기본값은 default_factory 사용
    scenario: Dict[str, Any] = Field(default_factory=dict)
    victim_profile: Dict[str, Any] = Field(default_factory=dict)
    templates: Dict[str, Any] = Field(default_factory=dict)

    # ✅ 기본값을 백엔드 호환 안전값으로
    #    - OpenAI: 날짜 포함 버전
    #    - Gemini: v1beta에서도 안전한 1.0-pro (최신 스택이면 .env에서 바꿔주세요)
    models: Dict[str, str] = Field(
        default_factory=lambda: {
            "attacker": "gpt-4o-mini-2024-07-18",
            "victim": "gemini-2.5-flash-lite",
        }
    )

    temperature: float = 0.6

class Turn(BaseModel):
    role: str  # "offender" | "victim"
    text: str  # (서버 구현이 'text' 키를 읽는 형태 그대로 유지)

class SimulationResult(BaseModel):
    conversation_id: str  # (서버는 case_id/conversation_id 둘 다 대응해주니 OK)
    turns: List[Turn]
    ended_by: Optional[str] = None
    stats: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)
