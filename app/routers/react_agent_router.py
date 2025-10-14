# app/routers/react_agent_router.py
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.logging import get_logger
from app.services.agent.orchestrator_react import run_orchestrated_stream  # <- async generator 여야 함

from pydantic import BaseModel

logger = get_logger(__name__)
router = APIRouter(prefix="/react-agent", tags=["React Agent"])


# --- (참고) 비스트리밍 요약 응답 스키마 - 기존 유지 가능 ---
class SimulationResponse(BaseModel):
    success: bool
    case_id: UUID
    rounds: int
    turns_per_round: int
    timestamp: str
    meta: Dict[str, Any]


def _json_line(data: Dict[str, Any]) -> str:
    """SSE data: ... 포맷으로 보낼 JSON 직렬화 보조함수"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get(
    "/simulation/stream",
    summary="SSE로 MCP 에이전트 스트리밍 (GET 전용)",
)
async def stream_simulation_sse(
    # 최소한의 파라미터를 쿼리로 받음 (EventSource는 GET만 가능)
    case_id: Optional[str] = Query(default=None),
    offender_id: Optional[int] = Query(default=None),
    victim_id: Optional[int] = Query(default=None),
    use_tavily: bool = Query(default=False),
    turns_per_round: int = Query(default=15),
    max_rounds: int = Query(default=3),
    db: Session = Depends(get_db),
):
    """
    브라우저 EventSource로 구독:
      /react-agent/simulation/stream?case_id=...&offender_id=...&victim_id=...&use_tavily=true

    - MCP 오케스트레이터가 async generator로 이벤트(dict)를 흘려준다고 가정
    - 이벤트는 그대로 SSE data: ... 으로 패스스루
    """
    # case_id 보장
    resolved_case_id = case_id or str(uuid4())

    # 오케스트레이터에 넘길 페이로드 구성 (너의 스키마에 맞게 필요한 키만)
    payload: Dict[str, Any] = {
        "case_id": resolved_case_id,
        "offender_id": offender_id,
        "victim_id": victim_id,
        "use_tavily": bool(use_tavily),
        "turns_per_round": int(turns_per_round),
        "max_rounds": int(max_rounds),
        # 필요하면 custom_scenario, custom_victim 등도 쿼리로 받아 추가
    }

    async def event_generator():
        # 주기적 하트비트(프록시 타임아웃 방지)
        HEARTBEAT_INTERVAL = 15  # seconds
        next_heartbeat = asyncio.get_event_loop().time() + HEARTBEAT_INTERVAL

        try:
            # 시작 이벤트 (선택)
            yield _json_line({"type": "start", "case_id": resolved_case_id, "ts": datetime.now().isoformat()})

            # MCP → 백엔드 스트리밍
            async for event in run_orchestrated_stream(db, payload):
                # event가 dict가 아닐 가능성 방어
                if not isinstance(event, dict):
                    event = {"type": "message", "text": str(event)}
                # 최소 공통 필드 주입
                event.setdefault("case_id", resolved_case_id)
                event.setdefault("ts", datetime.now().isoformat())

                yield _json_line(event)

                # 하트비트
                now = asyncio.get_event_loop().time()
                if now >= next_heartbeat:
                    # SSE 주석 프레임(클라이언트에 안 보임) 혹은 빈 이벤트
                    yield ": ping\n\n"  # 주석 라인
                    next_heartbeat = now + HEARTBEAT_INTERVAL

                await asyncio.sleep(0)  # 이벤트 루프 양보

            # 완료 이벤트
            yield _json_line({"type": "complete", "case_id": resolved_case_id, "ts": datetime.now().isoformat()})

        except Exception as e:
            logger.exception("SSE stream failed")
            # 에러 이벤트 후 스트림 종료
            yield _json_line({"type": "error", "case_id": resolved_case_id, "message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx 버퍼링 방지
        },
    )

# # app/routers/react_agent_router.py
# from __future__ import annotations

# from datetime import datetime
# from typing import Any, Dict
# from uuid import UUID, uuid4
# import json
# import asyncio


# from fastapi import APIRouter, Depends, HTTPException
# from fastapi.responses import StreamingResponse
# from sqlalchemy.orm import Session

# from app.db.session import get_db
# from app.core.logging import get_logger
# from app.services.agent.orchestrator_react import run_orchestrated_stream

# # ✅ 새 스키마 사용
# from app.schemas.simulation_request import SimulationStartRequest

# logger = get_logger(__name__)
# router = APIRouter(prefix="/react-agent", tags=["React Agent"])


# # ---------- Response Schema (유지) ----------
# from pydantic import BaseModel, Field

# class SimulationResponse(BaseModel):
#     success: bool
#     case_id: UUID
#     rounds: int
#     turns_per_round: int
#     timestamp: str
#     meta: Dict[str, Any]

# # ✅ 새로 추가: SSE 스트리밍 엔드포인트
# @router.post(
#     "/simulation/stream",
#     summary="SSE 스트리밍 시뮬레이션",
# )
# async def stream_simulation(req: SimulationStartRequest, db: Session = Depends(get_db)):
#     """
#     Server-Sent Events로 라운드별 실시간 스트리밍
#     """
#     async def event_generator():
#         try:
#             # case_id 생성
#             from uuid import uuid4
            
