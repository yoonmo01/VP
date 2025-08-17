# app/routers/conversations.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import timezone, datetime
from zoneinfo import ZoneInfo
from typing import Any  # ✅ 추가
from app.utils.deps import get_db
from app.schemas.conversation import (
    ConversationRunRequest,
    ConversationRunLogs,
    ConversationLogOut,
)
from app.services.simulation import run_two_bot_simulation
from app.services.conversations_read import fetch_logs_by_case  # ✅ 교체
from app.services.admin_summary import summarize_case  # ✅ 추가 임포트

router = APIRouter(prefix="/conversations", tags=["conversations"])

KST = ZoneInfo("Asia/Seoul")


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
    # 문자열로 오는 경우(예: "2025-08-17T11:42:55.749003+00:00", "2025-08-17T11:42:55Z")
    if isinstance(dt, str):
        try:
            s = dt.strip()
            # Z(UTC) 표기 보정
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            # Python 표준 ISO 파서
            dt = datetime.fromisoformat(s)
        except Exception:
            # 파싱 실패 시 그냥 반환(또는 None)
            return None
    # timezone 없는 naive -> UTC 가정
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


@router.post("/run/{offender_id}/{victim_id}",
             response_model=ConversationRunLogs)
def run_conversation_with_ids(
    offender_id: int,
    victim_id: int,
    payload: ConversationRunRequest,  # 나머지 설정은 body로 받음
    db: Session = Depends(get_db)):
    # body payload에 id 채워넣기 (기존 로직 재사용)
    payload.offender_id = offender_id
    payload.victim_id = victim_id

    case_id, total_turns = run_two_bot_simulation(db, payload)

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
        ) for r in rows
    ]

    phishing = None
    evidence = None
    if getattr(payload, "include_judgement", True):
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
