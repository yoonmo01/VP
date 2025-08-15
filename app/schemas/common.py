from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class Msg(BaseModel):
    message: str

class CaseRef(BaseModel):
    case_id: UUID

class TimeStamped(BaseModel):
    created_at: datetime
    class Config:
        from_attributes = True