# app/services/agent/orchestrator.py
from __future__ import annotations
from typing import Tuple, Optional, Dict, Any, List
from uuid import UUID
from types import SimpleNamespace
import math, json
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func, asc

from app.db import models as m
from app.services.conversations_read import fetch_logs_by_case
from app.services.simulation import run_two_bot_simulation
from app.services.llm_providers import agent_chat
from app.services.prompts_agent import (
    AGENT_PLANNER_PROMPT,
    AGENT_POSTRUN_ASSESSOR_PROMPT,  # ✅ 추가
)
from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------- 유틸 ----------
def _next_run(db: Session, case_id: UUID) -> int:
    max_run = (db.query(func.coalesce(
        func.max(m.ConversationLog.run),
        0)).filter(m.ConversationLog.case_id == case_id).scalar()) or 0
    return int(max_run) + 1


def _logs_json_for_run(db: Session, case_id: UUID, run_no: int) -> str:
    rows = (db.query(m.ConversationLog).filter(
        m.ConversationLog.case_id == case_id,
        m.ConversationLog.run == run_no).order_by(
            m.ConversationLog.turn_index.asc(),
            m.ConversationLog.created_at.asc()).all())
    items = [{
        "turn": r.turn_index,
        "role": r.role,
        "text": r.content
    } for r in rows]
    return json.dumps(items, ensure_ascii=False)


def _logs_json_for_run1(db: Session, case_id: UUID) -> str:
    return _logs_json_for_run(db, case_id, 1)


def _scenario_json(db: Session, case_id: UUID) -> str:
    case = db.get(m.AdminCase, case_id)
    return json.dumps(case.scenario or {}, ensure_ascii=False)


def _append_methods_used(db: Session, case_id: UUID, run_no: int,
                         append_obj: Dict[str, Any]) -> None:
    case = db.get(m.AdminCase, case_id)
    sc = dict(case.scenario or {})
    used: List[Dict[str, Any]] = list(sc.get("methods_used", []))
    if append_obj:
        used.append({"run": run_no, **append_obj})
    sc["methods_used"] = used
    case.scenario = sc
    db.add(case)
    db.flush()


def _update_case_analysis(db: Session, case_id: UUID, plan: Dict[str,
                                                                 Any]) -> None:
    """run=1 사전판단을 케이스에 남김(원 시나리오 보존)."""
    case = db.get(m.AdminCase, case_id)
    sc = dict(case.scenario or {})
    analysis = {
        "outcome": plan.get("outcome"),
        "phishing": bool(plan.get("phishing")),
        "reasons": (plan.get("reasons") or [])[:5],
        "guidance": {
            "type": (plan.get("guidance") or {}).get("type"),
            "category": (plan.get("guidance") or {}).get("category"),
            "title": (plan.get("guidance") or {}).get("title"),
        },
    }
    sc["last_analysis"] = analysis
    case.scenario = sc
    case.phishing = bool(plan.get("phishing"))
    case.evidence = " / ".join(analysis["reasons"])[:1000] or case.evidence
    db.add(case)
    db.flush()


def _get_primary_ids_from_case(db: Session,
                               case_id: UUID) -> Tuple[int, int, UUID]:
    row = (db.query(m.ConversationLog).filter(
        m.ConversationLog.case_id == case_id).order_by(
            asc(m.ConversationLog.run),
            asc(m.ConversationLog.turn_index)).first())
    if not row:
        raise ValueError("해당 case_id에 로그가 없어 에이전트를 실행할 수 없습니다.")
    return row.offender_id, row.victim_id, row.id


def _build_preview_from_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    g = plan.get("guidance") or {}
    return {
        "phishing": bool(plan.get("phishing")),
        "outcome": plan.get("outcome"),
        "reasons": (plan.get("reasons") or [])[:5],
        "guidance": {
            "type": g.get("type"),
            "category": g.get("category"),
            "title": g.get("title"),
        },
        "trace": {
            "decision_notes": (plan.get("trace")
                               or {}).get("decision_notes", [])
        },
    }


def plan_first_run_only(
        db: Session,
        case_id: UUID) -> Tuple[Dict[str, Any], Dict[str, Any], int, int, int]:
    """
    run=1 로그만 보고 Planner를 실행해 plan(JSON)과 preview를 만든다.
    return: (plan, preview, next_run, offender_id, victim_id)
    """
    # 참여자
    offender_id, victim_id, _ = _get_primary_ids_from_case(db, case_id)

    # Planner 실행
    chain = AGENT_PLANNER_PROMPT | agent_chat()
    resp = chain.invoke({
        "scenario_json": _scenario_json(db, case_id),
        "logs_json": _logs_json_for_run1(db, case_id),
    })
    raw = getattr(resp, "content", str(resp)).strip()
    plan = json.loads(raw)

    # next_run 산출 및 case 분석 저장(마지막 판정 근거)
    rows = fetch_logs_by_case(db, case_id)
    existing_runs = [int(r.get("run") or 1) for r in rows]
    next_run = (max(existing_runs) + 1) if existing_runs else 2

    _append_methods_used(db, case_id, next_run,
                         plan.get("methods_used_append") or {})
    _update_case_analysis(db, case_id, plan)  # scenario.last_analysis 업데이트

    preview = _build_preview_from_plan(plan)
    return plan, preview, next_run, offender_id, victim_id


