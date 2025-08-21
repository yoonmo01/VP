<<<<<<< HEAD
# # prompt.py
# from __future__ import annotations

=======
# # from typing import Dict, Any, List
# # from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# # # ----------------------------------------
# # # 1) DB 레코드 → 프롬프트 변수 변환 함수
# # # ----------------------------------------
# # def render_attacker_from_offender(offender: Dict[str, Any]) -> Dict[str, str]:
# #     """
# #     DB에서 읽은 PhishingOffender 객체를 프롬프트에 맞게 변환
# #     """
# #     name = offender.get("name") or "시나리오"
# #     otype = offender.get("type") or "유형미상"
# #     prof = offender.get("profile") or {}
# #     purpose = prof.get("purpose") or "목적 미상"
# #     steps: List[str] = prof.get("steps") or []

# #     steps_bulleted = "\n".join(f"- {s}"
# #                                for s in steps) if steps else "- (단계 없음)"

# #     # 기본 시나리오 요약
# #     method_block = (f"[시나리오명] {name}\n"
# #                     f"[유형] {otype}\n"
# #                     f"[목적] {purpose}\n"
# #                     f"[단계]\n{steps_bulleted}")

# #     # 공격자 전술 가이드 – 세세화
# #     playbook_block = """
# # [플레이북 단계 가이드 – 세부 예시 포함]
# # 1) 오프닝(관심 끌기):
# #    - 가상의 기관명·부서명·직책으로 신뢰 확보 ("○○금융 본사 안전관리팀 김팀장입니다.")
# #    - 피해자의 상황과 연결된 사건 제시 ("귀하 계좌가 범죄 혐의 계좌와 연결되어 긴급 점검 중입니다.")
# #    - 대사 예시: "본사 전산에서 긴급 경고가 발생하여 바로 연락드렸습니다."

# # 2) 탐색(정보 확보):
# #    - 짧고 닫힌 질문으로 금융 현황 파악 ("현재 대출 보유 중이십니까?", "모바일뱅킹 가능하십니까?")
# #    - 피해자가 장황하게 설명하지 않도록 통제하며, 핵심 답변만 받기
# #    - 대사 예시: "네, 간단히만 답해주시면 됩니다. ○○은행 대출 잔액이 맞습니까?"

# # 3) 훅(Hook – 동기 부여):
# #    - 즉시성·한시성 강조 ("오늘만 처리 가능", "5분 내 미이행 시 불이익")
# #    - 손실회피 프레임 ("이 절차를 밟지 않으면 더 큰 피해가 발생")
# #    - 대사 예시: "오늘 안에만 안전계좌로 이체하셔야 피해를 막을 수 있습니다."

# # 4) 에스컬레이션(권위 이관):
# #    - 가상의 상위권위자 연결 시나리오 ("본사 전담 검사님께 연결해드리겠습니다.")
# #    - 피해자 확신 강화, 의심 완화
# #    - 대사 예시: "전담 검사님께서 직접 전산 확인 중입니다. 곧 연결됩니다."

# # 5) 캐시아웃(최종 행동 유도):
# #    - 가상 계좌/링크로 이체 또는 현금 인출 지시
# #    - 금액, 절차, 시간까지 구체적으로 안내
# #    - 대사 예시: "지금 ○○은행 앱 여시고, 가상계좌 000-0000-000000으로 200만 원 이체해주세요."
# # """

# #     rebuttal_block = """
# # [반박 대응 스니펫 – 확장판]
# # - "지점 방문할게요.": "지점은 현장 전산이 분리되어 있어 오늘 내 처리가 불가합니다. 본사 전산전용으로 5분이면 끝납니다."
# # - "대표번호로 확인할래요.": "대표번호로는 전산 보안 건이 조회되지 않습니다. 내부 전용 코드가 있어야 조회됩니다."
# # - "시간이 없어요.": "간편인증 두 번이면 끝납니다. 2분 내 처리 못 하면 내일로 넘기겠습니다."
# # - "사기 아니에요?": "의심하실 수 있습니다. 그래서 처리 전 가상 전자영수증을 발송드립니다."
# # - "생각해볼게요.": "지금 결정하셔야 안전합니다. 미이행 시 전산이 자동으로 혐의 이관됩니다."
# # """

# #     tone_block = """
# # [톤/전술 지침 – 세밀]
# # - 기본 톤: 침착·전문·단정, 그러나 필요시 약간의 긴급성 부여
# # - 문장은 짧고 지시형으로 ("지금 앱 여세요", "확인 버튼 누르세요")
# # - 긍정·안심 메시지와 압박을 교차 사용 ("다 해결됩니다" ↔ "시간이 없습니다")
# # - 매 턴 목표: (a) 다음 단계로 진입하거나 (b) 즉시 행동(이체/앱 실행) 유도
# # """

