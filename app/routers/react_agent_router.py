# app/routers/react_agent_router.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.logging import get_logger
from app.services.agent.orchestrator_react import run_orchestrated

logger = get_logger(__name__)
router = APIRouter(prefix="/react-agent", tags=["React Agent"])


# ---------- Request Schemas (프론트 입력용) ----------

class VictimInfo(BaseModel):
    # (선택) 프론트에서 개별 victim 프로파일을 직접 넘길 수도 있어서 남겨둠.
    # 실제 victim은 DB victim_id로 로드되며, 이 필드는 커스텀 시나리오에서 힌트 정도로만 사용됩니다.
    age: Optional[int] = None
    tech_literacy: Optional[str] = Field(default=None, description="low/medium/high")
    personality: Dict[str, Any] = Field(default_factory=dict)
    background: Dict[str, Any] = Field(default_factory=dict)


class ScenarioInfo(BaseModel):
    type: str = Field(description="시나리오 타입(예: generic_test | custom)")
    description: str = Field(description="시나리오 설명")
    steps: List[str] = Field(default_factory=list, description="공격 단계들")
    target: Optional[str] = Field(default=None, description="타겟 정보")


class SimulationRequest(BaseModel):
    offender_id: int = Field(description="DB상 공격자 ID")
    victim_id: int = Field(description="DB상 피해자 ID")
    scenario: ScenarioInfo
    objectives: List[str] = Field(default_factory=lambda: ["education"])
    # 프론트에서는 max_turns/rounds를 절대 보내지 않습니다(서버 고정).
    # Tavily는 'custom' 시나리오일 때만 켜집니다(서버에서 자동 판단).


# ---------- Response Schema (선택) ----------

class SimulationResponse(BaseModel):
    success: bool
    case_id: UUID
    rounds: int
    turns_per_round: int
    timestamp: str
    meta: Dict[str, Any]


# ---------- Route (오케스트레이터 진입점 하나) ----------

@router.post("/simulation", response_model=SimulationResponse, summary="툴 기반 React 오케스트레이션 시뮬레이션")
def run_simulation(req: SimulationRequest, db: Session = Depends(get_db)):
    """
    프론트 → 오케스트레이터(툴 기반) 단일 진입점.

    - 서버 고정값:
      * turns_per_round(=15) : (공격자1 + 피해자1)을 1턴으로 간주, 한 사이클 최대 15턴
      * cycles: 에이전트가 내부 판단으로 2~5회 수행
      * Tavily: 시나리오 type == 'custom' 일 때만 등록 및 사용

    - 내부에서 `run_orchestrated`가 아래 툴들을 상황에 따라 호출:
      * sim.fetch_entities / sim.compose_prompts / sim.persist_turn / sim.should_stop
      * mcp.simulator_run (WS/HTTP)
      * admin.judge / admin.pick_guidance / admin.save_prevention
      * (custom일 때만) tavily.search
    """
    try:
        use_tavily = (req.scenario.type.lower() == "custom")

        payload = {
            "offender_id": req.offender_id,
            "victim_id": req.victim_id,
            "scenario": req.scenario.dict(),
            "objectives": req.objectives,
            "use_tavily": use_tavily,
            # max_turns / cycles는 오케스트레이터 내부 고정값 사용
        }

        result: Dict[str, Any] = run_orchestrated(db, payload)

        if result.get("status") != "success":
            # 오케스트레이터에서 에러 메시지 제공 시 그대로 노출
            raise HTTPException(status_code=500, detail=result.get("error", "simulation failed"))

        # 오케스트레이터가 반환하는 표준 필드 예시:
        # {
        #   "status": "success",
        #   "case_id": "<uuid>",
        #   "rounds": 3,
        #   "turns_per_round": 15,
        #   "timestamp": "....",
        #   "used_tools": [...],
        #   "mcp_used": true,
        #   "tavily_used": false
        # }
        return SimulationResponse(
            success=True,
            case_id=UUID(result["case_id"]),
            rounds=int(result.get("rounds", 0)),
            turns_per_round=int(result.get("turns_per_round", 15)),
            timestamp=result.get("timestamp", datetime.now().isoformat()),
            meta={
                "objectives": req.objectives,
                "mcp_used": bool(result.get("mcp_used", False)),
                "tavily_used": bool(result.get("tavily_used", False)),
                "used_tools": result.get("used_tools", []),
                "agent_type": "react_orchestrator",
                "automation_level": "full",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("React Agent 시뮬레이션 실행 실패")
        raise HTTPException(status_code=500, detail=f"시뮬레이션 실행 실패: {str(e)}")
