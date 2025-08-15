# app/services/simulation.py
from typing import Tuple
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone
import re
from app.core.config import settings

from langchain_core.messages import HumanMessage, AIMessage
from app.db import models as m
# from app.services.llm_providers import openai_chat, gemini_chat
from app.services.llm_providers import attacker_chat, victim_chat
from app.services.prompts import ATTACKER_PROMPT, VICTIM_PROMPT
from app.schemas.conversation import ConversationRunRequest

# 설명용 상수(턴 수 제어는 req.max_rounds + 아래 MAX_*_TURNS로 동작)
MAX_TURNS_PER_ROUND = 2
MAX_OFFENDER_TURNS = settings.MAX_OFFENDER_TURNS  # 피싱범 최대 발화 수
MAX_VICTIM_TURNS   = settings.MAX_VICTIM_TURNS    # 피해자 최대 발화 수

# --- 완료 행동(피해자 측) 감지 규칙 -----------------------------------------
#  - 현금 인출/송금/보관함 보관 등 "실행 완료"를 표현하는 한국어 패턴을 휴리스틱으로 감지
#  - 필요 시 keywords를 추가/조정하세요.
COMPLETE_KEYWORDS = [
    # 송금/이체 완료
    r"(송금|이체)\s*(완료|했[어요]?|했음|했습니다|했는데|했으니)",
    r"(보냈[어요]?|보냄)",  # 돈 보냄
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
    # 강건성: 숫자 금액/보관함 번호/비번 등과 함께 쓰이는 경우도 많음
    # 예) "24번 보관함에 넣었어요", "700만원 송금했습니다"
    for rx in COMPLETE_REGEXES:
        if rx.search(t):
            return True
    # 보조 규칙: 금액 + 송금/입금/인출 조합
    if re.search(r"(\d[\d,\.]*\s*(원|만원|억))", t) and re.search(r"(송금|입금|인출)", t):
        return True
    return False
# ---------------------------------------------------------------------------

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
    # attacker_llm = openai_chat()    # 피싱범: OpenAI
    # victim_llm   = gemini_chat()    # 피해자: Gemini
    attacker_llm = attacker_chat()     # ▶ .env의 ATTACKER_MODEL 사용 (항상 GPT)
    victim_llm   = victim_chat()        # ▶ 지금은 GPT, 나중엔 VICTIM_PROVIDER=gemini로 자동 전환
    attacker_chain = ATTACKER_PROMPT | attacker_llm
    victim_chain   = VICTIM_PROMPT   | victim_llm

    # 4) 히스토리 버퍼
    history_attacker: list = []
    history_victim: list = []
    turn_index = 0
    attacks = 0
    replies = 0

    # 5) 라운드 반복 (공격자 → 피해자), 각 역할 최대 10번, 피해자 완료 시 즉시 종료
    last_victim_text = "상대방이 아직 응답하지 않았다. 너부터 통화를 시작하라."
    last_offender_text = ""

    for _ in range(req.max_rounds):
        # ---- 공격자 턴 ----
        if attacks >= MAX_OFFENDER_TURNS:
            break
        attacker_msg = attacker_chain.invoke({
            "scenario": req.case_scenario,
            "profile": offender.profile,
            "history": history_attacker,
            "last_victim": last_victim_text,
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
            "meta": victim.meta,
            "knowledge": victim.knowledge,
            "traits": victim.traits,
            "history": history_victim,
            "last_offender": last_offender_text,
        })
        _save_turn(db, case.id, offender.id, victim.id, turn_index, "victim", victim_msg.content)
        history_victim   += [AIMessage(victim_msg.content)]
        history_attacker += [HumanMessage(victim_msg.content)]
        last_victim_text = victim_msg.content
        turn_index += 1
        replies += 1

        # ✅ 피해자 최종 행동 감지 → 즉시 종료
        if _victim_completed_action(victim_msg.content):
            # (선택) 케이스 상태를 바로 완료로 마킹
            case.status = "completed"
            case.completed_at = datetime.now(timezone.utc)
            db.commit()
            break

    return case.id, turn_index
