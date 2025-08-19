# app/services/conversations_read.py
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from app.db import models as m


def fetch_logs_by_case(db: Session, case_id: UUID) -> List[Dict[str, Any]]:
    """
    주어진 case_id의 대화 로그를 run→turn_index 순으로 반환.
    conversations.py의 get_val(...) 매핑(speaker/text 등)과 호환되도록 별칭을 맞춘다.
    """
    rows = (
        db.query(
            m.ConversationLog.id.label("id"),
            m.ConversationLog.turn_index.label("turn_index"),
            m.ConversationLog.role.label("speaker"),  # role -> speaker
            m.ConversationLog.content.label("text"),  # content -> text
            m.ConversationLog.label.label("label"),
            m.ConversationLog.created_at.label("created_at"),
            # ✅ 새 표식들
            m.ConversationLog.use_agent.label("use_agent"),
            m.ConversationLog.run.label("run"),
            m.ConversationLog.guidance_type.label("guidance_type"),
            m.ConversationLog.guideline.label("guideline"),
            # 표시용 이름
            m.PhishingOffender.name.label("offender_name"),
            m.Victim.name.label("victim_name"),
        ).join(m.PhishingOffender,
               m.PhishingOffender.id == m.ConversationLog.offender_id).join(
                   m.Victim,
                   m.Victim.id == m.ConversationLog.victim_id).filter(
                       m.ConversationLog.case_id == case_id).order_by(
                           m.ConversationLog.run.asc(),  # 1회차 -> 2회차 ...
                           m.ConversationLog.turn_index.asc(),
                           m.ConversationLog.created_at.asc(),
                       ).mappings()  # RowMapping(dict-like) 반환
        .all())
    # dict 리스트로 변환
    return [dict(r) for r in rows]
