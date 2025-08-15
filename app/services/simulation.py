# app/services/simulation.py
from typing import Tuple
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone
import re
from app.core.config import settings

from langchain_core.messages import HumanMessage, AIMessage
from app.db import models as m
from app.services.llm_providers import attacker_chat, victim_chat
from app.services.prompts import (
    ATTACKER_PROMPT, VICTIM_PROMPT,
    render_attacker_from_offender,          # ✅ CHANGED: 블록 생성 함수 사용
)
from app.schemas.conversation import ConversationRunRequest

# 설명용 상수(턴 수 제어는 req.max_rounds + 아래 MAX_*_TURNS로 동작)
MAX_TURNS_PER_ROUND = 2
MAX_OFFENDER_TURNS = settings.MAX_OFFENDER_TURNS  # 피싱범 최대 발화 수
MAX_VICTIM_TURNS   = settings.MAX_VICTIM_TURNS    # 피해자 최대 발화 수

# --- 완료 행동(피해자 측) 감지 규칙 -----------------------------------------
COMPLETE_KEYWORDS = [
    # 송금/이체 완료
    r"(송금|이체)\s*(완료|했[어요]?|했음|했습니다|했는데|했으니)",
    r"(보냈[어요]?|보냄)",
    r"(입금)\s*(완료|했[어요]?|했습니다)",
    # 현금 인출 + 보관
    r"(현금|돈)\s*(다\s*)?인출(했[어요]?|했습니다)",
    r"(보관함|락커|보관\s*함)\s*(에|에다)\s*(넣었|두었|보관했)",
    r"(지정|안전관리)\s*(전용)?\s*(계좌|보관함)",
    # 액션 완료 일반형
    r"(말씀|지시)\s*대로\s*(했[어요]?|완료했|처리했)",
]
COMPLETE_REGEXES = [re.compile(p) for p in COMPLETE_KEYWORDS]

def _victim_completed_action(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    for rx in COMPLETE_REGEXES:
        if rx.search(t):
            return True
    # 금액 + 행위 조합
    if re.search(r"(\d[\d,\.]*\s*(원|만원|억))", t) and re.search(r"(송금|입금|인출)", t):
        return True
    return False
# ---------------------------------------------------------------------------

# ✅ CHANGED: req에 블록이 없으면 case_scenario로부터 공격자 블록을 생성
def _mk_attacker_blocks_from_req(req: ConversationRunRequest) -> dict:
    """
    ConversationRunRequest에서 공격자 프롬프트 블록을 준비한다.
    - req에 블록들이 있으면 그대로 사용
    - 없으면 case_scenario(purpose/steps/type)로부터 생성
    """
    keys = ["method_block","playbook_block","rebuttal_block","tone_block","profile_block","scenario_title"]
    if all(getattr(req, k, None) for k in keys):
        return {k: getattr(req, k) for k in keys}

    cs = getattr(req, "case_scenario", {}) or {}
    offender_like = {
        "name": cs.get("name") or "시나리오",
        "type": cs.get("type") or "유형미상",
        "profile": {
            "purpose": cs.get("purpose", "목적 미상"),
            "steps": cs.get("steps", []) or []
        }
    }
    return render_attacker_from_offender(offender_like)

def _assert_turn_role(turn_index: int, role: str):
    """0턴=offender, 1턴=victim, 2턴=offender ... 번갈이 검증"""
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
    """턴 저장: 번갈이 역할 가드 + 즉시 커밋(로그 내결함성)"""
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

def run_two_bot_simulation(db: Session, req: ConversationRunRequest) -> Tuple[UUID, int]:
    # 1) 케이스 생성(시나리오 스냅샷)
    case = m.AdminCase(scenario=req.case_scenario)  # status 기본값: "running"
    db.add(case); db.commit(); db.refresh(case)

    # 2) 참여자 로드(방어)
    offender = db.get(m.PhishingOffender, req.offender_id)
    victim = db.get(m.Victim, req.victim_id)
    if offender is None:
        raise ValueError(f"Offender {req.offender_id} not found")
    if victim is None:
        raise ValueError(f"Victim {req.victim_id} not found")

    # 3) LLM 체인 구성
    attacker_llm = attacker_chat()   # ▶ .env의 ATTACKER_MODEL 사용
    victim_llm   = victim_chat()     # ▶ 지금은 GPT, 나중엔 VICTIM_PROVIDER=gemini로 자동 전환
    attacker_chain = ATTACKER_PROMPT | attacker_llm
    victim_chain   = VICTIM_PROMPT   | victim_llm

    # 4) 히스토리 버퍼
    history_attacker: list = []
    history_victim: list = []
    turn_index = 0
    attacks = 0
    replies = 0

    # 5) 라운드 반복 (공격자 → 피해자), 각 역할 최대 N번, 피해자 완료 시 즉시 종료
    last_victim_text = "상대방이 아직 응답하지 않았다. 너부터 통화를 시작하라."
    last_offender_text = ""

    # ✅ CHANGED: 공격자 프롬프트 블록 준비
    attacker_blocks = _mk_attacker_blocks_from_req(req)

    for _ in range(req.max_rounds):
        # ---- 공격자 턴 ----
        if attacks >= MAX_OFFENDER_TURNS:
            break
        attacker_msg = attacker_chain.invoke({
            "history": history_attacker,
            "last_victim": last_victim_text,
            **attacker_blocks,          # ✅ CHANGED: 새 키들 전달
        })
        _save_turn(db, case.id, offender.id, victim.id, turn_index, "offender", attacker_msg.content)
        history_attacker += [AIMessage(attacker_msg.content)]
        history_victim   += [HumanMessage(attacker_msg.content)]
        last_offender_text = attacker_msg.content
        turn_index += 1
        attacks += 1

        # ---- 피해자 턴 ----
        if replies >= MAX_VICTIM_TURNS:
            break
        victim_msg = victim_chain.invoke({
            "history": history_victim,
            "last_offender": last_offender_text,
            # ✅ CHANGED: req에서 넘어온 값을 우선 사용(없으면 victim 모델)
            "meta":       getattr(req, "meta",       None) or getattr(victim, "meta", "정보 없음"),
            "knowledge":  getattr(req, "knowledge",  None) or getattr(victim, "knowledge", "정보 없음"),
            "traits":     getattr(req, "traits",     None) or getattr(victim, "traits", "정보 없음"),
        })
        _save_turn(db, case.id, offender.id, victim.id, turn_index, "victim", victim_msg.content)
        history_victim   += [AIMessage(victim_msg.content)]
        history_attacker += [HumanMessage(victim_msg.content)]
        last_victim_text = victim_msg.content
        turn_index += 1
        replies += 1

        # ✅ 피해자 최종 행동 감지 → 즉시 종료
        if _victim_completed_action(victim_msg.content):
            case.status = "completed"
            case.completed_at = datetime.now(timezone.utc)
            db.commit()
            break

    return case.id, turn_index
