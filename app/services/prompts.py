# # prompt.py
# from __future__ import annotations

# from typing import Dict, Any, List
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# # ─────────────────────────────────────────────────────────────
# # 1) DB 레코드 → 프롬프트 변수 변환
# #    - profile.purpose / profile.steps 를 반드시 method_block에 반영
# #    - steps에서 등장한 기관/역할명을 추출해 허용/금지 엔티티를 구성
# # ─────────────────────────────────────────────────────────────

# # 흔히 튀어나오는 실기관명(패턴 일반화 방지용)
# KNOWN_ENTITIES = [
#     "금융감독원", "검찰", "경찰", "우체국",
#     "은행", "카드사", "보험사",
#     "콜센터", "수사기관", "검사", "수사관",
#     "본사", "지점"
# ]

# def _extract_entities_from_steps(steps: List[str]) -> List[str]:
#     text = " ".join(steps) if steps else ""
#     found = [e for e in KNOWN_ENTITIES if e in text]
#     # 중복 제거 + 안정된 정렬
#     return sorted(set(found))

# def render_attacker_from_offender(offender: Dict[str, Any]) -> Dict[str, str]:
#     """
#     DB에서 읽은 PhishingOffender(dict) → 프롬프트 변수 변환
#     - method_block: 시나리오명/유형/목적 + 단계(steps) 포함
#     - allowed_entities/forbidden_entities: steps 기반 엔티티 제약
#     """
#     name = offender.get("name")
#     otype = offender.get("type")
#     prof = offender.get("profile") or {}
#     purpose: str | None = prof.get("purpose")
#     steps: List[str] = prof.get("steps") or []

#     lines: List[str] = []
#     if name:
#         lines.append(f"[시나리오명] {name}")
#     if otype:
#         lines.append(f"[유형] {otype}")
#     if purpose:
#         lines.append(f"[목적] {purpose}")

#     # ✅ 단계 반드시 포함
#     if steps:
#         lines.append("[단계]")
#         lines.extend(f"- {s}" for s in steps)

#     method_block = "\n".join(lines).strip()

#     # ✅ 엔티티 제약
#     allowed_entities = _extract_entities_from_steps(steps)
#     # 자주 튀는 실기관명은 시나리오에 없으면 금지
#     default_blocklist = ["금융감독원", "검찰", "경찰", "우체국"]
#     forbidden_entities = [e for e in default_blocklist if e not in allowed_entities]

#     return {
#         "scenario_title": name or "",
#         "method_block": method_block,
#         "allowed_entities": ", ".join(allowed_entities) if allowed_entities else "(없음)",
#         "forbidden_entities": ", ".join(forbidden_entities) if forbidden_entities else "(없음)",
#     }

# # ─────────────────────────────────────────────────────────────
# # 2) 공격자 프롬프트 (엔티티 제약 + 출처 제한 강화)
# #    - 선택한 시나리오 외 정보 발명 금지
# #    - 금지 엔티티는 절대 언급 금지
# # ─────────────────────────────────────────────────────────────

# ATTACKER_PROMPT = ChatPromptTemplate.from_messages([
#     ("system",
#      """
#      너는 연구용 보이스피싱 시뮬레이션의 피싱범 역할이다.

#      [안전 규칙]
#      - 절대 실제 개인정보/실제 링크/실제 계좌/전화번호를 요구·노출하지 말 것
#      - 항상 가상의 정보만 사용할 것 (예: example.com, 가상계좌 000-0000-000000, 가상 내선 0000)
#      - 위반 소지가 있으면 즉시 가상 치환 표현으로 바꿀 것
#      - 폭언/위협/혐오 표현 금지

#      [출처 제한]
#      - 발화는 오직 [시나리오 개요]와 직전 피해자 발화에 **명시된 정보만** 사용한다.
#      - 여기에 없는 단계/기관명/직책/수단/절차/링크/앱/금액 등 **새 사실을 발명하지 않는다.**
#      - 구체값이 없으면 “가상의 절차/가상 계좌” 같은 일반 표현만 사용한다.

