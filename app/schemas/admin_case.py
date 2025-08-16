from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from app.schemas.conversation import ConversationLogOut

class AdminCaseOut(BaseModel):
    id: UUID
    scenario: dict
    phishing: bool | None
    evidence: str | None
    status: str
    defense_count: int | None
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)

# 케이스 + 전체 로그
class AdminCaseWithLogs(BaseModel):
    case: AdminCaseOut
    logs: list[ConversationLogOut]
