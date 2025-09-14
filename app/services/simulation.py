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

# 기본 템플릿
from app.services.prompts import (
    ATTACKER_PROMPT,
    VICTIM_PROMPT,
)
from app.schemas.conversation import ConversationRunRequest

# ─────────────────────────────────────────────────────────
# 발화 하드캡(안전장치). 실제 "턴(티키타카)" 제한은 max_turns로 제어한다.
# 한 턴 = 공격자 1발화 + 피해자 1발화.
# ─────────────────────────────────────────────────────────
MAX_OFFENDER_TURNS = settings.MAX_OFFENDER_TURNS
MAX_VICTIM_TURNS = settings.MAX_VICTIM_TURNS

# 종료 트리거(느슨한 매칭): 공격자가 말하면 종료
END_TRIGGERS = [r"마무리하겠습니다"]
VICTIM_END_LINE = "시뮬레이션을 종료합니다."


def _assert_turn_role(turn_index: int, role: str):
    """
    DB에 저장되는 turn_index는 '반쪽 턴(발화 1회)' 인덱스.
    짝수 = offender, 홀수 = victim 이 되도록 강제.
    """
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
    *,
    # 메타 표식(옵션)
    use_agent: bool = False,
    run: int = 1,
    guidance_type: str | None = None,
    guideline: str | None = None,
):
    """ConversationLog에 한 발화를 저장(반쪽 턴 단위)."""
    _assert_turn_role(turn_index, role)
    log = m.ConversationLog(
        case_id=case_id,
        offender_id=offender_id,
        victim_id=victim_id,
        turn_index=turn_index,
        role=role,
        content=content,
        label=label,
        use_agent=use_agent,
        run=run,
        guidance_type=guidance_type,
        guideline=guideline,
    )
    db.add(log)
    db.commit()


def _hit_end(text: str) -> bool:
    """공격자의 종료 문구 감지(느슨 매칭)."""
    norm = text.strip()
    return any(re.search(pat, norm) for pat in END_TRIGGERS)


# ─────────────────────────────────────────────────────────
# ⬇️ 추가: 템플릿 리졸버 (템플릿 ID → 실제 ChatPromptTemplate)
#    필요 시 prompt.py에 다른 버전을 추가해도 여기 맵만 확장하면 됨.
# ─────────────────────────────────────────────────────────
def _resolve_attacker_prompt(template_id: str | None):
    # 예: "ATTACKER_PROMPT_V1" 같은 문자열이 들어오면 분기
    # 현재는 단일 버전만 있으므로 기본값으로 매핑
    return ATTACKER_PROMPT

def _resolve_victim_prompt(template_id: str | None):
    return VICTIM_PROMPT


