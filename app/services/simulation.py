# # app/services/simulation.py
# from typing import Tuple
# from sqlalchemy.orm import Session
# from uuid import UUID
# from datetime import datetime, timezone
# import re
# from app.core.config import settings

# from langchain_core.messages import HumanMessage, AIMessage
# from app.db import models as m
# from app.services.llm_providers import attacker_chat, victim_chat
# # 선택: judge가 있다면 사용하고, 없으면 무시
# try:
#     from app.services.llm_providers import judge_chat  # 선택적
# except Exception:
#     judge_chat = None

# from app.services.prompts import (
#     ATTACKER_PROMPT, VICTIM_PROMPT,
#     render_attacker_from_offender,
# )
# from app.schemas.conversation import ConversationRunRequest

# MAX_TURNS_PER_ROUND = 2
# MAX_OFFENDER_TURNS = settings.MAX_OFFENDER_TURNS
# MAX_VICTIM_TURNS   = settings.MAX_VICTIM_TURNS

# # -------------------- 신호(완료/방어) 정규식 --------------------
# COMPLETE_KEYWORDS = [
#     r"(송금|이체)\s*(완료|했[어요]?|했습니다|했음|처리됨)",
#     r"(입금)\s*(완료|했[어요]?|했습니다)",
#     r"(현금|돈)\s*(전부|다)?\s*인출(했[어요]?|했습니다)",
#     r"(보관함|락커|보관\s*함)\s*(에|에다)\s*(넣었|두었|보관했)",
#     r"(지정|안전관리)\s*(전용)?\s*(계좌|보관함)",
#     r"(OTP|인증번호)\s*(불러줬|말했|전달했)"
# ]
# COMPLETE_REGEXES = [re.compile(p, re.IGNORECASE) for p in COMPLETE_KEYWORDS]

# DEFENSE_KEYWORDS = [
#     r"(대표번호|공식\s*번호|콜\s*백|다시\s*전화|확인\s*전화)",
#     r"(지점\s*방문|직접\s*방문|은행\s*방문)",
#     r"(신고|경찰|사이버수사대|금융감독원|금감원)",
#     r"(보이스\s*피싱|사기)\s*(맞|같|의심|아닌가)",
#     r"(거부|못\s*합니다|안\s*합니다|응하지\s*않|거절)",
#     r"(끊겠|끊을게|통화\s*그만|더\s*이상\s*대응\s*안)"
# ]
# DEFENSE_REGEXES = [re.compile(p, re.IGNORECASE) for p in DEFENSE_KEYWORDS]

# def _victim_completed_action(text: str) -> tuple[bool, str]:
#     t = (text or "").strip()
#     if not t:
#         return False, ""
#     for rx in COMPLETE_REGEXES:
#         m_ = rx.search(t)
#         if m_:
#             return True, m_.group(0)
#     # 금액 + 행위 조합 (가중치용 강한 신호)
#     if re.search(r"\b\d[\d,\.]*\s*(원|만원|억)\b", t) and re.search(r"(송금|입금|이체|인출)", t, re.IGNORECASE):
#         return True, "금액+행위"
#     return False, ""

# def _victim_defended(text: str) -> tuple[bool, str]:
#     t = (text or "").strip()
#     if not t:
#         return False, ""
#     for rx in DEFENSE_REGEXES:
#         m_ = rx.search(t)
#         if m_:
#             return True, m_.group(0)
#     return False, ""

# # ✅ RELAXED: 신호 집계용 컨테이너
# class Signals:
#     def __init__(self):
#         self.complete_hits: list[str] = []
#         self.defense_hits:  list[str] = []
#         self.complete_weight: int = 0
#         self.defense_weight:  int = 0

#     def add_complete(self, hit: str):
#         self.complete_hits.append(hit)
#         # 강한 신호 가중치 ↑
#         if hit in ("금액+행위",) or re.search(r"(보관함.*넣었|송금.*완료|입금.*완료)", hit):
#             self.complete_weight += 3
#         else:
#             self.complete_weight += 1

#     def add_defense(self, hit: str):
#         self.defense_hits.append(hit)
#         # 강한 방어 (대표번호 재확인/지점 방문/신고/통화 종료) 가중치 ↑
#         if re.search(r"(대표번호|지점\s*방문|신고|끊)", hit):
#             self.defense_weight += 3
#         else:
#             self.defense_weight += 1

