# app/services/simulation.py
from __future__ import annotations

from typing import Dict, Any, List, Tuple
from uuid import UUID
import re

from sqlalchemy.orm import Session

from app.db import models as m
from app.core.config import settings

from langchain_core.messages import HumanMessage, AIMessage
from app.services.llm_providers import attacker_chat, victim_chat
from app.services.admin_summary import summarize_case

from app.services.prompts import (
    ATTACKER_PROMPT,
    VICTIM_PROMPT,
    render_attacker_from_offender,  # (옵션) 필요 시 사용
)
from app.schemas.conversation import ConversationRunRequest

MAX_TURNS_PER_ROUND = 2
MAX_OFFENDER_TURNS = settings.MAX_OFFENDER_TURNS
MAX_VICTIM_TURNS = settings.MAX_VICTIM_TURNS

# 종료 트리거(느슨한 매칭)
END_TRIGGERS = [r"마무리하겠습니다"]
VICTIM_END_LINE = "시뮬레이션을 종료합니다."

def _assert_turn_role(turn_index: int, role: str):
    expected = "offender" if turn_index % 2 == 0 else "victim"
    if role != expected:
        raise ValueError(f"Turn {turn_index} must be {expected}, got {role}")

def _save_turn(
    db: Session,
    case_id: UUID,
    offender_id: int,
    victim_id: int,
    turn_index: int,
    role: str,
    content: str,
    label: str | None = None,
):
    _assert_turn_role(turn_index, role)
    log = m.ConversationLog(
        case_id=case_id,
        offender_id=offender_id,
        victim_id=victim_id,
        turn_index=turn_index,
        role=role,
        content=content,
        label=label,
    )
    db.add(log)
    db.commit()

def _hit_end(text: str) -> bool:
    norm = text.strip()
    return any(re.search(pat, norm) for pat in END_TRIGGERS)

def run_two_bot_simulation(db: Session, req: ConversationRunRequest) -> Tuple[UUID, int]:
    # 케이스 생성
    case = m.AdminCase(scenario=req.case_scenario or {})
    db.add(case)
    db.commit()
    db.refresh(case)

    offender = db.get(m.PhishingOffender, req.offender_id)
    victim = db.get(m.Victim, req.victim_id)
    if offender is None:
        raise ValueError(f"Offender {req.offender_id} not found")
    if victim is None:
        raise ValueError(f"Victim {req.victim_id} not found")

    # LLM 준비
    attacker_llm = attacker_chat()
    victim_llm = victim_chat()
    attacker_chain = ATTACKER_PROMPT | attacker_llm
    victim_chain = VICTIM_PROMPT | victim_llm

    history_attacker: list = []
    history_victim: list = []
    turn_index = 0
    attacks = replies = 0

    # ✅ Step-Lock: 시나리오 단계와 커서 준비
    scenario = req.case_scenario or {}
    steps: List[str] = (scenario.get("steps")
                    or (scenario.get("profile") or {}).get("steps")
                    or (offender.profile or {}).get("steps")
                    or [])
    
    print("[DEBUG] steps_len:", len(steps), "step0:", (steps[0] if steps else None))
    if not steps:
        raise ValueError("시나리오 steps가 비어 있습니다. case_scenario.steps 또는 profile.steps를 확인하세요.")
    current_step_idx = 0

    # ✅ 첫 턴은 빈 문자열로 시작(상투 시작 방지)
    last_victim_text = ""
    last_offender_text = ""

    print("[DEBUG] steps_len:", len(steps), "step0:", (steps[0] if steps else None))
    for _ in range(req.max_rounds):
        # ---- 공격자 턴 ----
        if attacks >= MAX_OFFENDER_TURNS:
            break

        # 모든 단계 소진 시 종료
        if current_step_idx >= len(steps):
            break

        attacker_msg = attacker_chain.invoke({
            "history": history_attacker,
            "last_victim": last_victim_text,
            # ✅ 핵심: 현재 단계 한 줄만 전달하여 그 단계에 해당하는 말만 하게 함
            "current_step": steps[current_step_idx],
        })
        attacker_text = getattr(attacker_msg, "content", str(attacker_msg)).strip()

        _save_turn(db, case.id, offender.id, victim.id, turn_index, "offender", attacker_text)
        history_attacker.append(AIMessage(attacker_text))
        history_victim.append(HumanMessage(attacker_text))
        last_offender_text = attacker_text
        turn_index += 1
        attacks += 1

        # 다음 공격자 턴에는 다음 단계로 전진
        current_step_idx += 1

        # 공격자 종료 선언 감지 시: 피해자 종료 한 줄 후 즉시 종료
        if _hit_end(attacker_text):
            if replies < MAX_VICTIM_TURNS:
                victim_text = VICTIM_END_LINE
                _save_turn(db, case.id, offender.id, victim.id, turn_index, "victim", victim_text)
                history_victim.append(AIMessage(victim_text))
                history_attacker.append(HumanMessage(victim_text))
                last_victim_text = victim_text
                turn_index += 1
                replies += 1
            break

        # ---- 피해자 턴 ----
        if replies >= MAX_VICTIM_TURNS:
            break

        victim_msg = victim_chain.invoke({
            "history": history_victim,
            "last_offender": last_offender_text,
            "meta": getattr(req, "meta", None) or getattr(victim, "meta", "정보 없음"),
            "knowledge": getattr(req, "knowledge", None) or getattr(victim, "knowledge", "정보 없음"),
            "traits": getattr(req, "traits", None) or getattr(victim, "traits", "정보 없음"),
        })
        victim_text = getattr(victim_msg, "content", str(victim_msg)).strip()

        _save_turn(db, case.id, offender.id, victim.id, turn_index, "victim", victim_text)
        history_victim.append(AIMessage(victim_text))
        history_attacker.append(HumanMessage(victim_text))
        last_victim_text = victim_text
        turn_index += 1
        replies += 1

    # 관리자 요약/판정 실행
    summarize_case(db, case.id)
    return case.id, turn_index

def advance_one_tick(
    db: Session,
    case_id: UUID,
    inject: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    rows = (
        db.query(m.ConversationLog)
        .filter(m.ConversationLog.case_id == case_id)
        .order_by(m.ConversationLog.turn_index.asc())
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows[-4:]:
        out.append({"role": r.role, "content": r.content, "label": r.label})
    return out
