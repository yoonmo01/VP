# app/services/agent_orchestrator.py
from __future__ import annotations
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from uuid import UUID

from app.db import models as m
from app.services.admin_summary import summarize_case
from app.services.simulation import run_two_bot_simulation  # 기존 것 재사용
from types import SimpleNamespace


# 0) case 내 다음 run 번호
def next_run_no(db: Session, case_id: UUID) -> int:
    q = db.query(func.coalesce(func.max(m.ConversationLog.run),
                               0)).filter(m.ConversationLog.case_id == case_id)
    return int(q.scalar() or 0) + 1


# 1) 공격/예방 어떤 지침을 쓸지 자동 판단
def decide_guidance_kind(db: Session, case_id: UUID) -> str:
    """
    summarize_case(db, case_id) -> {"phishing": bool, ...}
    기본 로직:
      - 이미 당했다(phishing=True): 예방(P)으로 방어 강화
      - 아직 아니다(False): 공격(A)로 도전 강도 상향(레드팀)
    """
    try:
        res = summarize_case(db, case_id) or {}
        phishing = res.get("phishing")
    except Exception:
        phishing = None

    if phishing is True:
        return "P"
    if phishing is False:
        return "A"
    # 판단 실패 시 기본은 예방(P)
    return "P"


# 2) 지침 하나 고르기 (카테고리 매칭 등은 필요시 보강)
def pick_guideline(db: Session, kind: str) -> Tuple[str, str]:
    """
    kind: 'P'|'A'
    return: (guideline_text, title)
    """
    if kind == "P":
        row = (db.query(
            m.Preventive).filter(m.Preventive.is_active == True).order_by(
                m.Preventive.id.asc()).first())
        if not row:
            raise RuntimeError("no preventive guideline found")
        return (row.body or {}).get("summary") or row.title, row.title
    else:
        row = (db.query(m.Attack).filter(m.Attack.is_active == True).order_by(
            m.Attack.id.asc()).first())
        if not row:
            raise RuntimeError("no attack guideline found")
        # 공격은 body.opening/script 등을 한 묶음으로 줄 수도 있음
        body = row.body or {}
        text = body.get("opening") or body.get("summary") or row.title
        return text, row.title


# 3) 같은 case로 재시뮬 돌리기 (지침 주입)
def rerun_with_guidance(
    db: Session,
    case_id: UUID,
    offender_id: int,
    victim_id: int,
    guidance_type: str,  # 'P' or 'A'
    guideline_text: str,
) -> Tuple[UUID, int, int]:
    """
    returns: (case_id, total_turns, run_no)
    내부적으로 run_no=next_run_no, use_agent=True로 표기.
    run_two_bot_simulation 에서 'guideline'을 프롬프트에 반영하도록 약속한다.
    """
    run_no = next_run_no(db, case_id)

    # 기존 run_two_bot_simulation에 'case_id_override', 'guidance' 파라미터를 추가하는 걸 추천.
    # (없다면: case는 유지하고 로그 INSERT 시 run/use_agent/guideline을 함께 적재하는 분기가 필요)
    args = SimpleNamespace(
        offender_id=offender_id,
        victim_id=victim_id,
        include_judgement=True,
        max_turns=30,
        agent_mode="admin",  # or "police", 네 정책에 맞춰
        case_scenario={
            "guidance_type": guidance_type,
            "guideline": guideline_text
        },
        # ↓ 신규 제어 파라미터 (run_two_bot_simulation에 반영 필요)
        case_id_override=case_id,
        run_no=run_no,
        use_agent=True,
        guidance_type=guidance_type,
        guideline=guideline_text,
    )

    # run_two_bot_simulation이 동기로 (case_id, total_turns)를 반환하는 기존 시그니처라면,
    # 위 확장 필드를 내부에서 읽어 runtime에 반영하도록만 수정하면 됨.
    case_id2, total_turns = run_two_bot_simulation(db, args)
    return case_id2, total_turns, run_no


# 4) 맞춤형 예방법 저장 (에이전트 "생각만으로")
def save_personalized_prevention(
    db: Session,
    case_id: UUID,
    offender_id: int,
    victim_id: int,
    run_no: int,
    source_log_id: Optional[UUID] = None,
) -> UUID:
    """
    실제 생성은 LLM으로 하겠지만, 여기서는 저장만 캡슐화.
    content 스키마는 프로젝트 합의에 맞춰 자유롭게 확장.
    """
    # 간단 템플릿(예시) — 실제로는 에이전트가 case/로그를 읽고 생성한 dict를 받도록 변경
    content = {
        "summary":
        "피해자 특성 기반 맞춤형 예방 가이드",
        "steps": [
            "송금·인증요청은 반드시 2차 채널로 재확인", "링크/QR 클릭 금지, 앱 설치 요구 차단",
            "의심 시 112 또는 1332 즉시 신고"
        ]
    }
    obj = m.PersonalizedPrevention(
        case_id=case_id,
        offender_id=offender_id,
        victim_id=victim_id,
        run=run_no,
        source_log_id=source_log_id,
        content=content,
        note="agent-generated",
        is_active=True,
    )
    db.add(obj)
    db.flush()
    return obj.id