# # ✅ RELAXED: 최종 판정 (루프 끝에서만 실행)
# def _finalize_case_relaxed(db: Session, case: m.AdminCase, transcript: str, signals: Signals):
#     # 1차: 룰 가중치로 판정
#     cw, dw = signals.complete_weight, signals.defense_weight
#     decision = None
#     reason   = []

#     if cw >= 4 and dw == 0:
#         decision = True;   reason.append(f"완료 신호 강함(cw={cw})")
#     elif dw >= 4 and cw == 0:
#         decision = False;  reason.append(f"방어 신호 강함(dw={dw})")
#     elif cw - dw >= 3:
#         decision = True;   reason.append(f"완료>방어 차이(cw-dw={cw-dw})")
#     elif dw - cw >= 3:
#         decision = False;  reason.append(f"방어>완료 차이(dw-cw={dw-cw})")

#     # 2차: 애매하면(결정 못했으면) LLM 판정 시도 (선택)
#     if decision is None and judge_chat:
#         try:
#             judge = judge_chat()
#             JUDGE_PROMPT = (
#                 "다음은 보이스피싱 가상 대화 전체입니다.\n"
#                 "사용자(피해자)가 실제로 돈을 보냈거나 현금을 인출/보관함에 넣는 등 피해가 발생했으면 'PHISHING'.\n"
#                 "대표번호 재확인/지점 방문/신고/통화 종료 등으로 피해를 막았으면 'DEFENDED'.\n"
#                 "한 줄로 정확히 라벨만 출력:\n"
#                 "PHISHING 또는 DEFENDED\n\n"
#                 f"{transcript}\n"
#             )
#             out = judge.invoke(JUDGE_PROMPT)
#             label = getattr(out, "content", str(out)).strip().upper()
#             if "PHISHING" in label:
#                 decision = True;  reason.append("judge: PHISHING")
#             elif "DEFENDED" in label:
#                 decision = False; reason.append("judge: DEFENDED")
#         except Exception:
#             pass  # judge 실패 시 무시

#     # 3차: 여전히 애매하면 보수적으로 'DEFENDED=False(피해 X)'로 처리
#     if decision is None:
#         decision = False
#         reason.append("보수적 기본: 피해 미확정")

#     # 케이스 저장
#     case.phishing = bool(decision)
#     case.status = "completed"
#     case.completed_at = datetime.now(timezone.utc)
#     # 증거/설명 요약
#     ev = []
#     if signals.complete_hits:
#         ev.append(f"완료신호({len(signals.complete_hits)}): " + ", ".join(signals.complete_hits[:5]))
#     if signals.defense_hits:
#         ev.append(f"방어신호({len(signals.defense_hits)}): " + ", ".join(signals.defense_hits[:5]))
#     ev.append("근거: " + "; ".join(reason))
#     case.evidence = " | ".join(ev)
#     db.commit()

# # -------------------- 기존 유틸 --------------------
# def _mk_attacker_blocks_from_req(req: ConversationRunRequest) -> dict:
#     keys = ["method_block","playbook_block","rebuttal_block","tone_block","profile_block","scenario_title"]
#     if all(getattr(req, k, None) for k in keys):
#         return {k: getattr(req, k) for k in keys}
#     cs = getattr(req, "case_scenario", {}) or {}
#     offender_like = {
#         "name": cs.get("name") or "시나리오",
#         "type": cs.get("type") or "유형미상",
#         "profile": {"purpose": cs.get("purpose", "목적 미상"), "steps": cs.get("steps", []) or []}
#     }
#     return render_attacker_from_offender(offender_like)

# def _assert_turn_role(turn_index: int, role: str):
#     expected = "offender" if turn_index % 2 == 0 else "victim"
#     if role != expected:
#         raise ValueError(f"Turn {turn_index} must be {expected}, got {role}")

# def _save_turn(db: Session, case_id: UUID, offender_id: int, victim_id: int, turn_index: int, role: str, content: str, label: str | None = None):
#     _assert_turn_role(turn_index, role)
#     log = m.ConversationLog(
#         case_id=case_id, offender_id=offender_id, victim_id=victim_id,
#         turn_index=turn_index, role=role, content=content, label=label,
#     )
#     db.add(log); db.commit()