def postrun_assess_and_save(
    db: Session,
    *,
    case_id: UUID,
    run_no: int,
    plan: Dict[str, Any],
    offender_id: int,
    victim_id: int,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    run=2 로그만 보고 사후평가(AGENT_POSTRUN_ASSESSOR) → PersonalizedPrevention 저장
    """
    # 1) assessor 호출
    chain = AGENT_POSTRUN_ASSESSOR_PROMPT | agent_chat()
    resp = chain.invoke({
        "scenario_json": _scenario_json(db, case_id),
        "logs_json": _logs_json_for_run(db, case_id, run_no),
    })
    raw = getattr(resp, "content", str(resp)).strip()
    try:
        post = json.loads(raw)
    except Exception as e:
        logger.error(f"[AGENT][postrun] JSON 파싱 실패: {e} raw={raw[:300]}")
        post = {
            "phishing": bool(plan.get("phishing")),
            "outcome": plan.get("outcome"),
            "reasons": plan.get("reasons", []),
            "personalized_prevention": {
                "summary": "사후 평가 생성 실패로 기본 요약을 사용합니다.",
                "analysis": {
                    "outcome": "success" if plan.get("phishing") else "fail",
                    "reasons": plan.get("reasons", []),
                    "risk_level": "medium",
                },
                "steps": [],
                "tips": [],
            },
            "trace": {
                "decision_notes": (plan.get("trace")
                                   or {}).get("decision_notes", [])
            },
        }

    # 2) PP 저장
    pp_content = post.get("personalized_prevention") or {}
    if verbose:
        pp_content["trace"] = {
            "decision_notes": (post.get("trace")
                               or {}).get("decision_notes", [])
        }

    pp = m.PersonalizedPrevention(
        case_id=case_id,
        offender_id=offender_id,
        victim_id=victim_id,
        run=run_no,
        source_log_id=None,
        content=pp_content,
        note="agent-postrun(ko)",
        is_active=True,
    )
    db.add(pp)
    db.commit()
    db.refresh(pp)

    return {
        "phishing": post.get("phishing"),
        "outcome": post.get("outcome"),
        "reasons": post.get("reasons", []),
        "personalized_id": str(pp.id),
    }


# ---------- (선택) 간단 신호 분석: why 요약 ----------
_KEYWORDS_ATTACK = [
    "안전계좌", "원격", "앱 설치", "인증번호", "OTP", "보안카드", "검찰", "금감원", "대환대출"
]
_KEYWORDS_DEFENSE = ["신고", "차단", "대표번호", "지점 방문", "사기", "보이스피싱", "경찰"]


def _extract_signals(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    sigs = []
    atk, defn = 0, 0
    for r in rows:
        text = (r.get("text") or "").lower()
        speaker = r.get("speaker")
        turn = r.get("turn_index")
        for kw in _KEYWORDS_ATTACK:
            if kw.lower() in text:
                sigs.append({
                    "turn": turn,
                    "speaker": speaker,
                    "match": kw,
                    "kind": "keyword"
                })
                atk += 1
        for kw in _KEYWORDS_DEFENSE:
            if kw.lower() in text:
                sigs.append({
                    "turn": turn,
                    "speaker": speaker,
                    "match": kw,
                    "kind": "defense"
                })
                defn += 1
    import math
    risk = 1 / (1 + math.exp(-(atk - defn)))
    return {
        "signals": sigs,
        "risk_score": float(risk),
        "atk_hits": atk,
        "def_hits": defn
    }


def _why_summary_for_case(
        db: Session,
        case_id: UUID,
        decision: str,
        guidance_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rows = fetch_logs_by_case(db, case_id)
    feats = _extract_signals(rows)
    conf = min(0.95,
               0.5 + 0.5 * feats["risk_score"] + 0.05 * feats["atk_hits"])
    return {
        "decision": decision,
        "signals": feats["signals"],
        "confidence": round(conf, 2),
        "notes": "공격/방어 키워드와 피해자 반응 기반 간이 산출",
        "used_guidance": guidance_snapshot or None,
    }


# ---------- 메인 파이프라인 ----------
def run_agent_pipeline_by_case(db: Session,
                               case_id: UUID,
                               verbose: bool = False) -> Dict[str, Any]:
    """
    흐름:
    1) (run=1) Planner로 사전판단(JSON) 생성 → preview로 즉시 사용
    2) methods_used 누적 + case.last_analysis 갱신
    3) (run=2) 같은 케이스로 지침 주입 재시뮬
    4) (run=2) Post-run Assessor로 최종 개인화 예방법 생성 → DB 저장
    5) preview와 final 결과를 함께 반환
    """
    # 0) 기본 식별
    offender_id, victim_id, base_log_id = _get_primary_ids_from_case(
        db, case_id)

    # 1) Planner 호출 (run=1만 입력)
    planner_chain = AGENT_PLANNER_PROMPT | agent_chat()
    planner_resp = planner_chain.invoke({
        "scenario_json":
        _scenario_json(db, case_id),
        "logs_json":
        _logs_json_for_run1(db, case_id),
    })
    planner_raw = getattr(planner_resp, "content", str(planner_resp)).strip()
    try:
        plan = json.loads(planner_raw)
    except Exception as e:
        logger.error(
            f"[AGENT][planner] JSON 파싱 실패: {e} raw={planner_raw[:300]}")
        raise

    preview = _build_preview_from_plan(plan)

    # 2) run 계산 + methods_used 축적 + 케이스 분석 저장(사전판단 근거)
    rows = fetch_logs_by_case(db, case_id)
    existing_runs = [int(r.get("run") or 1) for r in rows]
    next_run = (max(existing_runs) + 1) if existing_runs else 2
    _append_methods_used(db, case_id, next_run,
                         plan.get("methods_used_append") or {})
    _update_case_analysis(db, case_id, plan)

    # 3) 지침 주입 재시뮬(run=2)
    g = plan.get("guidance") or {}
    sim_args = SimpleNamespace(
        offender_id=offender_id,
        victim_id=victim_id,
        include_judgement=True,
        max_rounds=30,
        case_id_override=case_id,  # 같은 케이스에 run 누적
        run_no=next_run,
        use_agent=True,
        guidance_type=g.get("type"),
        guideline=g.get("text") or "",
        case_scenario={},  # 원 시나리오 보존
    )
    case_id2, total_turns = run_two_bot_simulation(db, sim_args)

    # 4) Post-run Assessor 호출(run=2만 입력) → PersonalizedPrevention 저장
    assessor_chain = AGENT_POSTRUN_ASSESSOR_PROMPT | agent_chat()
    assessor_resp = assessor_chain.invoke({
        "scenario_json":
        _scenario_json(db, case_id2),
        "logs_json":
        _logs_json_for_run(db, case_id2, next_run),
    })
    assessor_raw = getattr(assessor_resp, "content",
                           str(assessor_resp)).strip()
    try:
        post = json.loads(assessor_raw)
    except Exception as e:
        logger.error(
            f"[AGENT][postrun] JSON 파싱 실패: {e} raw={assessor_raw[:300]}")
        # 실패 시, planner의 최소 정보로라도 저장
        post = {
            "phishing": bool(plan.get("phishing")),
            "outcome": plan.get("outcome"),
            "reasons": plan.get("reasons", []),
            "personalized_prevention": {
                "summary": "사후 평가 생성 실패로 기본 요약을 사용합니다.",
                "analysis": {
                    "outcome": "success" if plan.get("phishing") else "fail",
                    "reasons": plan.get("reasons", []),
                    "risk_level": "medium",
                },
                "steps": [],
                "tips": [],
            },
            "trace": {
                "decision_notes": (plan.get("trace")
                                   or {}).get("decision_notes", [])
            },
        }

    pp_content = post.get("personalized_prevention") or {}
    # verbose면 안전한 근거(trace.decision_notes) 포함
    if verbose:
        trace_notes = (post.get("trace") or {}).get("decision_notes", [])
        pp_content["trace"] = {"decision_notes": trace_notes}

    # (선택) why 보강: 키워드 신호 요약 + 사용 지침 스냅샷
    why = _why_summary_for_case(db,
                                case_id2,
                                decision="preventive" if
                                (g.get("type") == "P") else "attack_guidance",
                                guidance_snapshot={
                                    "type":
                                    g.get("type"),
                                    "category":
                                    g.get("category"),
                                    "title":
                                    g.get("title"),
                                    "guideline_excerpt":
                                    (plan.get("methods_used_append")
                                     or {}).get("guideline_excerpt")
                                })
    pp_content["why"] = why

    pp = m.PersonalizedPrevention(
        case_id=case_id2,
        offender_id=offender_id,
        victim_id=victim_id,
        run=next_run,
        source_log_id=base_log_id,
        content=pp_content,
        note="agent-postrun(ko)",
        is_active=True,
    )
    db.add(pp)
    db.commit()
    db.refresh(pp)

    # 5) 프론트에 줄 응답(사전판단 미리보기 + 최종결과 요약)
    return {
        "case_id": case_id2,
        "run": next_run,
        "total_turns": total_turns,
        "verbose": verbose,

        # 사전판단(바로 화면에 보여줄 것)
        "preview":
        preview,  # { phishing, outcome, reasons, guidance{...}, trace{decision_notes[]} }

        # 지침 요약(스냅샷)
        "guidance_type": g.get("type"),
        "guidance_title": g.get("title"),
        "guidance_category": g.get("category"),
        "guideline": g.get("text"),

        # 사후평가(최종)
        "final": {
            "phishing": post.get("phishing"),
            "outcome": post.get("outcome"),
            "reasons": post.get("reasons", []),
            "personalized_id": str(pp.id),
        },
    }
