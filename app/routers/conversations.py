# app/routers/conversations.py
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from datetime import timezone, datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict
from types import SimpleNamespace

from app.utils.deps import get_db
from app.schemas.conversation import (
    ConversationRunBody,
    ConversationRunRequest,
    ConversationRunLogs,
    ConversationLogOut,
)
from app.services.simulation import run_two_bot_simulation
from app.services.conversations_read import fetch_logs_by_case
from app.services.admin_summary import summarize_case

import uuid, asyncio
from starlette.concurrency import run_in_threadpool
from app.db.session import SessionLocal

router = APIRouter(prefix="/conversations", tags=["conversations"])
KST = ZoneInfo("Asia/Seoul")

# ✅ NEW: 인메모리 잡 상태 저장소 (로컬 개발용)
JOBS: Dict[str, dict] = {
}  # {job_id: {"status": "running|done|error", "case_id": str, "total_turns": int, "error": str}}


def get_val(row: Any, key: str, default=None):
    """Row/ORM/dict 어디서든 안전하게 값 꺼내기"""
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, key):
        return getattr(row, key)
    try:
        return row[key]
    except Exception:
        return default


def to_kst(dt):
    """str/naive/aware datetime -> KST 변환 (안전 파서)"""
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            s = dt.strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


# ✅ NEW: 백그라운드에서 시뮬레이션을 실행하는 잡 함수
async def _run_simulation_job(job_id: str, req: ConversationRunRequest):
    db = SessionLocal()
    try:
        args = req.model_dump()
        if "max_rounds" not in args and "max_turns" in args:
            args["max_rounds"] = args["max_turns"]

        # run_two_bot_simulation 이 동기라고 가정 → 스레드풀에서 실행
        case_id, total_turns = await run_in_threadpool(run_two_bot_simulation,
                                                       db,
                                                       SimpleNamespace(**args))

        JOBS[job_id].update({
            "status": "done",
            "case_id": str(case_id),
            "total_turns": int(total_turns),
        })
    except Exception as e:
        JOBS[job_id].update({
            "status": "error",
            "error": f"{e}",
        })
    finally:
        db.close()


# ✅ NEW: 비동기 킥 엔드포인트 (즉시 반환 → 폴링으로 상태 확인)
@router.post("/run_async/{offender_id}/{victim_id}")
async def run_conversation_async(
    offender_id: int,
    victim_id: int,
    payload: ConversationRunBody,
    response: Response,
):
    # Path + Body 병합
    req = ConversationRunRequest(offender_id=offender_id,
                                 victim_id=victim_id,
                                 **payload.model_dump())

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "running"}

    # 백그라운드 작업 시작
    asyncio.create_task(_run_simulation_job(job_id, req))

    # 클라이언트가 바로 따라갈 수 있게 힌트 제공
    response.headers["Location"] = f"/api/conversations/job/{job_id}"
    response.headers["Retry-After"] = "1"
    return {"job_id": job_id, "status": "accepted"}  # 필요시 202 사용 가능


# ✅ NEW: 잡 상태 조회 (클라이언트 폴링용)
@router.get("/job/{job_id}")
def get_job(job_id: str):
    return JOBS.get(job_id, {"status": "not_found"})


# ✅ CHANGED(유지): 동기 실행 엔드포인트 (기존 로직 그대로 둠)
@router.post("/run/{offender_id}/{victim_id}",
             response_model=ConversationRunLogs)
def run_conversation_with_ids(
        offender_id: int,
        victim_id: int,
        payload: ConversationRunBody,
        db: Session = Depends(get_db),
):
    # 1) Path + Body 병합 → 실행용 요청 모델
    req = ConversationRunRequest(offender_id=offender_id,
                                 victim_id=victim_id,
                                 **payload.model_dump())

    # 2) 내부 실행 함수 호환용: max_rounds 보정
    run_args = req.model_dump()
    if "max_rounds" not in run_args and "max_turns" in run_args:
        run_args["max_rounds"] = run_args["max_turns"]

    # 3) 시뮬레이션 실행
    case_id, total_turns = run_two_bot_simulation(db,
                                                  SimpleNamespace(**run_args))

    # 4) 로그 조회 → 출력 스키마로 매핑
    rows = fetch_logs_by_case(db, case_id)
    logs = [
        ConversationLogOut(
            turn_index=get_val(r, "turn_index", 0),
            role="offender"
            if get_val(r, "speaker") == "offender" else "victim",
            content=get_val(r, "text", ""),
            label=get_val(r, "label"),
            created_kst=to_kst(get_val(r, "created_at")),
            offender_name=get_val(r, "offender_name"),
            victim_name=get_val(r, "victim_name"),
            # ✅ 추가
            use_agent=get_val(r, "use_agent", False),
            run=get_val(r, "run", 1),
            guidance_type=get_val(r, "guidance_type"),
            guideline=get_val(r, "guideline"),
        ) for r in rows
    ]

    # 5) (옵션) 피해 판정
    phishing = None
    evidence = None
    if req.include_judgement:
        try:
            result = summarize_case(db, case_id)
            phishing = result.get("phishing")
            evidence = result.get("evidence")
        except Exception as e:
            phishing = None
            evidence = f"[summarize_case 실패] {e}"

    return {
        "case_id": case_id,
        "total_turns": total_turns,
        "logs": logs,
        "phishing": phishing,
        "evidence": evidence,
    }


# ✅ NEW: (선택) 증분 조회 tail 엔드포인트 — 실시간 폴링에 유용
from fastapi import Query
from uuid import UUID


@router.get("/{case_id}/tail", response_model=ConversationRunLogs)
def get_conversation_tail(
        case_id: UUID,
        after: int = Query(-1, description="이 turn_index 이후만 반환"),
        db: Session = Depends(get_db),
):
    rows = fetch_logs_by_case(
        db, case_id)  # 성능 위해 실제 SQL에서 turn_index > :after 로 제한 권장
    logs_all = [
        ConversationLogOut(
            turn_index=get_val(r, "turn_index", 0),
            role="offender"
            if get_val(r, "speaker") == "offender" else "victim",
            content=get_val(r, "text", ""),
            label=get_val(r, "label"),
            created_kst=to_kst(get_val(r, "created_at")),
            offender_name=get_val(r, "offender_name"),
            victim_name=get_val(r, "victim_name"),
            # ✅ 추가
            use_agent=get_val(r, "use_agent", False),
            run=get_val(r, "run", 1),
            guidance_type=get_val(r, "guidance_type"),
            guideline=get_val(r, "guideline"),
        ) for r in rows
    ]
    logs = [l for l in logs_all if (l.turn_index or 0) > after]
    return {
        "case_id": case_id,
        "total_turns": len(logs_all),
        "logs": logs,
        "phishing": None,
        "evidence": None,
    }
