# app/routers/conversations_read.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import timezone, timedelta
from typing import List, Optional

from app.db.session import get_db
from app.db import models as m

from app.schemas.conversation import ConversationLogOut
from app.schemas.conversation_read import ConversationBundleOut
from app.schemas.offender import OffenderOut
from app.schemas.victim import VictimOut

router = APIRouter(tags=["conversations"])


@router.get("/conversations/{case_id}", response_model=ConversationBundleOut)
def get_conversation_bundle(case_id: UUID, db: Session = Depends(get_db)):
    # 1) 케이스
    case: Optional[m.AdminCase] = db.get(m.AdminCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")

    # 2) 로그(턴 순)
    logs: List[m.ConversationLog] = (db.query(m.ConversationLog).filter(
        m.ConversationLog.case_id == case_id).order_by(
            m.ConversationLog.turn_index.asc()).all())

    # 3) offender / victim 식별 (로그 첫 행에서 id를 얻는 방식)
    offender_record: Optional[m.PhishingOffender] = None
    victim_record: Optional[m.Victim] = None
    if logs:
        off_id = getattr(logs[0], "offender_id", None)
        vic_id = getattr(logs[0], "victim_id", None)
        if off_id is not None:
            offender_record = db.get(m.PhishingOffender, off_id)
        if vic_id is not None:
            victim_record = db.get(m.Victim, vic_id)

    # 4) UTC -> KST 변환하여 출력 (스키마가 created_kst를 기본 출력으로 사용)
    KST = timezone(timedelta(hours=9))
    logs_out: List[ConversationLogOut] = [
        ConversationLogOut(
            turn_index=l.turn_index,
            role=("offender" if l.role == "offender" else "victim"),
            content=l.content,
            label=getattr(l, "label", None),
            # 이름 필드가 모델에 없을 수 있으니 안전 처리
            offender_name=getattr(l, "offender_name", None),
            victim_name=getattr(l, "victim_name", None),
            created_kst=(l.created_at.astimezone(KST) if getattr(
                l, "created_at", None) else None),

            # ✅ 새 필드
            use_agent=getattr(l, "use_agent", False),
            run=getattr(l, "run", 1),
            guidance_type=getattr(l, "guidance_type", None),
            guideline=getattr(l, "guideline", None),
        ) for l in logs
    ]

    # 5) offender/victim 직렬화 (네가 준 Out 스키마 그대로)
    offender_out: Optional[OffenderOut] = None
    if offender_record:
        offender_out = OffenderOut.model_validate(offender_record)

    victim_out: Optional[VictimOut] = None
    if victim_record:
        victim_out = VictimOut.model_validate(victim_record)

    return ConversationBundleOut(
        case_id=case.id,
        scenario=case.scenario or {},
        offender=offender_out,
        victim=victim_out,
        logs=logs_out,
    )
