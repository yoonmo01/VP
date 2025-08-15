from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.utils.deps import get_db
from app.schemas.conversation import ConversationRunRequest, ConversationRunResult
from app.services.simulation import run_two_bot_simulation
from app.services.admin_summary import summarize_case  # ✅ 교체

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.post("/run", response_model=ConversationRunResult)
def run_conversation(payload: ConversationRunRequest, db: Session = Depends(get_db)):
    case_id, total_turns = run_two_bot_simulation(db, payload)
    result = summarize_case(db, case_id)
    return {
        "case_id": case_id,
        "total_turns": total_turns,
        "phishing": result["phishing"],
        "evidence": result["evidence"],
    }
