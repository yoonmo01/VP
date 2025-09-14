from __future__ import annotations
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator

class CustomVictim(BaseModel):
    meta: Dict[str, Any] = Field(default_factory=dict)
    knowledge: Dict[str, Any] = Field(default_factory=dict)
    traits: Dict[str, Any] = Field(default_factory=dict)

class CustomScenarioSeed(BaseModel):
    # 커스텀 시나리오 시드(프론트에서 넘어오는 최소 정보)
    type: Optional[str] = None          # 예: "기관사칭"
    purpose: Optional[str] = None       # 예: "현금 편취"
    text: Optional[str] = None          # 자유 서술
    objectives: Optional[List[str]] = None  # 임시 단계/목표

class SimulationStartRequest(BaseModel):
    # ─ 피해자 선택 ─
    custom_victim: Optional[CustomVictim] = None
    victim_id: Optional[int] = None             # custom_victim 없으면 필수

    # ─ 시나리오 선택 ─
    custom_scenario: Optional[CustomScenarioSeed] = None
    offender_id: Optional[int] = None           # custom_scenario 없으면 필수

    # 공통 옵션
    use_tavily: bool = False                    # 커스텀 시나리오일 때만 사용 권장
    max_turns: int = Field(default=15, ge=1, le=30)

    # 레거시 호환(프론트가 이미 보내는 값 케어용)
    scenario: Optional[Dict[str, Any]] = None
    objectives: Optional[List[str]] = None

    @model_validator(mode="after")
    def _validate_choice(self):
        # 피해자: custom_victim 또는 victim_id 중 하나는 반드시 있어야 함
        if not self.custom_victim and self.victim_id is None:
            raise ValueError("victim_id 또는 custom_victim 중 하나는 필수입니다.")
        # 시나리오: custom_scenario 또는 offender_id 중 하나는 반드시 있어야 함
        if not self.custom_scenario and self.offender_id is None:
            raise ValueError("offender_id 또는 custom_scenario 중 하나는 필수입니다.")
        return self