# #     return {
# #         "scenario_title": name,
# #         "method_block": method_block.strip(),
# #         "playbook_block": playbook_block.strip(),
# #         "rebuttal_block": rebuttal_block.strip(),
# #         "tone_block": tone_block.strip(),
# #         "profile_block": f"{otype} / 목적: {purpose}",
# #     }

# # # ----------------------------------------
# # # 2) 공격자 프롬프트 템플릿
# # #     - 매 턴 끝에는 피해자가 즉시 취할 수 있는 행동을 유도하는 지시를 1개 포함한다.
# # #  {playbook_block}

# # #  {rebuttal_block}

# # #  {tone_block}
# # # ----------------------------------------
# # ATTACKER_PROMPT = ChatPromptTemplate.from_messages([
# #     ("system", """
# #      너는 연구용 보이스피싱 시뮬레이션의 피싱범 역할이다.

# #      [안전 규칙]
# #      - 절대 실제 개인정보/실제 링크/실제 계좌/전화번호를 요구·노출하지 말 것
# #      - 항상 가상의 정보만 사용할 것 (예: example.com, 가상계좌 000-0000-000000, 가상 내선 0000)
# #      - 위반 소지가 있으면 즉시 가상 치환 표현으로 바꿀 것
# #      - 폭언/위협/혐오 표현 금지

# #     [멀티턴 규칙]
# #     - 15번의 턴 안에 피싱을 성공할 수 있게한다.
# #     - 각 턴은 2~4문장, 350자 이내로 간결하게 말한다.
# #     - 피해자가 강한 거부·단절·신고 의사를 보이면 즉시 "여기서 마무리하겠습니다."라고 말하고 종료한다.
# #     - 피해자가 의심·확인·지연 의사만 보이는 경우, 마지막 한 턴 동안만 설득 가능하다.
# #     그 후에도 거부나 의심이 반복되면 종료한다.

# #      [시나리오 개요]
# #      {method_block}

# #      [목표]
# #      - 플레이북 전술을 상황에 맞게 조합하여 피해자를 설득하라.
# #      - 캐시아웃 단계로 빠르게 도달하도록 구체 행동을 유도하라.
# #      - 모든 정보·절차는 가상의 것으로만 기술하라.

# #      [출력 형식]
# #      - 오직 공격자(너)의 대사 한 단락의 한국어 텍스트만 출력
# #      - 메타설명/내적독백/단계표/태그/JSON/코드블록 금지
# #      """),
# #     MessagesPlaceholder("history"),
# #     ("human", """
# #      마지막 피해자 발화(없으면 비어 있음):
# #      {last_victim}

# #      참고 프로필:
# #      {profile_block}

# #      참고: 시나리오 제목 = {scenario_title}
# #      """)
# # ])

# # def render_victim_from_profile(victim_data: dict) -> dict:
# #     """
# #     victim_data 예시:
# #     {
# #         "meta": "65세 은퇴자, 혼자 거주",
# #         "knowledge": "금융 리터러시 낮음, 디지털 기기 사용 미숙",
# #         "traits": "신중성 낮음, 친화성 높음"
# #     }
# #     """
# #     return {
# #         "meta": victim_data.get("meta", "정보 없음"),
# #         "knowledge": victim_data.get("knowledge", "정보 없음"),
# #         "traits": victim_data.get("traits", "정보 없음"),
# #     }

# # # 피해자 시스템 프롬프트 (메타/리터러시/성격 규칙)
# # VICTIM_PROMPT = ChatPromptTemplate.from_messages([
# #     ("system", """
# #      이건 보이스피싱 시뮬레이션이고 너는 피해자의 역할이야.
# #      너의 캐릭터 시트를 줄테니 이걸 기반으로 보이스피싱 시뮬레이션을 진행해줘.

# #      [캐릭터 시트]
# #      메타정보: {meta}
# #      지식정보(리터러시): {knowledge}
# #      성격정보(OCEAN 일부 특성): {traits}

# #      """),
# #     MessagesPlaceholder("history"), ("human", "{last_offender}")
# # ])
# # app/services/prompts.py
# from __future__ import annotations
>>>>>>> 52555a939ac73cb357aa6f730e327e7bb399769e
# from typing import Dict, Any, List
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# # ─────────────────────────────────────────────────────────────
<<<<<<< HEAD
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
=======
# # 1) (옵션) DB → 프롬프트 변수 변환
# #    - 이 프로젝트에선 공격자 쪽은 current_step로만 제어하므로
# #      render_attacker_from_offender는 써도 되고 안 써도 됩니다.
# # ─────────────────────────────────────────────────────────────
# def render_attacker_from_offender(offender: Dict[str, Any]) -> Dict[str, str]:
#     name = offender.get("name")
#     otype = offender.get("type")
#     prof = offender.get("profile") or {}
#     purpose = prof.get("purpose")
#     steps: List[str] = prof.get("steps") or []

