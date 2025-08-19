# app/routers/agent.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, Dict, Any, List
from app.db.session import get_db
from app.services.agent.orchestrator import run_agent_pipeline

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/{log_id}", name="AgentRun")
def run_agent(log_id: UUID, db: Session = Depends(get_db)):
    try:
        result = run_agent_pipeline(db, log_id)
        db.commit()
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
