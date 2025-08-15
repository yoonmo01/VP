from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.schemas.conversation import ConversationLogOut

class AdminCaseOut(BaseModel):
    id: UUID
    scenario: dict
    phishing: bool | None
    evidence: str | None

    class Config:
        from_attributes = True


# ✅ 케이스 + 전체 로그
class AdminCaseWithLogs(BaseModel):
    case: AdminCaseOut
    logs: list[ConversationLogOut]