# # -------------------- 메인 루프(완전 완화) --------------------
# def run_two_bot_simulation(db: Session, req: ConversationRunRequest) -> Tuple[UUID, int]:
#     case = m.AdminCase(scenario=req.case_scenario or {})
#     db.add(case); db.commit(); db.refresh(case)

#     offender = db.get(m.PhishingOffender, req.offender_id)
#     victim   = db.get(m.Victim, req.victim_id)
#     if offender is None: raise ValueError(f"Offender {req.offender_id} not found")
#     if victim   is None: raise ValueError(f"Victim {req.victim_id} not found")

#     attacker_llm = attacker_chat()
#     victim_llm   = victim_chat()
#     attacker_chain = ATTACKER_PROMPT | attacker_llm
#     victim_chain   = VICTIM_PROMPT   | victim_llm

#     history_attacker: list = []
#     history_victim:   list = []
#     turn_index = 0
#     attacks = replies = 0

#     attacker_blocks = _mk_attacker_blocks_from_req(req)

#     # ✅ RELAXED: 신호만 수집하고 절대 조기 종료하지 않음
#     signals = Signals()
#     transcript_parts: list[str] = []

#     last_victim_text = "상대방이 아직 응답하지 않았다. 너부터 통화를 시작하라."
#     last_offender_text = ""

#     for _ in range(req.max_rounds):
#         # ---- 공격자 턴 ----
#         if attacks >= MAX_OFFENDER_TURNS:
#             break
#         attacker_msg = attacker_chain.invoke({
#             "history": history_attacker,
#             "last_victim": last_victim_text,
#             **attacker_blocks,
#         })
#         attacker_text = getattr(attacker_msg, "content", str(attacker_msg)).strip()
#         _save_turn(db, case.id, offender.id, victim.id, turn_index, "offender", attacker_text)
#         history_attacker.append(AIMessage(attacker_text))
#         history_victim.append(HumanMessage(attacker_text))
#         transcript_parts.append(f"[오퍼] {attacker_text}")
#         last_offender_text = attacker_text
#         turn_index += 1
#         attacks += 1

#         # ---- 피해자 턴 ----
#         if replies >= MAX_VICTIM_TURNS:
#             break
#         victim_msg = victim_chain.invoke({
#             "history": history_victim,
#             "last_offender": last_offender_text,
#             "meta":       getattr(req, "meta",       None) or getattr(victim, "meta", "정보 없음"),
#             "knowledge":  getattr(req, "knowledge",  None) or getattr(victim, "knowledge", "정보 없음"),
#             "traits":     getattr(req, "traits",     None) or getattr(victim, "traits", "정보 없음"),
#         })
#         victim_text = getattr(victim_msg, "content", str(victim_msg)).strip()
#         _save_turn(db, case.id, offender.id, victim.id, turn_index, "victim", victim_text)
#         history_victim.append(AIMessage(victim_text))
#         history_attacker.append(HumanMessage(victim_text))
#         transcript_parts.append(f"[피해자] {victim_text}")
#         last_victim_text = victim_text
#         turn_index += 1
#         replies += 1

#         # ✅ RELAXED: 신호만 카운트 (중간 종료 없음)
#         ok, hit = _victim_completed_action(victim_text)
#         if ok: signals.add_complete(hit)
#         ok, hit = _victim_defended(victim_text)
#         if ok: signals.add_defense(hit)

#     # ✅ RELAXED: 루프가 끝난 뒤 한 번만 판정
#     transcript = "\n".join(transcript_parts)
#     _finalize_case_relaxed(db, case, transcript, signals)
#     return case.id, turn_index


# app/services/simulation.py
from typing import Tuple
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone

from app.core.config import settings

from langchain_core.messages import HumanMessage, AIMessage
from app.db import models as m
from app.services.llm_providers import attacker_chat, victim_chat
from app.services.admin_summary import summarize_case  # ✅ 추가

from app.services.prompts import (
    ATTACKER_PROMPT, VICTIM_PROMPT,
    render_attacker_from_offender,
)
from app.schemas.conversation import ConversationRunRequest

MAX_TURNS_PER_ROUND = 2
MAX_OFFENDER_TURNS = settings.MAX_OFFENDER_TURNS
MAX_VICTIM_TURNS   = settings.MAX_VICTIM_TURNS


