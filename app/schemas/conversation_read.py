# app/schemas/conversation_read.py
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from uuid import UUID

# 기존 스키마들 재사용
from app.schemas.conversation import ConversationLogOut
from app.schemas.offender import OffenderOut
from app.schemas.victim import VictimOut

class ConversationBundleOut(BaseModel):
    case_id: UUID
    scenario: Dict[str, Any]
    offender: Optional[OffenderOut] = None
    victim: Optional[VictimOut] = None
    logs: List[ConversationLogOut]
