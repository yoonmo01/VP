# app/routers/agent.py
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Response
from sqlalchemy.orm import Session
from uuid import UUID
import asyncio
import uuid
from types import SimpleNamespace
from typing import Dict, Any

from app.db.session import get_db, SessionLocal
# ✅ 파이프라인 한방 함수는 동기 라우트에서만 사용(옵션)
from app.services.agent.orchestrator import (
    run_agent_pipeline_by_case,  # 동기 라우트용(원하면 유지)
    plan_first_run_only,  # ★ 1차 판단(프리뷰) 전용
    run_two_bot_simulation,  # ★ 재시뮬
    postrun_assess_and_save,  # ★ 사후평가 + PersonalizedPrevention 저장
)
from app.services.simulation import run_two_bot_simulation

router = APIRouter(prefix="/agent", tags=["agent"])

# 간단 잡 스토어(인메모리)
AGENT_JOBS: Dict[str, Dict[str, Any]] = {}


def _parse_verbose(request: Request, verbose_q: bool) -> bool:
    """
    쿼리 ?verbose=true 또는 헤더 X-Verbose: true 이면 verbose.
    """
    if verbose_q:
        return True
    xv = request.headers.get("X-Verbose")
    return str(xv).lower() in ("1", "true", "yes", "on")


@router.post("/run/{case_id}", name="AgentRunByCase")
def run_agent_by_case(
        case_id: UUID,
        request: Request,
        db: Session = Depends(get_db),
        verbose: bool = Query(False, description="에이전트 내부 추론(trace) 활성화 여부"),
):
    """
    동기 실행(원샷): 프리뷰를 '미리' 주지는 않음. 바로 최종 결과 리턴.
    """
    try:
        v = _parse_verbose(request, verbose)
        result = run_agent_pipeline_by_case(db, case_id, verbose=v)
        return {**result, "verbose": v}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/run_async/{case_id}", name="AgentRunByCaseAsync")
async def run_agent_async(
        case_id: UUID,
        request: Request,
        response: Response,
        verbose: bool = Query(False),
):
    """
    비동기 실행:
      1) plan_first_run_only → preview 산출 후 곧바로 AGENT_JOBS[job_id].preview 에 저장
      2) run_two_bot_simulation (run=2)
      3) postrun_assess_and_save → PersonalizedPrevention 저장
      4) done
    """
    v = _parse_verbose(request, verbose)
    job_id = str(uuid.uuid4())
    AGENT_JOBS[job_id] = {"status": "running", "verbose": v, "preview": None}

    async def _worker():
        db_local = SessionLocal()
        try:
            # 1) (run=1) 프리뷰
            plan, preview, next_run, offender_id, victim_id = plan_first_run_only(
                db_local, case_id)
            # 👉 프리뷰 즉시 노출
            AGENT_JOBS[job_id] = {
                "status": "running",
                "verbose": v,
                "preview": preview
            }

            # 2) (run=2) 지침 주입 재시뮬
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
                case_scenario={},  # 시나리오 보존
            )
            case_id2, total_turns = run_two_bot_simulation(db_local, args)

            # 3) (run=2) 사후평가 + PersonalizedPrevention 저장
            final = postrun_assess_and_save(
                db_local,
                case_id=case_id2,
                run_no=next_run,
                plan=plan,  # (필요 시 plan 정보 일부 활용)
                offender_id=offender_id,
                victim_id=victim_id,
                verbose=v,
            )
            # 4) 완료
            AGENT_JOBS[job_id] = {
                "status": "done",
                "verbose": v,
                "result": {
                    "case_id": case_id2,
                    "run": next_run,
                    "total_turns": total_turns,
                    "preview": preview,  # 완료 응답에도 포함(옵션)
                    "final":
                    final,  # {"phishing", "outcome", "reasons", "personalized_id"}
                },
            }
        except Exception as e:
            AGENT_JOBS[job_id] = {
                "status": "error",
                "error": str(e),
                "verbose": v
            }
        finally:
            db_local.close()

    asyncio.create_task(_worker())
    response.headers["Location"] = f"/api/agent/job/{job_id}"
    return {"job_id": job_id, "status": "running", "verbose": v}


@router.get("/job/{job_id}", name="AgentJobStatus")
def get_agent_job(job_id: str):
    """
    폴링: running이면 preview가 들어있고, done이면 result에 최종 정보가 들어있음.
    """
    return AGENT_JOBS.get(job_id, {"status": "not_found"})