#             # 페이로드 준비
#             payload = req.model_dump(mode="python")
#             payload["case_id"] = req.case_id
#             payload["use_tavily"] = bool(req.use_tavily)
            
#             # 오케스트레이터 스트리밍 실행
#             async for event in run_orchestrated_stream(db, payload):
#                 yield f"data: {json.dumps(event)}\n\n"
#                 await asyncio.sleep(0.01)  # 버퍼링 방지
            
#             # 완료 이벤트
#             yield f"data: {json.dumps({'type': 'complete', 'case_id': req.case_id})}\n\n"
            
#         except Exception as e:
#             logger.exception("SSE 스트리밍 실패")
#             yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
#     return StreamingResponse(
#         event_generator(),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "Connection": "keep-alive",
#             "X-Accel-Buffering": "no",  # nginx 버퍼링 비활성화
#         }
#     )

# # ---------- Route (오케스트레이터 진입점 하나) ----------
# @router.post(
#     "/simulation",
#     response_model=SimulationResponse,
#     summary="툴 기반 React 오케스트레이션 시뮬레이션",
# )
# def start_simulation(req: SimulationStartRequest, db: Session = Depends(get_db)):
#     """
#     프론트 → 오케스트레이터(툴 기반) 단일 진입점.

#     선택 규칙:
#     - 피해자: custom_victim O → 그 데이터 사용 / 없으면 victim_id로 DB 로드
#     - 시나리오: custom_scenario O → Tavily 생성→DB 저장→사용 / 없으면 offender_id로 DB 로드

#     서버 고정:
#     - turns_per_round = 15 (공+피 한 쌍 = 1턴)
#     - 라운드 수는 오케스트레이터가 내부 판단(2~5회)
#     - Tavily는 custom_scenario 있을 때 자동 활성화
#     """
#     try:
#         # Tavily 사용 여부: 커스텀 시나리오가 있고, (프론트에서 켠 경우 OR 서버가 강제)면 True
#         tavily_used_flag = bool(req.custom_scenario) and bool(req.use_tavily or True)

#         # 오케스트레이터에 그대로 전달(한 곳에서 분기/DB 로딩/템플릿 패키징 처리)
#         payload: Dict[str, Any] = req.model_dump(mode="python")
#         payload["use_tavily"] = tavily_used_flag

#         # ★ 없으면 새로 생성해서 주입
#         if not payload.get("case_id"):
#             payload["case_id"] = str(uuid4())
            
#         result: Dict[str, Any] = run_orchestrated(db, payload)

#         if result.get("status") != "success":
#             raise HTTPException(status_code=500, detail=result.get("error", "simulation failed"))

#         return SimulationResponse(
#             success=True,
#             case_id=UUID(result["case_id"]),
#             rounds=int(result.get("rounds", 0)),
#             turns_per_round=int(result.get("turns_per_round", 15)),
#             timestamp=result.get("timestamp", datetime.now().isoformat()),
#             meta={
#                 "mcp_used": bool(result.get("mcp_used", True)),
#                 "tavily_used": bool(result.get("tavily_used", tavily_used_flag)),
#                 "used_tools": result.get("used_tools", []),
#                 "agent_type": "react_orchestrator",
#                 "automation_level": "full",
#             },
#         )

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.exception("React Agent 시뮬레이션 실행 실패")
#         raise HTTPException(status_code=500, detail=f"시뮬레이션 실행 실패: {str(e)}")

