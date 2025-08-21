# app/services/agent/worker.py
from __future__ import annotations
from uuid import UUID
from types import SimpleNamespace

from app.db.session import SessionLocal  # 세션 팩토리
from app.db import models as m
from app.services.jobs import jobs
from app.services.agent.orchestrator import (
    plan_first_run_only,  # ← orchestrator에 helper 제공 (아래 안내)
    run_two_bot_simulation,  # 기존 함수
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def agent_run_worker(job_id: str, case_id: UUID, verbose: bool = False):
    db = SessionLocal()
    try:
        # 1) 1차 판단(프리뷰)
        plan, preview, next_run, offender_id, victim_id = plan_first_run_only(
            db, case_id)
        jobs.update(job_id, status="running", preview=preview)

        # 2) 지침 주입 재시뮬(run=next_run)
        g = plan.get("guidance") or {}
        args = SimpleNamespace(
            offender_id=offender_id,
            victim_id=victim_id,
            include_judgement=True,
            max_rounds=30,
            case_id_override=case_id,
            run_no=next_run,
            use_agent=True,
            guidance_type=g.get("type"),
            guideline=g.get("text") or "",
            case_scenario={},
        )
        case_id2, total_turns = run_two_bot_simulation(db, args)

        # 3) (간단 버전) planner의 personalized_prevention로 저장
        #    — 만약 사후평가(AGENT_POSTRUN_ASSESSOR)를 쓰려면 여기서 assessor 호출/저장으로 교체
        pp_content = plan.get("personalized_prevention") or {}
        ana = dict(pp_content.get("analysis") or {})
        if not ana.get("reasons"):
            ana["reasons"] = plan.get("reasons", [])
        if "outcome" not in ana:
            ana["outcome"] = "success" if plan.get("phishing") else "fail"
        pp_content["analysis"] = ana

        if verbose:
            trace = dict(pp_content.get("trace") or {})
            trace["decision_notes"] = (plan.get("trace")
                                       or {}).get("decision_notes", [])
            pp_content["trace"] = trace

        pp = m.PersonalizedPrevention(
            case_id=case_id2,
            offender_id=offender_id,
            victim_id=victim_id,
            run=next_run,
            source_log_id=None,
            content=pp_content,
            note="agent-planner(ko)",
            is_active=True,
        )
        db.add(pp)
        db.commit()

        # 4) 완료 결과
        result = {
            "case_id": case_id2,
            "run": next_run,
            "total_turns": total_turns,
            "phishing": plan.get("phishing"),
            "outcome": plan.get("outcome"),
            "reasons": plan.get("reasons", []),
        }
        jobs.done(job_id, result=result)

    except Exception as e:
        logger.exception("[AGENT][worker] failed")
        jobs.error(job_id, error=str(e))
    finally:
        db.close()