#     lines: List[str] = []
#     if name: lines.append(f"[시나리오명] {name}")
#     if otype: lines.append(f"[유형] {otype}")
#     if purpose: lines.append(f"[목적] {purpose}")
>>>>>>> 52555a939ac73cb357aa6f730e327e7bb399769e
#     if steps:
#         lines.append("[단계]")
#         lines.extend(f"- {s}" for s in steps)

<<<<<<< HEAD
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
=======
#     return {
#         "scenario_title": name or "",
#         "method_block": "\n".join(lines).strip(),
#     }

# # ─────────────────────────────────────────────────────────────
# # 2) 공격자 프롬프트 (최소·Step-Lock)
# #    - 오직 현재 단계(current_step)와 마지막 피해자 발화만 사용
# # ─────────────────────────────────────────────────────────────
# ATTACKER_PROMPT = ChatPromptTemplate.from_messages([
#     ("system", """
#      너는 보이스피싱 시뮬레이션의 피싱범 역할이다.

#      [규칙]
#      - 오직 아래 [현재 단계]에 적힌 행동에 해당하는 대사만 말한다.
#      - 다른 단계의 내용, 새로운 사실(앱/기관/계좌/금액 등) 발명 금지.
#      - 문장 수 2~4, 350자 이내.
#      - 캐릭터 대사 한 단락만 출력(요약/해설/메타설명 금지).

#      [안전]
#      - 실제 개인정보/실제 링크/실제 계좌/전화번호는 사용·요구하지 말고, 필요 시 가상 표기만 사용.

#      [종결 규칙(모델 판단)]
#      - 아래 상황 중 하나라도 감지되면 **즉시** 다음 문구 **한 줄만** 출력하고 종료한다:
#        1) 피해자가 이 대화를 보이스피싱/사기로 **인지·지목**함
#        2) 피해자가 **신고/차단/대표번호 확인/지점 방문** 등 **강한 거부 의사**를 밝힘
#        3) 너의 요구(이체/현금 전달/원격앱 설치/민감정보 제공 등)가 **완료되었다고 확인**됨
#      - 그때 출력할 문구(정확히): **"여기서 마무리하겠습니다."**
#      - 종결 규칙이 발동되면 [현재 단계]는 무시하고, 다른 말 없이 **해당 문구만** 출력한다.

#      [현재 단계]
#      {current_step}
#      """),
#     MessagesPlaceholder("history"),
#     ("human", """
#      마지막 피해자 발화(없으면 비어 있음):
#      {last_victim}
>>>>>>> 52555a939ac73cb357aa6f730e327e7bb399769e
#      """)
# ])

# # ─────────────────────────────────────────────────────────────
<<<<<<< HEAD
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
=======
# # 3) 피해자 프롬프트 (요청한 최소 버전)
# # ─────────────────────────────────────────────────────────────
# def render_victim_from_profile(victim_data: dict) -> dict:
>>>>>>> 52555a939ac73cb357aa6f730e327e7bb399769e
#     return {
#         "meta": victim_data.get("meta", "정보 없음"),
#         "knowledge": victim_data.get("knowledge", "정보 없음"),
#         "traits": victim_data.get("traits", "정보 없음"),
#     }

# VICTIM_PROMPT = ChatPromptTemplate.from_messages([
<<<<<<< HEAD
#     ("system",
#      """
=======
#     ("system", """
>>>>>>> 52555a939ac73cb357aa6f730e327e7bb399769e
#      이건 보이스피싱 시뮬레이션이고 너는 피해자의 역할이야.
#      너의 캐릭터 시트를 줄테니 이걸 기반으로 보이스피싱 시뮬레이션을 진행해줘.

#      [캐릭터 시트]
#      메타정보: {meta}
#      지식정보(리터러시): {knowledge}
#      성격정보(OCEAN 일부 특성): {traits}