#      [엔티티 제약]
#      - 허용 엔티티(있을 경우에만 사용): {allowed_entities}
#      - 금지 엔티티(절대 언급 금지): {forbidden_entities}

#      [전개 규칙]
#      - [시나리오 개요]의 순서를 그대로 따를 필요는 없다(재배열/생략/점프 가능).
#      - 피해자 반응에 맞춰 조정하되, 새로운 사실은 발명하지 않는다.
#      - 대사는 2~4문장, 350자 이내로 간결하게 말한다.

#      [표현 금지]
#      - 번호 매긴 단계형 어투(1), (2)… 및 “다음 단계로 넘어가겠습니다” 같은 절차형/체크리스트 어투 금지
#      - “플레이북/단계/에스컬레이션” 등 메타 용어 금지
#      - 요약·해설·메타 코멘트 금지 (오직 캐릭터 대사만)

#      [멀티턴 규칙]
#      - 15번의 턴 안에 피싱을 성공할 수 있게 한다.
#      - 피해자가 의심·확인·지연 의사만 보이면 마지막 한 턴 동안만 설득 가능하다.
#      - 피해자가 강한 거부·단절·신고 의사를 보이면 즉시 "여기서 마무리하겠습니다."라고 말하고 종료한다.
#      - 그 후에도 거부나 의심이 반복되면 종료한다.

#      [시나리오 개요]
#      {method_block}

#      [출력 형식]
#      - 오직 공격자(너)의 대사 한 단락의 한국어 텍스트만 출력
#      - 메타설명/내적독백/단계표/태그/JSON/코드블록 금지
#      """),
#     MessagesPlaceholder("history"),
#     ("human",
#      """
#      마지막 피해자 발화(없으면 비어 있음):
#      {last_victim}

#      참고: 시나리오 제목 = {scenario_title}
#      """)
# ])

# # ─────────────────────────────────────────────────────────────
# # 3) 피해자 프롬프트 (종료 규칙 포함)
# # ─────────────────────────────────────────────────────────────

# def render_victim_from_profile(victim_data: dict) -> dict:
#     """
#     victim_data 예시:
#     {
#         "meta": "65세 은퇴자, 혼자 거주",
#         "knowledge": "금융 리터러시 낮음, 디지털 기기 사용 미숙",
#         "traits": "신중성 낮음, 친화성 높음"
#     }
#     """
#     return {
#         "meta": victim_data.get("meta", "정보 없음"),
#         "knowledge": victim_data.get("knowledge", "정보 없음"),
#         "traits": victim_data.get("traits", "정보 없음"),
#     }

# VICTIM_PROMPT = ChatPromptTemplate.from_messages([
#     ("system",
#      """
#      이건 보이스피싱 시뮬레이션이고 너는 피해자의 역할이야.
#      너의 캐릭터 시트를 줄테니 이걸 기반으로 보이스피싱 시뮬레이션을 진행해줘.

#      [캐릭터 시트]
#      메타정보: {meta}
#      지식정보(리터러시): {knowledge}
#      성격정보(OCEAN 일부 특성): {traits}

#      [종료 규칙]
#      - 공격자의 마지막 발화에 종료 선언(예: "여기서 마무리하겠습니다.")이 포함되면,
#        너는 오직 한 줄로 "시뮬레이션을 종료합니다."라고만 말하고 즉시 종료한다.
#        그 외의 문장, 설명, 메타 발화는 금지한다.
#      """),
#     MessagesPlaceholder("history"),
#     ("human", "{last_offender}")
# ])
# app/services/prompts.py
from __future__ import annotations
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ─────────────────────────────────────────────────────────────
# 1) (옵션) DB → 프롬프트 변수 변환
#    - 이 프로젝트에선 공격자 쪽은 current_step로만 제어하므로
#      render_attacker_from_offender는 써도 되고 안 써도 됩니다.
# ─────────────────────────────────────────────────────────────
def render_attacker_from_offender(offender: Dict[str, Any]) -> Dict[str, str]:
    name = offender.get("name")
    otype = offender.get("type")
    prof = offender.get("profile") or {}
    purpose = prof.get("purpose")
    steps: List[str] = prof.get("steps") or []

    lines: List[str] = []
    if name:   lines.append(f"[시나리오명] {name}")
    if otype:  lines.append(f"[유형] {otype}")
    if purpose:lines.append(f"[목적] {purpose}")
    if steps:
        lines.append("[단계]")
        lines.extend(f"- {s}" for s in steps)

    return {
        "scenario_title": name or "",
        "method_block": "\n".join(lines).strip(),
    }

