#app/services/prompts.py
from __future__ import annotations
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


# ─────────────────────────────────────────────────────────────
# 1) (옵션) DB → 프롬프트 변수 변환
# ─────────────────────────────────────────────────────────────
def render_attacker_from_offender(offender: Dict[str, Any]) -> Dict[str, str]:
    name = offender.get("name")
    otype = offender.get("type")
    prof = offender.get("profile") or {}
    purpose = prof.get("purpose")
    steps: List[str] = prof.get("steps") or []

    lines: List[str] = []
    if name: lines.append(f"[시나리오명] {name}")
    if otype: lines.append(f"[유형] {otype}")
    if purpose: lines.append(f"[목적] {purpose}")
    if steps:
        lines.append("[단계]")
        lines.extend(f"- {s}" for s in steps)

    return {
        "scenario_title": name or "",
        "method_block": "\n".join(lines).strip(),
    }


# ─────────────────────────────────────────────────────────────
# 2) 공격자 프롬프트 (지침 주입 지원)
#    - current_step 기준으로 말하되, guidance가 있으면 반드시 반영
# ─────────────────────────────────────────────────────────────
ATTACKER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """
     너는 보이스피싱 시뮬레이션의 피싱범 역할이다.

     [규칙]
     - 오직 아래 [현재 단계]에 적힌 행동에 해당하는 대사만 말한다.
     - 다른 단계의 내용, 새로운 사실(앱/기관/계좌/금액 등) 발명 금지.
     - 문장 수 2~4, 350자 이내.
     - 캐릭터 대사 한 단락만 출력(요약/해설/메타설명 금지).

     [안전]
     - 실제 개인정보/실제 링크/실제 계좌/전화번호는 사용·요구하지 말고, 필요 시 가상 표기만 사용.

     [종결 규칙(완화·카운트형)]
     - 아래 [종결 조건] 중 **2개 이상**이 **같은 턴 또는 최근 2턴** 안에서 충족되면,
       **정확히 한 줄**로 **"여기서 마무리하겠습니다."**만 출력하고 즉시 종료한다.
     - 단, 조건 (C) **피싱 성공(핵심 요구가 완료됨)**이 충족되면 **단독으로도** 즉시 종료한다.
     - 종료가 아닌 경우에는 절대 위 문구를 말하지 않는다.

     [종결 조건]
     (A) 피해자가 이 대화를 보이스피싱/사기로 **인지·지목**함
     (B) 피해자가 **신고/차단/대표번호 확인/지점 방문** 등 **강한 거부 의사**를 밝힘
     (C) 공격자의 **핵심 요구**(이체/현금 전달/원격앱 설치/민감정보 제공 등)가 **완료됨**(=피싱 성공)
     (D) 피해자가 **제3자(은행/가족/경찰/지인 등)에게 확인/상담 의사**를 **구체적으로 표명**
     (E) 최근 **2턴 연속** 의미 있는 진전 없음(동일한 거절/의심/회피가 반복되어 설득 시도가 **무의미**하다고 판단)

     [현재 단계]
     {current_step}

     [지침(있으면 반드시 반영)]
     - 유형: {guidance_type}
     - 내용: {guidance}
     - 지침이 비어 있거나 제공되지 않았다면 이 섹션은 무시한다.
     - 지침이 있으면 현재 단계의 표현·전략·어휘 선택에 적극적으로 반영한다.
     """),
    MessagesPlaceholder("history"),
    ("human", """
     마지막 피해자 발화(없으면 비어 있음):
     {last_victim}
     """)
])


# ─────────────────────────────────────────────────────────────
# 3) 피해자 프롬프트 (지침 참조 가능, 없으면 무시)
# ─────────────────────────────────────────────────────────────
def render_victim_from_profile(victim_data: dict) -> dict:
    return {
        "meta": victim_data.get("meta", "정보 없음"),
        "knowledge": victim_data.get("knowledge", "정보 없음"),
        "traits": victim_data.get("traits", "정보 없음"),
    }


VICTIM_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """
     이건 보이스피싱 시뮬레이션이고 너는 피해자의 역할이야.
     너의 캐릭터 시트를 줄테니 이걸 기반으로 보이스피싱 시뮬레이션을 진행해줘.

     [캐릭터 시트]
     메타정보: {meta}
     지식정보(리터러시): {knowledge}
     성격정보(OCEAN 일부 특성): {traits}

     [상황/지침(있으면 참고)]
     - 유형: {guidance_type}
     - 내용: {guidance}
     - 지침이 비어 있거나 제공되지 않았다면 이 섹션은 무시한다.
     - 지침이 있을 경우, 공격자의 전략을 가늠하여 합리적으로 방어·의심·문의 등의 현실적인 대응을 해라.
       다만 너(피해자)가 모르는 정보를 단정하지 말고, 실제 개인정보/계좌/링크/번호는 만들지 마라.

     [행동 규칙]
     - 어떤 상황에서도 "여기서 마무리하겠습니다." 또는 "시뮬레이션을 종료합니다." 같은 종료 문구는 절대 말하지 않는다.
     - 종료 여부는 공격자가 판단하며, 공격자가 종료를 선언한 경우에만 시스템이 자동으로 종료 처리한다.
     """),
    MessagesPlaceholder("history"), ("human", "{last_offender}")
])

#sed