#      [종료 규칙]
<<<<<<< HEAD
#      - 공격자의 마지막 발화에 종료 선언(예: "여기서 마무리하겠습니다.")이 포함되면,
#        너는 오직 한 줄로 "시뮬레이션을 종료합니다."라고만 말하고 즉시 종료한다.
#        그 외의 문장, 설명, 메타 발화는 금지한다.
#      """),
#     MessagesPlaceholder("history"),
#     ("human", "{last_offender}")
# ])
# app/services/prompts.py
=======
#      - 공격자의 마지막 발화에 종료 선언(정확히 "여기서 마무리하겠습니다.")이 포함되면,
#        너는 오직 한 줄로 "시뮬레이션을 종료합니다."라고만 말하고 즉시 종료한다.
#      - 위 조건 외에는 **"여기서 마무리하겠습니다."라는 문구를 절대 말하지 않는다.**
#      - 그 외의 문장, 설명, 메타 발화는 금지한다.
#      """),
#     MessagesPlaceholder("history"), ("human", "{last_offender}")
# ])
>>>>>>> 52555a939ac73cb357aa6f730e327e7bb399769e
from __future__ import annotations
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

<<<<<<< HEAD
# ─────────────────────────────────────────────────────────────
# 1) (옵션) DB → 프롬프트 변수 변환
#    - 이 프로젝트에선 공격자 쪽은 current_step로만 제어하므로
#      render_attacker_from_offender는 써도 되고 안 써도 됩니다.
=======

# ─────────────────────────────────────────────────────────────
# 1) (옵션) DB → 프롬프트 변수 변환
>>>>>>> 52555a939ac73cb357aa6f730e327e7bb399769e
# ─────────────────────────────────────────────────────────────
def render_attacker_from_offender(offender: Dict[str, Any]) -> Dict[str, str]:
    name = offender.get("name")
    otype = offender.get("type")
    prof = offender.get("profile") or {}
    purpose = prof.get("purpose")
    steps: List[str] = prof.get("steps") or []

    lines: List[str] = []
<<<<<<< HEAD
    if name:   lines.append(f"[시나리오명] {name}")
    if otype:  lines.append(f"[유형] {otype}")
    if purpose:lines.append(f"[목적] {purpose}")
=======
    if name: lines.append(f"[시나리오명] {name}")
    if otype: lines.append(f"[유형] {otype}")
    if purpose: lines.append(f"[목적] {purpose}")
>>>>>>> 52555a939ac73cb357aa6f730e327e7bb399769e
    if steps:
        lines.append("[단계]")
        lines.extend(f"- {s}" for s in steps)

    return {
        "scenario_title": name or "",
        "method_block": "\n".join(lines).strip(),
    }

<<<<<<< HEAD
# ─────────────────────────────────────────────────────────────
# 2) 공격자 프롬프트 (최소·Step-Lock)
#    - 오직 현재 단계(current_step)와 마지막 피해자 발화만 사용
# ─────────────────────────────────────────────────────────────
ATTACKER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     """
=======

# ─────────────────────────────────────────────────────────────
# 2) 공격자 프롬프트 (지침 주입 지원)
#    - current_step 기준으로 말하되, guidance가 있으면 반드시 반영
# ─────────────────────────────────────────────────────────────
ATTACKER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """
>>>>>>> 52555a939ac73cb357aa6f730e327e7bb399769e
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
     [현재 단계]
     {current_step}
<<<<<<< HEAD
=======

     [지침(있으면 반드시 반영)]
     - 유형: {guidance_type}
     - 내용: {guidance}
     - 지침이 비어 있거나 제공되지 않았다면 이 섹션은 무시한다.
     - 지침이 있으면 현재 단계의 표현·전략·어휘 선택에 적극적으로 반영한다.
>>>>>>> 52555a939ac73cb357aa6f730e327e7bb399769e
     """),
    MessagesPlaceholder("history"),
    ("human", """
     마지막 피해자 발화(없으면 비어 있음):
     {last_victim}
     """)
])

<<<<<<< HEAD
# ─────────────────────────────────────────────────────────────
# 3) 피해자 프롬프트 (요청한 최소 버전)
=======

# ─────────────────────────────────────────────────────────────
# 3) 피해자 프롬프트 (지침 참조 가능, 없으면 무시)
>>>>>>> 52555a939ac73cb357aa6f730e327e7bb399769e
# ─────────────────────────────────────────────────────────────
def render_victim_from_profile(victim_data: dict) -> dict:
    return {
        "meta": victim_data.get("meta", "정보 없음"),
        "knowledge": victim_data.get("knowledge", "정보 없음"),
        "traits": victim_data.get("traits", "정보 없음"),
    }

<<<<<<< HEAD
=======

>>>>>>> 52555a939ac73cb357aa6f730e327e7bb399769e
VICTIM_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """
     이건 보이스피싱 시뮬레이션이고 너는 피해자의 역할이야.
     너의 캐릭터 시트를 줄테니 이걸 기반으로 보이스피싱 시뮬레이션을 진행해줘.

     [캐릭터 시트]
     메타정보: {meta}
     지식정보(리터러시): {knowledge}
     성격정보(OCEAN 일부 특성): {traits}

<<<<<<< HEAD
=======
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