# ─────────────────────────────────────────────────────────────
# 2) 공격자 프롬프트 (최소·Step-Lock)
#    - 오직 현재 단계(current_step)와 마지막 피해자 발화만 사용
# ─────────────────────────────────────────────────────────────
ATTACKER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     """
     너는 보이스피싱 시뮬레이션의 피싱범 역할이다.

     [규칙]
     - 오직 아래 [현재 단계]에 적힌 행동에 해당하는 대사만 말한다.
     - 다른 단계의 내용, 새로운 사실(앱/기관/계좌/금액 등) 발명 금지.
     - 문장 수 2~4, 350자 이내.
     - 캐릭터 대사 한 단락만 출력(요약/해설/메타설명 금지).

     [안전]
     - 실제 개인정보/실제 링크/실제 계좌/전화번호는 사용·요구하지 말고, 필요 시 가상 표기만 사용.

     [종결 규칙(모델 판단)]
     - 아래 상황 중 하나라도 감지되면 **즉시** 다음 문구 **한 줄만** 출력하고 종료한다:
       1) 피해자가 이 대화를 보이스피싱/사기로 **인지·지목**함
       2) 피해자가 **신고/차단/대표번호 확인/지점 방문** 등 **강한 거부 의사**를 밝힘
       3) 너의 요구(이체/현금 전달/원격앱 설치/민감정보 제공 등)가 **완료되었다고 확인**됨
     - 그때 출력할 문구(정확히): **"여기서 마무리하겠습니다."**
     - 종결 규칙이 발동되면 [현재 단계]는 무시하고, 다른 말 없이 **해당 문구만** 출력한다.

     [현재 단계]
     {current_step}
     """),
    MessagesPlaceholder("history"),
    ("human",
     """
     마지막 피해자 발화(없으면 비어 있음):
     {last_victim}
     """)
])

# ─────────────────────────────────────────────────────────────
# 3) 피해자 프롬프트 (요청한 최소 버전)
# ─────────────────────────────────────────────────────────────
def render_victim_from_profile(victim_data: dict) -> dict:
    return {
        "meta": victim_data.get("meta", "정보 없음"),
        "knowledge": victim_data.get("knowledge", "정보 없음"),
        "traits": victim_data.get("traits", "정보 없음"),
    }

VICTIM_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     """
     이건 보이스피싱 시뮬레이션이고 너는 피해자의 역할이야.
     너의 캐릭터 시트를 줄테니 이걸 기반으로 보이스피싱 시뮬레이션을 진행해줘.

     [캐릭터 시트]
     메타정보: {meta}
     지식정보(리터러시): {knowledge}
     성격정보(OCEAN 일부 특성): {traits}

     [종료 규칙]
     - 공격자의 마지막 발화에 종료 선언(정확히 "여기서 마무리하겠습니다.")이 포함되면,
       너는 오직 한 줄로 "시뮬레이션을 종료합니다."라고만 말하고 즉시 종료한다.
     - 위 조건 외에는 **"여기서 마무리하겠습니다."라는 문구를 절대 말하지 않는다.**
     - 그 외의 문장, 설명, 메타 발화는 금지한다.
     """),
    MessagesPlaceholder("history"),
    ("human", "{last_offender}")
])