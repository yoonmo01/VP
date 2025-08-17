# app/services/conversations_read.py
from __future__ import annotations
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
from app.db import models as m

def fetch_logs_by_case(db: Session, case_id: UUID) -> List[Dict[str, Any]]:
    """
    주어진 case_id에 대한 대화 로그를 턴 순서대로 반환.
    Conversation 테이블과의 조인은 불필요하며, 없는 모델로 인해 오류가 나므로 제거.
    """
    rows = (
        db.query(
            m.ConversationLog.id,
            m.ConversationLog.turn_index,
            m.ConversationLog.role,
            m.ConversationLog.content,
            m.ConversationLog.created_at,
            m.PhishingOffender.name.label("offender_name"),
            m.Victim.name.label("victim_name"),
        )
        .join(m.PhishingOffender, m.PhishingOffender.id == m.ConversationLog.offender_id)
        .join(m.Victim, m.Victim.id == m.ConversationLog.victim_id)
        .filter(m.ConversationLog.case_id == case_id)      # ← 핵심: case_id로 필터
        .order_by(m.ConversationLog.turn_index.asc(), m.ConversationLog.created_at.asc())
        .all()
    )

    # 필요 시 dict로 변환 (라우터에서 바로 JSON 응답하기 편하도록)
    return [
        {
            "id": r.id,
            "turn_index": r.turn_index,
            "role": r.role,
            "content": r.content,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "offender_name": r.offender_name,
            "victim_name": r.victim_name,
        }
        for r in rows
    ]
