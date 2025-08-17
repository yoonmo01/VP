# app/routers/conversations.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import timezone, datetime
from zoneinfo import ZoneInfo

from app.utils.deps import get_db
from app.schemas.conversation import (
    ConversationRunRequest,
    ConversationRunLogs,
    ConversationLogOut,
)
from app.services.simulation import run_two_bot_simulation
from app.services.conversations_read import fetch_logs_by_case  # ✅ 교체

router = APIRouter(prefix="/conversations", tags=["conversations"])

KST = ZoneInfo("Asia/Seoul")

def to_kst(dt: datetime | None) -> datetime | None:
    """UTC/naive datetime -> KST로 변환"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)

@router.post("/run", response_model=ConversationRunLogs)
def run_conversation(payload: ConversationRunRequest, db: Session = Depends(get_db)):
    # 1) 시뮬레이션 실행 → case_id, 총 턴 수 반환
    case_id, total_turns = run_two_bot_simulation(db, payload)

    # 2) 로그 조회
    rows = fetch_logs_by_case(db, case_id)

    def _get(r, key, default=None):
        # dict 또는 객체 속성 모두 안전하게 접근
        if isinstance(r, dict):
            return r.get(key, default)
        return getattr(r, key, default)

    logs = []
    for r in rows:
        created_at = _get(r, "created_at")
        # created_at이 datetime이면 ISO 문자열로 변환
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()

        logs.append({
            "turn_index": _get(r, "turn_index"),
            "role": _get(r, "role"),
            "content": _get(r, "content"),
            "created_at": created_at,
            "offender_name": _get(r, "offender_name"),
            "victim_name": _get(r, "victim_name"),
        })

    return {
        "case_id": str(case_id),
        "total_turns": total_turns,
        "logs": logs,
    }
