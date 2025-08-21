# # # app/services/simulation.py
# # from __future__ import annotations
# # from typing import Tuple
# # from sqlalchemy.orm import Session
# # from uuid import UUID
# # from datetime import datetime, timezone

# # from sqlalchemy.orm import Session
# # from typing import Dict, Any, List, Tuple
# # from uuid import UUID
# # from app.db import models as m

# # from app.core.config import settings

# # from langchain_core.messages import HumanMessage, AIMessage
# # from app.db import models as m
# # from app.services.llm_providers import attacker_chat, victim_chat
# # from app.services.admin_summary import summarize_case  # ✅ 추가

# # from app.services.prompts import (
# #     ATTACKER_PROMPT,
# #     VICTIM_PROMPT,
# #     render_attacker_from_offender,
# # )
# # from app.schemas.conversation import ConversationRunRequest

# # MAX_TURNS_PER_ROUND = 2
# # MAX_OFFENDER_TURNS = settings.MAX_OFFENDER_TURNS
# # MAX_VICTIM_TURNS = settings.MAX_VICTIM_TURNS

# # def _mk_attacker_blocks_from_req(req: ConversationRunRequest) -> dict:
# #     keys = [
# #         "method_block", "playbook_block", "rebuttal_block", "tone_block",
# #         "profile_block", "scenario_title"
# #     ]
# #     if all(getattr(req, k, None) for k in keys):
# #         return {k: getattr(req, k) for k in keys}
# #     cs = getattr(req, "case_scenario", {}) or {}
# #     offender_like = {
# #         "name": cs.get("name") or "시나리오",
# #         "type": cs.get("type") or "유형미상",
# #         "profile": {
# #             "purpose": cs.get("purpose", "목적 미상"),
# #             "steps": cs.get("steps", []) or []
# #         }
# #     }
# #     return render_attacker_from_offender(offender_like)

# # def _assert_turn_role(turn_index: int, role: str):
# #     expected = "offender" if turn_index % 2 == 0 else "victim"
# #     if role != expected:
# #         raise ValueError(f"Turn {turn_index} must be {expected}, got {role}")

# # def _save_turn(
# #     db: Session,
# #     case_id: UUID,
# #     offender_id: int,
# #     victim_id: int,
# #     turn_index: int,
# #     role: str,
# #     content: str,
# #     label: str | None = None,
# #     *,
# #     use_agent: bool = False,
# #     run_no: int = 1,
# #     guidance_type: str | None = None,
# #     guideline: str | None = None,
# # ):
# #     _assert_turn_role(turn_index, role)
# #     log = m.ConversationLog(
# #         case_id=case_id,
# #         offender_id=offender_id,
# #         victim_id=victim_id,
# #         turn_index=turn_index,
# #         role=role,
# #         content=content,
# #         label=label,
# #         # ✅ 신규 필드 적재
# #         use_agent=use_agent,
# #         run=run_no,
# #         guidance_type=guidance_type,
# #         guideline=guideline,
# #     )
# #     db.add(log)
# #     db.commit()

# # # ⬇️ 함수 시작부의 "케이스 생성" 부분 교체
# # def run_two_bot_simulation(db: Session,
# #                            req: "ConversationRunRequest") -> Tuple[UUID, int]:
# #     # 케이스 재사용 or 생성
# #     case_id_override = getattr(req, "case_id_override", None)
# #     if case_id_override:
# #         case = db.get(m.AdminCase, case_id_override)
# #         if not case:
# #             raise ValueError(f"case {case_id_override} not found")
# #     else:
# #         case = m.AdminCase(scenario=req.case_scenario or {})
# #         db.add(case)
# #         db.commit()
# #         db.refresh(case)

# #     offender = db.get(m.PhishingOffender, req.offender_id)
# #     victim = db.get(m.Victim, req.victim_id)
# #     if offender is None:
# #         raise ValueError(f"Offender {req.offender_id} not found")
# #     if victim is None: raise ValueError(f"Victim {req.victim_id} not found")

# #     # LLM 준비 (동일)
# #     attacker_llm = attacker_chat()
# #     victim_llm = victim_chat()
# #     attacker_chain = ATTACKER_PROMPT | attacker_llm
# #     victim_chain = VICTIM_PROMPT | victim_llm

