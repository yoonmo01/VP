from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from app.utils.deps import get_db
from app.db import models as m
from app.schemas.admin_case import AdminCaseOut, AdminCaseWithLogs
from app.schemas.conversation import ConversationLogOut
from datetime import timezone, timedelta
router = APIRouter(prefix="/admin-cases", tags=["admin"])

@router.get("/{case_id}", response_model=AdminCaseOut)
def get_case(case_id: UUID, db: Session = Depends(get_db)):
    return db.get(m.AdminCase, case_id)


# ✅ case_id 하나로 전체 로그까지
@router.get("/{case_id}/full", response_model=AdminCaseWithLogs)
def get_case_with_logs(case_id: UUID, db: Session = Depends(get_db)):
    case = db.get(m.AdminCase, case_id)
    if not case:
        return {"case": None, "logs": []}
    logs = (
        db.query(m.ConversationLog)
        .filter(m.ConversationLog.case_id == case_id)
        .order_by(m.ConversationLog.turn_index.asc())
        .all()
    )
    return {
        "case": case,
        "logs": [
            ConversationLogOut(
                turn=l.turn_index, role=l.role, content=l.content, created_at=l.created_at
            ) for l in logs
        ]
    }