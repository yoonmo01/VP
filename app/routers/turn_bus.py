# app/routers/turn_bus.py
from __future__ import annotations
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Literal
import os, time

from app.services.agent.turn_bus import push
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/turn-bus", tags=["turn-bus"])

SHARED = os.getenv("VOICEPHISH_TURNBUS_TOKEN", "")

class TurnEvent(BaseModel):
    stream_id: str
    type: Literal["new_message","judgement","guidance","heartbeat","terminal","log"] = "new_message"
    case_id: Optional[str] = None
    round: Optional[int] = None
    turn_index: Optional[int] = None
    role: Optional[str] = None
    content: Optional[str] = None
    created_kst: Optional[str] = None
    # 유연성 확보용
    extra: Optional[dict] = None

@router.post("/emit")
async def emit_turn_event(
    body: TurnEvent,
    x_voicephish_token: str = Header(default=""),
):
    if not SHARED or x_voicephish_token != SHARED:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    ok = push(body.stream_id, body.model_dump())
    if not ok:
        # 스트림이 아직 안 켜졌거나 이미 종료
        logger.info("[turn-bus] no sink for stream=%s (drop)", body.stream_id)
        return {"ok": False, "dropped": True}

    return {"ok": True, "ts": int(time.time())}