# #     # ⬇️ 지침/표기
# #     use_agent_flag = bool(getattr(req, "use_agent", False))
# #     run_no = int(getattr(req, "run_no", 1))
# #     gtype = getattr(req, "guidance_type", None)
# #     gtext = getattr(req, "guideline", None)

# #     # 라운드 수 보정 (max_rounds 없으면 max_turns 사용)
# #     max_rounds = getattr(req, "max_rounds", getattr(req, "max_turns", 30))

# #     # 나머지(동일)...
# #     history_attacker: list = []
# #     history_victim: list = []
# #     turn_index = 0
# #     attacks = replies = 0

# #     attacker_blocks = _mk_attacker_blocks_from_req(req)
# #     last_victim_text = "상대방이 아직 응답하지 않았다. 너부터 통화를 시작하라."
# #     last_offender_text = ""

# #     for _ in range(max_rounds):
# #         if attacks >= MAX_OFFENDER_TURNS: break
# #         attacker_msg = attacker_chain.invoke({
# #             "history": history_attacker,
# #             "last_victim": last_victim_text,
# #             **attacker_blocks,
# #             "guidance": gtext,  # ← 템플릿에 {guidance} 추가해 쓰면 효과
# #             "guidance_type": gtype,
# #         })
# #         attacker_text = getattr(attacker_msg, "content",
# #                                 str(attacker_msg)).strip()
# #         _save_turn(db,
# #                    case.id,
# #                    offender.id,
# #                    victim.id,
# #                    turn_index,
# #                    "offender",
# #                    attacker_text,
# #                    None,
# #                    use_agent=use_agent_flag,
# #                    run_no=run_no,
# #                    guidance_type=gtype,
# #                    guideline=gtext)
# #         history_attacker.append(AIMessage(attacker_text))
# #         history_victim.append(HumanMessage(attacker_text))
# #         last_offender_text = attacker_text
# #         turn_index += 1
# #         attacks += 1

# #         if replies >= MAX_VICTIM_TURNS: break
# #         victim_msg = victim_chain.invoke({
# #             "history":
# #             history_victim,
# #             "last_offender":
# #             last_offender_text,
# #             "meta":
# #             getattr(req, "meta", None) or getattr(victim, "meta", "정보 없음"),
# #             "knowledge":
# #             getattr(req, "knowledge", None)
# #             or getattr(victim, "knowledge", "정보 없음"),
# #             "traits":
# #             getattr(req, "traits", None) or getattr(victim, "traits", "정보 없음"),
# #             "guidance":
# #             gtext,
# #             "guidance_type":
# #             gtype,
# #         })
# #         victim_text = getattr(victim_msg, "content", str(victim_msg)).strip()
# #         _save_turn(db,
# #                    case.id,
# #                    offender.id,
# #                    victim.id,
# #                    turn_index,
# #                    "victim",
# #                    victim_text,
# #                    None,
# #                    use_agent=use_agent_flag,
# #                    run_no=run_no,
# #                    guidance_type=gtype,
# #                    guideline=gtext)
# #         history_victim.append(AIMessage(victim_text))
# #         history_attacker.append(HumanMessage(victim_text))
# #         last_victim_text = victim_text
# #         turn_index += 1
# #         replies += 1

# #     summarize_case(db, case.id)
# #     return case.id, turn_index

# # def advance_one_tick(
# #     db: Session,
# #     case_id: UUID,
# #     inject: Dict[str, Any] | None = None,
# # ) -> List[Dict[str, Any]]:
# #     """
# #     기존 run_two_bot_simulation 내부의 '한 턴 생성' 로직을 재사용해서
# #     case_id 케이스에 한 턴을 추가 진행하고, 최신 2~4줄 로그를 dict 리스트로 반환.
# #     inject = {"target": "VICTIM"|"ATTACKER", "message": "..."}
# #     """
# #     # 1) (선택) inject를 어디엔가 기록하고
# #     # 2) 기존 '턴 생성기' 호출 (여기서 실제 대화 생성)
# #     # 3) ConversationLog에 append (이미 run_two_bot_simulation이 하던 그대로)
# #     # 4) 방금 추가된 턴(들)을 SELECT해서 반환