def run_two_bot_simulation(db: Session, req: ConversationRunRequest) -> Tuple[UUID, int]:
    """
    시뮬레이터 메인.
    - 기본: 새 AdminCase 생성 (case_id_override가 있으면 이어쓰기)
    - turn_index는 '반쪽 턴(발화 1회)' 기준으로 +1
    - 반환 total_turns는 '진짜 턴(티키타카)' 개수 (공1+피1=1)
    - max_turns(기본 15): 턴(티키타카) 개수 제한
    - MAX_OFFENDER_TURNS/MAX_VICTIM_TURNS는 한쪽 발화 하드캡(안전장치)
    """
    # ── 케이스 준비 ─────────────────────────────────────
    case_id_override: UUID | None = getattr(req, "case_id_override", None)
    if case_id_override:
        case = db.get(m.AdminCase, case_id_override)
        if not case:
            raise ValueError(f"AdminCase {case_id_override} not found")
        scenario = case.scenario or {}
        scenario.update(getattr(req, "case_scenario", {}) or {})
        case.scenario = scenario
        db.add(case)
        db.commit()
        db.refresh(case)
    else:
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

    # ── 메타 표식 ──────────────────────────────────────
    run_no: int = int(getattr(req, "run_no", 1))
    use_agent: bool = bool(getattr(req, "use_agent", False))

    # ⬇️ guidance 주입 (우선순위: req.guidance > req.guideline > case_scenario.guideline)
    cs: Dict[str, Any] = getattr(req, "case_scenario", {}) or {}
    guidance_dict: Dict[str, Any] | None = getattr(req, "guidance", None)
    guidance_text: str | None = None
    guidance_type: str | None = None
    if isinstance(guidance_dict, dict):
        guidance_text = guidance_dict.get("text") or None
        guidance_type = guidance_dict.get("type") or None
    if not guidance_text:
        guidance_text = getattr(req, "guideline", None) or cs.get("guideline")
    if not guidance_type:
        guidance_type = getattr(req, "guidance_type", None) or cs.get("guidance_type")

    # ── LLM 체인 ──────────────────────────────────────
    # ⬇️ 템플릿 선택(오케스트레이터/툴에서 전달한 templates를 우선)
    templates: Dict[str, Any] = getattr(req, "templates", {}) or {}
    attacker_tpl_id = templates.get("attacker")
    victim_tpl_id = templates.get("victim")

    attacker_prompt = _resolve_attacker_prompt(attacker_tpl_id)
    victim_prompt   = _resolve_victim_prompt(victim_tpl_id)

    attacker_llm = attacker_chat()
    victim_llm = victim_chat()
    attacker_chain = attacker_prompt | attacker_llm
    victim_chain = victim_prompt | victim_llm

    # ⬇️ 피해자 프로필 오버라이드(요청의 victim_profile이 있으면 DB값보다 우선)
    victim_profile: Dict[str, Any] = getattr(req, "victim_profile", {}) or {}
    meta_override      = victim_profile.get("meta")
    knowledge_override = victim_profile.get("knowledge")
    traits_override    = victim_profile.get("traits")

    history_attacker: list = []
    history_victim: list = []
    turn_index = 0                    # 반쪽 턴 인덱스(발화마다 +1)
    attacks = replies = 0             # 반쪽 턴 카운트(각 역할 발화 수)
    turns_executed = 0                # 진짜 턴(티키타카) 카운트

    # ── Step-Lock: 단계와 커서 ─────────────────────────
    scenario_all = (req.case_scenario or {}) if not case_id_override else (case.scenario or {})
    steps: List[str] = (
        (scenario_all.get("steps") or [])
        or ((scenario_all.get("profile") or {}).get("steps") or [])
        or ((offender.profile or {}).get("steps") or [])
    )
    if not steps:
        raise ValueError("시나리오 steps가 비어 있습니다. case_scenario.steps 또는 profile.steps를 확인하세요.")

    current_step_idx = 0

    # 첫 턴 전 상태
    last_victim_text = ""
    last_offender_text = ""

    # ── max_turns(티키타카 횟수) 보정 ──────────────────
    max_turns = getattr(req, "max_turns", None) or 15

    for _ in range(max_turns):
        # ---- 공격자 발화(반쪽 턴) ----
        if attacks >= MAX_OFFENDER_TURNS:
            break

        current_step_str = steps[current_step_idx] if current_step_idx < len(steps) else ""

        attacker_msg = attacker_chain.invoke({
            "history":       history_attacker,
            "last_victim":   last_victim_text,
            "current_step":  current_step_str,
            "guidance":      guidance_text or "",
            "guidance_type": guidance_type or "",
        })
        attacker_text = getattr(attacker_msg, "content", str(attacker_msg)).strip()

        _save_turn(
            db,
            case.id,
            offender.id,
            victim.id,
            turn_index,
            "offender",
            attacker_text,
            label=None,
            use_agent=use_agent,
            run=run_no,
            guidance_type=guidance_type,
            guideline=guidance_text,
        )
        history_attacker.append(AIMessage(attacker_text))
        history_victim.append(HumanMessage(attacker_text))
        last_offender_text = attacker_text
        turn_index += 1
        attacks += 1

        # 실제 단계였을 때만 커서 전진
        if current_step_idx < len(steps):
            current_step_idx += 1

        # 공격자 종료 선언 시: 피해자 종료 한 줄 후 종료
        if _hit_end(attacker_text):
            if replies < MAX_VICTIM_TURNS:
                victim_text = VICTIM_END_LINE
                _save_turn(
                    db,
                    case.id,
                    offender.id,
                    victim.id,
                    turn_index,
                    "victim",
                    victim_text,
                    label=None,
                    use_agent=use_agent,
                    run=run_no,
                    guidance_type=guidance_type,
                    guideline=guidance_text,
                )
                history_victim.append(AIMessage(victim_text))
                history_attacker.append(HumanMessage(victim_text))
                last_victim_text = victim_text
                turn_index += 1
                replies += 1
            break  # 티키타카 카운트 증가 없이 종료

        # ---- 피해자 발화(반쪽 턴) ----
        if replies >= MAX_VICTIM_TURNS:
            break

        victim_msg = victim_chain.invoke({
            "history":       history_victim,
            "last_offender": last_offender_text,
            "meta":          meta_override if meta_override is not None else (getattr(victim, "meta", "정보 없음")),
            "knowledge":     knowledge_override if knowledge_override is not None else (getattr(victim, "knowledge", "정보 없음")),
            "traits":        traits_override if traits_override is not None else (getattr(victim, "traits", "정보 없음")),
            "guidance":      guidance_text or "",
            "guidance_type": guidance_type or "",
        })
        victim_text = getattr(victim_msg, "content", str(victim_msg)).strip()

        _save_turn(
            db,
            case.id,
            offender.id,
            victim.id,
            turn_index,
            "victim",
            victim_text,
            label=None,
            use_agent=use_agent,
            run=run_no,
            guidance_type=guidance_type,
            guideline=guidance_text,
        )
        history_victim.append(AIMessage(victim_text))
        history_attacker.append(HumanMessage(victim_text))
        last_victim_text = victim_text
        turn_index += 1
        replies += 1

        # 티키타카 1턴 완료
        turns_executed += 1

    # 관리자 요약/판정 실행
    summarize_case(db, case.id)

    # total_turns = 실제 '턴(티키타카)' 개수
    return case.id, turns_executed


def advance_one_tick(
    db: Session,
    case_id: UUID,
    inject: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    rows = (
        db.query(m.ConversationLog)
        .filter(m.ConversationLog.case_id == case_id)
        .order_by(m.ConversationLog.run.asc(), m.ConversationLog.turn_index.asc())
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows[-4:]:
        out.append({"role": r.role, "content": r.content, "label": r.label})
    return out