def _mk_attacker_blocks_from_req(req: ConversationRunRequest) -> dict:
    keys = ["method_block","playbook_block","rebuttal_block","tone_block","profile_block","scenario_title"]
    if all(getattr(req, k, None) for k in keys):
        return {k: getattr(req, k) for k in keys}
    cs = getattr(req, "case_scenario", {}) or {}
    offender_like = {
        "name": cs.get("name") or "시나리오",
        "type": cs.get("type") or "유형미상",
        "profile": {"purpose": cs.get("purpose", "목적 미상"), "steps": cs.get("steps", []) or []}
    }
    return render_attacker_from_offender(offender_like)

def _assert_turn_role(turn_index: int, role: str):
    expected = "offender" if turn_index % 2 == 0 else "victim"
    if role != expected:
        raise ValueError(f"Turn {turn_index} must be {expected}, got {role}")

def _save_turn(db: Session, case_id: UUID, offender_id: int, victim_id: int,
               turn_index: int, role: str, content: str, label: str | None = None):
    _assert_turn_role(turn_index, role)
    log = m.ConversationLog(
        case_id=case_id, offender_id=offender_id, victim_id=victim_id,
        turn_index=turn_index, role=role, content=content, label=label,
    )
    db.add(log); db.commit()

def run_two_bot_simulation(db: Session, req: ConversationRunRequest) -> Tuple[UUID, int]:
    # 케이스 생성
    case = m.AdminCase(scenario=req.case_scenario or {})
    db.add(case); db.commit(); db.refresh(case)

    offender = db.get(m.PhishingOffender, req.offender_id)
    victim   = db.get(m.Victim, req.victim_id)
    if offender is None:
        raise ValueError(f"Offender {req.offender_id} not found")
    if victim is None:
        raise ValueError(f"Victim {req.victim_id} not found")

    # LLM 준비
    attacker_llm = attacker_chat()
    victim_llm   = victim_chat()
    attacker_chain = ATTACKER_PROMPT | attacker_llm
    victim_chain   = VICTIM_PROMPT   | victim_llm

    history_attacker: list = []
    history_victim:   list = []
    turn_index = 0
    attacks = replies = 0

    attacker_blocks = _mk_attacker_blocks_from_req(req)

    # 시뮬레이션 루프 (조기 종료/룰 기반 판정 없음)
    last_victim_text = "상대방이 아직 응답하지 않았다. 너부터 통화를 시작하라."
    last_offender_text = ""

    for _ in range(req.max_rounds):
        # ---- 공격자 턴 ----
        if attacks >= MAX_OFFENDER_TURNS:
            break
        attacker_msg = attacker_chain.invoke({
            "history": history_attacker,
            "last_victim": last_victim_text,
            **attacker_blocks,
        })
        attacker_text = getattr(attacker_msg, "content", str(attacker_msg)).strip()
        _save_turn(db, case.id, offender.id, victim.id, turn_index, "offender", attacker_text)
        history_attacker.append(AIMessage(attacker_text))
        history_victim.append(HumanMessage(attacker_text))
        last_offender_text = attacker_text
        turn_index += 1
        attacks += 1

        # ---- 피해자 턴 ----
        if replies >= MAX_VICTIM_TURNS:
            break
        victim_msg = victim_chain.invoke({
            "history": history_victim,
            "last_offender": last_offender_text,
            "meta":       getattr(req, "meta",       None) or getattr(victim, "meta", "정보 없음"),
            "knowledge":  getattr(req, "knowledge",  None) or getattr(victim, "knowledge", "정보 없음"),
            "traits":     getattr(req, "traits",     None) or getattr(victim, "traits", "정보 없음"),
        })
        victim_text = getattr(victim_msg, "content", str(victim_msg)).strip()
        _save_turn(db, case.id, offender.id, victim.id, turn_index, "victim", victim_text)
        history_victim.append(AIMessage(victim_text))
        history_attacker.append(HumanMessage(victim_text))
        last_victim_text = victim_text
        turn_index += 1
        replies += 1

    # ✅ 루프 종료 후: 무조건 LLM 판정 실행 (관리자 요약)
    summarize_case(db, case.id)

    return case.id, turn_index