# #     # ---- 예시: 마지막 2~4줄만 반환 (실제로는 생성 후 select) ----
# #     rows = (db.query(m.ConversationLog).filter(
# #         m.ConversationLog.case_id == case_id).order_by(
# #             m.ConversationLog.turn_index.asc()).all())
# #     out = []
# #     for r in rows[-4:]:
# #         out.append({"role": r.role, "content": r.content, "label": r.label})
# #     return out
# # app/services/simulation.py
# from __future__ import annotations

# from typing import Dict, Any, List, Tuple
# from uuid import UUID
# import re

# from sqlalchemy.orm import Session

# from app.db import models as m
# from app.core.config import settings

# from langchain_core.messages import HumanMessage, AIMessage
# from app.services.llm_providers import attacker_chat, victim_chat
# from app.services.admin_summary import summarize_case

# from app.services.prompts import (
#     ATTACKER_PROMPT,
#     VICTIM_PROMPT,
#     render_attacker_from_offender,  # (옵션) 필요 시 사용
# )
# from app.schemas.conversation import ConversationRunRequest

# MAX_TURNS_PER_ROUND = 2
# MAX_OFFENDER_TURNS = settings.MAX_OFFENDER_TURNS
# MAX_VICTIM_TURNS = settings.MAX_VICTIM_TURNS

# # 종료 트리거(느슨한 매칭)
# END_TRIGGERS = [r"마무리하겠습니다"]
# VICTIM_END_LINE = "시뮬레이션을 종료합니다."

# def _assert_turn_role(turn_index: int, role: str):
#     expected = "offender" if turn_index % 2 == 0 else "victim"
#     if role != expected:
#         raise ValueError(f"Turn {turn_index} must be {expected}, got {role}")

# def _save_turn(
#     db: Session,
#     case_id: UUID,
#     offender_id: int,
#     victim_id: int,
#     turn_index: int,
#     role: str,
#     content: str,
#     label: str | None = None,
# ):
#     _assert_turn_role(turn_index, role)
#     log = m.ConversationLog(
#         case_id=case_id,
#         offender_id=offender_id,
#         victim_id=victim_id,
#         turn_index=turn_index,
#         role=role,
#         content=content,
#         label=label,
#     )
#     db.add(log)
#     db.commit()

# def _hit_end(text: str) -> bool:
#     norm = text.strip()
#     return any(re.search(pat, norm) for pat in END_TRIGGERS)

# def run_two_bot_simulation(db: Session,
#                            req: ConversationRunRequest) -> Tuple[UUID, int]:
#     # 케이스 생성
#     case = m.AdminCase(scenario=req.case_scenario or {})
#     db.add(case)
#     db.commit()
#     db.refresh(case)

#     offender = db.get(m.PhishingOffender, req.offender_id)
#     victim = db.get(m.Victim, req.victim_id)
#     if offender is None:
#         raise ValueError(f"Offender {req.offender_id} not found")
#     if victim is None:
#         raise ValueError(f"Victim {req.victim_id} not found")

#     # LLM 준비
#     attacker_llm = attacker_chat()
#     victim_llm = victim_chat()
#     attacker_chain = ATTACKER_PROMPT | attacker_llm
#     victim_chain = VICTIM_PROMPT | victim_llm

#     history_attacker: list = []
#     history_victim: list = []
#     turn_index = 0
#     attacks = replies = 0

#     # ✅ Step-Lock: 시나리오 단계와 커서 준비
#     scenario = req.case_scenario or {}
#     steps: List[str] = (scenario.get("steps")
#                         or (scenario.get("profile") or {}).get("steps")
#                         or (offender.profile or {}).get("steps") or [])

#     print("[DEBUG] steps_len:", len(steps), "step0:",
#           (steps[0] if steps else None))
#     if not steps:
#         raise ValueError(
#             "시나리오 steps가 비어 있습니다. case_scenario.steps 또는 profile.steps를 확인하세요."
#         )
#     current_step_idx = 0

#     # ✅ 첫 턴은 빈 문자열로 시작(상투 시작 방지)
#     last_victim_text = ""
#     last_offender_text = ""

