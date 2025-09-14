# app/schemas/schemas_custom.py
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

# ----- Victim -----
class CustomVictimCreate(BaseModel):
    name: str
    meta: Dict[str, Any] = Field(default_factory=dict)
    knowledge: Dict[str, Any] = Field(default_factory=dict)
    traits: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None

class CustomVictimOut(BaseModel):
    id: int
    name: str
    meta: Dict[str, Any]
    knowledge: Dict[str, Any]
    traits: Dict[str, Any]
    is_active: bool

# ----- Scenario -----
class CustomScenarioCreate(BaseModel):
    purpose: str                              # 사용자 입력(필수)
    steps: Optional[List[str]] = None         # 없으면 서버가 생성
    use_tavily: bool = True                   # 기본값: tavily 사용
    tavily_query: Optional[str] = None        # 없으면 purpose로 검색
    k: int = 5                                # 검색 결과 개수
    note: Optional[str] = None

class CustomScenarioOut(BaseModel):
    id: int
    purpose: str
    steps: List[str]
    source: Optional[Dict[str, Any]] = None   # tavily 메타(선택)
    is_active: bool

# ----- Resolve(시뮬 직전 전달형) -----
class ResolveIn(BaseModel):
    custom_victim_id: Optional[str] = None
    custom_scenario_id: Optional[str] = None

class ResolveOut(BaseModel):
    victim_profile: Dict[str, Any]            # {meta, knowledge, traits}
    scenario: Dict[str, Any]                  # {purpose, steps, source?}
