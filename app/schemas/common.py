#schemas/common.py
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class Msg(BaseModel):
    message: str

class CaseRef(BaseModel):
    case_id: UUID

class TimeStamped(BaseModel):
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