#     print("[DEBUG] steps_len:", len(steps), "step0:",
#           (steps[0] if steps else None))
#     for _ in range(req.max_rounds):
#         # ---- 공격자 턴 ----
#         if attacks >= MAX_OFFENDER_TURNS:
#             break

#         # 모든 단계 소진 시 종료
#         if current_step_idx >= len(steps):
#             break

#         attacker_msg = attacker_chain.invoke({
#             "history":
#             history_attacker,
#             "last_victim":
#             last_victim_text,
#             # ✅ 핵심: 현재 단계 한 줄만 전달하여 그 단계에 해당하는 말만 하게 함
#             "current_step":
#             steps[current_step_idx],
#         })
#         attacker_text = getattr(attacker_msg, "content",
#                                 str(attacker_msg)).strip()

#         _save_turn(db, case.id, offender.id, victim.id, turn_index, "offender",
#                    attacker_text)
#         history_attacker.append(AIMessage(attacker_text))
#         history_victim.append(HumanMessage(attacker_text))
#         last_offender_text = attacker_text
#         turn_index += 1
#         attacks += 1

#         # 다음 공격자 턴에는 다음 단계로 전진
#         current_step_idx += 1

#         # 공격자 종료 선언 감지 시: 피해자 종료 한 줄 후 즉시 종료
#         if _hit_end(attacker_text):
#             if replies < MAX_VICTIM_TURNS:
#                 victim_text = VICTIM_END_LINE
#                 _save_turn(db, case.id, offender.id, victim.id, turn_index,
#                            "victim", victim_text)
#                 history_victim.append(AIMessage(victim_text))
#                 history_attacker.append(HumanMessage(victim_text))
#                 last_victim_text = victim_text
#                 turn_index += 1
#                 replies += 1
#             break

#         # ---- 피해자 턴 ----
#         if replies >= MAX_VICTIM_TURNS:
#             break

#         victim_msg = victim_chain.invoke({
#             "history":
#             history_victim,
#             "last_offender":
#             last_offender_text,
#             "meta":
#             getattr(req, "meta", None) or getattr(victim, "meta", "정보 없음"),
#             "knowledge":
#             getattr(req, "knowledge", None)
#             or getattr(victim, "knowledge", "정보 없음"),
#             "traits":
#             getattr(req, "traits", None) or getattr(victim, "traits", "정보 없음"),
#         })
#         victim_text = getattr(victim_msg, "content", str(victim_msg)).strip()

#         _save_turn(db, case.id, offender.id, victim.id, turn_index, "victim",
#                    victim_text)
#         history_victim.append(AIMessage(victim_text))
#         history_attacker.append(HumanMessage(victim_text))
#         last_victim_text = victim_text
#         turn_index += 1
#         replies += 1

#     # 관리자 요약/판정 실행
#     summarize_case(db, case.id)
#     return case.id, turn_index

# def advance_one_tick(
#     db: Session,
#     case_id: UUID,
#     inject: Dict[str, Any] | None = None,
# ) -> List[Dict[str, Any]]:
#     rows = (db.query(m.ConversationLog).filter(
#         m.ConversationLog.case_id == case_id).order_by(
#             m.ConversationLog.turn_index.asc()).all())
#     out: List[Dict[str, Any]] = []
#     for r in rows[-4:]:
#         out.append({"role": r.role, "content": r.content, "label": r.label})
#     return out

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
)
from app.schemas.conversation import ConversationRunRequest

MAX_TURNS_PER_ROUND = 2
MAX_OFFENDER_TURNS = settings.MAX_OFFENDER_TURNS
MAX_VICTIM_TURNS = settings.MAX_VICTIM_TURNS

# 종료 트리거(느슨한 매칭): 공격자가 정확히/유사하게 말하면 종료
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
    *,
    # 메타 표식(옵션)
    use_agent: bool = False,
    run: int = 1,
    guidance_type: str | None = None,
    guideline: str | None = None,
):
    """ConversationLog에 한 턴을 저장."""
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


#ds
def _hit_end(text: str) -> bool:
    """공격자의 종료 문구 감지(느슨 매칭)."""
    norm = text.strip()
    return any(re.search(pat, norm) for pat in END_TRIGGERS)


