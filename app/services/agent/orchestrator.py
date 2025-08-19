# app/services/agent/orchestrator.py
from __future__ import annotations
from typing import Tuple, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import models as m
from app.services.agent.guideline_repo_db import GuidelineRepoDB
from app.services.agent.llm_agent import SimpleAgent
from app.services.simulation import run_two_bot_simulation
from types import SimpleNamespace


def _next_run(db: Session, case_id: UUID) -> int:
    max_run = (db.query(func.coalesce(
        func.max(m.ConversationLog.run),
        0)).filter(m.ConversationLog.case_id == case_id).scalar()) or 0
    return int(max_run) + 1


def _get_primary_ids_from_log(db: Session,
                              log_id: UUID) -> Tuple[UUID, int, int]:
    base = db.get(m.ConversationLog, log_id)
    if not base:
        raise ValueError("log not found")
    return base.case_id, base.offender_id, base.victim_id


def run_agent_pipeline(db: Session, base_log_id: UUID) -> Dict[str, Any]:
    # 1) 식별
    case_id, offender_id, victim_id = _get_primary_ids_from_log(
        db, base_log_id)

    # 2) 판단/지침 선택
    # 한국어 LLM 우선, 실패 시 폴백
    try:
        agent = LLMAgent(db)
        kind = agent.decide_kind(case_id)  # 'P' or 'A'
    except Exception:
        agent = SimpleAgent(db)
        kind = agent.decide_kind(case_id)

    repo = GuidelineRepoDB(db)
    guideline_text, guideline_title = (repo.pick_preventive()
                                       if kind == "P" else repo.pick_attack())

    # 3) 같은 case로 재시뮬 (run 증가, use_agent=True, 지침 주입)
    run_no = _next_run(db, case_id)
    args = SimpleNamespace(
        offender_id=offender_id,
        victim_id=victim_id,
        include_judgement=True,
        max_rounds=30,  # simulation이 요구하는 필드
        case_scenario={
            "guidance_type": kind,
            "guideline": guideline_text
        },
        case_id_override=case_id,  # ← 새 case 만들지 말고 기존 case 사용
        run_no=run_no,
        use_agent=True,
        guidance_type=kind,
        guideline=guideline_text,
    )
    case_id2, total_turns = run_two_bot_simulation(db, args)

    # 한국어 개인화 생성
    try:
        content = agent.personalize(case_id2, offender_id, victim_id, run_no)
    except Exception:
        content = SimpleAgent(db).personalize(case_id2, offender_id, victim_id,
                                              run_no)

    # 4) 개인화 예방법 생성/저장(에이전트 생각만으로)
    content = agent.personalize(case_id2, offender_id, victim_id, run_no)
    pp = m.PersonalizedPrevention(case_id=case_id2,
                                  offender_id=offender_id,
                                  victim_id=victim_id,
                                  run=run_no,
                                  source_log_id=base_log_id,
                                  content=content,
                                  note="agent-generated",
                                  is_active=True)
    db.add(pp)
    db.flush()

    return {
        "case_id": case_id2,
        "run": run_no,
        "guidance_type": kind,
        "guideline": guideline_text,
        "personalized_id": str(pp.id),
        "total_turns": total_turns,
    }