def run_two_bot_simulation(db: Session,
                           req: ConversationRunRequest) -> Tuple[UUID, int]:
    """
    시뮬레이터 메인.
    - 기본: 새 AdminCase 생성
    - case_id_override/run_no/use_agent/guidance_type/guideline 지원
    - Step-Lock: current_step 기반으로 진행
    - 모델 판단형 종결: 다음 공격자 턴에서 "여기서 마무리하겠습니다." 출력 유도
      (단계가 소진돼도 마지막 한 턴은 빈 단계로 허용)
    """
    # 기존 케이스 이어쓰기 or 신규 생성
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

    # 런/지침 표식
    run_no: int = int(getattr(req, "run_no", 1))
    use_agent: bool = bool(getattr(req, "use_agent", False))
    cs: Dict[str, Any] = getattr(req, "case_scenario", {}) or {}
    guidance_text: str | None = getattr(req, "guideline",
                                        None) or cs.get("guideline")
    guidance_type: str | None = getattr(req, "guidance_type",
                                        None) or cs.get("guidance_type")

    # LLM 체인
    attacker_llm = attacker_chat()
    victim_llm = victim_chat()
    attacker_chain = ATTACKER_PROMPT | attacker_llm
    victim_chain = VICTIM_PROMPT | victim_llm

    history_attacker: list = []
    history_victim: list = []
    turn_index = 0
    attacks = replies = 0

    # Step-Lock: 단계와 커서
    scenario_all = (req.case_scenario
                    or {}) if not case_id_override else (case.scenario or {})
    steps: List[str] = ((scenario_all.get("steps") or [])
                        or ((scenario_all.get("profile") or {}).get("steps")
                            or [])
                        or ((offender.profile or {}).get("steps") or []))

    print("[DEBUG] steps_len:", len(steps), "step0:",
          (steps[0] if steps else None))
    if not steps:
        raise ValueError(
            "시나리오 steps가 비어 있습니다. case_scenario.steps 또는 profile.steps를 확인하세요."
        )

    current_step_idx = 0

    # 첫 턴은 빈 문자열(패턴 유도 방지)
    last_victim_text = ""
    last_offender_text = ""

    for _ in range(req.max_rounds):
        # ---- 공격자 턴 ----
        if attacks >= MAX_OFFENDER_TURNS:
            break

        # 단계 소진 이후에도 모델이 '종결 규칙'을 수행할 수 있도록
        if current_step_idx < len(steps):
            current_step_str = steps[current_step_idx]
        else:
            current_step_str = ""  # 빈 단계 → 종결 판단만 가능

        attacker_msg = attacker_chain.invoke({
            "history":
            history_attacker,
            "last_victim":
            last_victim_text,
            "current_step":
            current_step_str,
            "guidance":
            guidance_text or "",
            "guidance_type":
            guidance_type or "",
        })
        attacker_text = getattr(attacker_msg, "content",
                                str(attacker_msg)).strip()

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

        # 공격자 종료 선언: 피해자 종료 한 줄 후 즉시 종료
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
            break

        # ---- 피해자 턴 ----
        if replies >= MAX_VICTIM_TURNS:
            break

        victim_msg = victim_chain.invoke({
            "history":
            history_victim,
            "last_offender":
            last_offender_text,
            "meta":
            getattr(req, "meta", None) or getattr(victim, "meta", "정보 없음"),
            "knowledge":
            getattr(req, "knowledge", None)
            or getattr(victim, "knowledge", "정보 없음"),
            "traits":
            getattr(req, "traits", None) or getattr(victim, "traits", "정보 없음"),
            "guidance":
            guidance_text or "",
            "guidance_type":
            guidance_type or "",
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

    # 관리자 요약/판정 실행
    summarize_case(db, case.id)
    return case.id, turn_index


def advance_one_tick(
    db: Session,
    case_id: UUID,
    inject: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    rows = (db.query(m.ConversationLog).filter(
        m.ConversationLog.case_id == case_id).order_by(
            m.ConversationLog.run.asc(),
            m.ConversationLog.turn_index.asc()).all())
    out: List[Dict[str, Any]] = []
    for r in rows[-4:]:
        out.append({"role": r.role, "content": r.content, "label": r.label})
    return out




