# # app/services/admin_summary.py
# from __future__ import annotations

# from sqlalchemy.orm import Session
# from uuid import UUID
# from app.db import models as m
# from app.services.llm_providers import openai_chat  # ADMIN_MODEL은 .env로 지정
# from datetime import datetime, timezone
# import json, re, ast
# from typing import Any

# PROMPT_LLM_ONLY = """
# 당신은 연구용 보이스피싱 분석가입니다.
# 아래 대화 로그를 읽고, 보이스피싱 피해 발생 여부와 그 근거를 **JSON으로만** 출력하세요.

# [중요 전제]
# - 대화가 아직 종료되지 않았을 수 있음. **현재까지의 로그만** 근거로 판정하고, 미래 상황은 가정하지 말 것.
# - **아래 로그에는 '피해자'의 발화만 제공된다. 오직 피해자의 실제 행동/확인 발화(송금·인출·앱 설치·링크/QR 접속·민감정보 제공 등)만으로 판정할 것.**
# - 애매하면 보수적으로 보되, 아래의 **완료/고위험 행위**가 하나라도 확인되면 `phishing=true`.

# [판정 기준] (하나라도 충족 시 phishing=true)
# A) **금전 이동 완료/직접 시도**
#    - “송금/이체/입금/출금/인출/ATM에서 찾음/락커(보관함)에 넣음/현금 전달/자동이체/강제출금/안전계좌” 등 **실제 금전 이동**이 완료 또는 즉시 실행 단계
#    - 신규·대환·카드론 등 **대출 실행** 후 금액을 범인 측에 전달
# B) **민감한 금융·인증 정보 제공**
#    - 주민등록번호, 계좌번호, **통장 비밀번호**, 보안카드 번호, **OTP/인증번호**, 카드 CVC/유효기간 등 제공
# C) **디지털 접근 허용(피싱 경유)**
#    - **QR코드 접속**, **피싱 링크 클릭**, **악성앱 설치/실행**, **원격제어 앱(예: AnyDesk/TeamViewer 등) 설치·승인**
# D) **지인/기관 사칭에 따른 실행**
#    - 가족·지인·수사기관·금융기관 사칭에 속아 **송금/인출/계좌·비밀번호 제공/앱 설치**가 발생

# [phishing=false 판단] (모든 항목 충족 시에만)
# - 위 A~D 신호가 **전혀 없고**, 현재까지 **피해자의 발화 기준**으로 금전 이동·민감정보 제공·앱/링크 실행이 **발생하지 않음**
# - 피해자가 대표번호 재확인/지점 방문/신고/거절/통화 종료 등으로 **명확히 방어**하고 이후 실행이 없음

# [출력 형식] (매우 엄격)
# - 오직 JSON 객체 1개만 출력(코드블록, 설명, 주석 금지)
# - 키는 정확히 2개: "phishing", "evidence"
# - 키 순서는 ["phishing", "evidence"]
# - "phishing": true 또는 false
# - "evidence": 한 단락(2~4문장) 요약 + **핵심 발화 2~5개**를 turn_index와 함께 인용 (모두 피해자 발화)
#   - 인용 예: turn 07 "700만원 송금했어요", turn 10 "락커 24번에 넣었습니다", turn 05 "OTP 6자리 불러드릴게요"

# [참고 시나리오]
# 시나리오: {scenario}

# [대화 로그]
# {dialog}

# [출력 예시]
# {{"phishing": true, "evidence": "피해자 발화 기준, turn 07에서 '700만원 송금했어요', turn 10에서 '락커 24번에 넣었습니다' 등 금전 이동 완료가 확인됨. 또한 turn 05에서 OTP 제공 발화가 나타남."}}
# """.strip()


# def _format_dialog_victim_only(db: Session, case_id: UUID) -> str:
#     """
#     DB의 대화 로그에서 '피해자' 발화만 판정용 평문으로 변환.
#     형식: 02 [피해자] ...내용...
#     """
#     logs = (
#         db.query(m.ConversationLog)
#         .filter(m.ConversationLog.case_id == case_id)
#         .order_by(m.ConversationLog.turn_index.asc())
#         .all()
#     )
#     lines = []
#     for lg in logs:
#         if lg.role != "victim":
#             continue
#         lines.append(f"{lg.turn_index:02d} [피해자] {lg.content}")
#     return "\n".join(lines)


# def _json_loads_lenient(s: str) -> dict[str, Any]:
#     """모델이 앞뒤에 텍스트를 붙였을 경우에도 JSON 블록만 안전하게 파싱."""
#     mobj = re.search(r"\{[\s\S]*\}", s)
#     raw = mobj.group(0) if mobj else s
#     try:
#         return json.loads(raw)
#     except json.JSONDecodeError:
#         # 마지막 안전장치
#         return ast.literal_eval(raw)


# # ── 보정용: 피해자 발화에서 '완료/고위험' 신호 직접 감지 (LLM이 놓칠 때 승격)
# _MONEY_DONE_PATTERNS = [
#     r"송금(했|완료|했습니다)", r"이체(했|완료|했습니다)", r"입금(했|완료|했습니다)",
#     r"출금(했|완료|했습니다)", r"인출(했|완료|했습니다)", r"ATM.*(찾았|인출)",
#     r"(락커|보관함).*(넣었|보관|입금)", r"(현금|돈).*(전달했|건넸|넘겼)",
#     r"(보냈[어요]|보냈습니다)"
# ]
# _SENSITIVE_INFO_PATTERNS = [
#     r"(통장\s*비밀번호|비밀번호).*불러", r"OTP|인증번호|보안카드", r"카드.*(CVC|유효기간)",
#     r"주민등록번호", r"계좌번호"
# ]
# _DIGITAL_ACCESS_PATTERNS = [
#     r"QR\s*코드.*(찍|스캔|접속|들어갔)", r"(링크|주소).*(눌렀|들어갔|접속)",
#     r"(앱|어플).*(설치|깔았|실행했)", r"(원격|리모트).*(앱|프로그램).*(설치|승인|연결)",
#     r"(AnyDesk|TeamViewer|팀뷰어)"
# ]

# def _has_victim_highrisk(dialog: str) -> bool:
#     for line in dialog.splitlines():
#         if any(re.search(p, line) for p in _MONEY_DONE_PATTERNS):
#             return True
#         if any(re.search(p, line, re.IGNORECASE) for p in _SENSITIVE_INFO_PATTERNS):
#             return True
#         if any(re.search(p, line, re.IGNORECASE) for p in _DIGITAL_ACCESS_PATTERNS):
#             return True
#     return False


# def summarize_case(db: Session, case_id: UUID):
#     """
#     대화가 끝났든 말든 '현재까지의 로그' 중 **피해자 발화만**으로 LLM 판정.
#     ADMIN_MODEL은 .env(예: gpt-4o)로 제어.
#     """
#     case = db.get(m.AdminCase, case_id)
#     if case is None:
#         raise ValueError(f"AdminCase {case_id} not found")

#     # 시나리오 정규화
#     scenario_obj = case.scenario
#     scenario_str = json.dumps(scenario_obj, ensure_ascii=False) if isinstance(scenario_obj, (dict, list)) else str(scenario_obj or "")

#     # 피해자 발화만 사용
#     dialog = _format_dialog_victim_only(db, case_id)

#     # 🔸 피해자 발화가 전혀 없는 경우: 보수적 false로 마감
#     if not dialog.strip():
#         case.phishing = False
#         case.evidence = "피해자 발화가 없어 피해 발생을 확인할 수 없음."
#         case.defense_count = 0
#         case.status = "completed"
#         case.completed_at = datetime.now(timezone.utc)
#         db.commit(); db.refresh(case)
#         return {"phishing": False, "evidence": case.evidence, "defense_count": 0}

#     # 🔹 LLM 호출 (피해자 발화만 전달)
#     llm = openai_chat()  # 내부에서 ADMIN_MODEL 사용
#     resp = llm.invoke(PROMPT_LLM_ONLY.format(scenario=scenario_str, dialog=dialog)).content

#     data = _json_loads_lenient(resp)
#     if "phishing" not in data or "evidence" not in data:
#         raise RuntimeError("LLM 응답에 'phishing' 또는 'evidence' 키가 없습니다.")

#     phishing = bool(data["phishing"])
#     evidence = str(data["evidence"] or "")

#     # ★ 보정: 피해자 발화 내 완료/고위험 신호가 있으면 무조건 true로 승격
#     if not phishing and _has_victim_highrisk(dialog):
#         phishing = True
#         if not evidence.strip():
#             evidence = "피해자 발화에서 금전 이동/민감정보 제공/앱·링크 실행 등 완료·고위험 신호가 확인됨."

#     # 메타(방어 횟수 등)는 룰기반 미사용 → 0
#     case.phishing = phishing
#     case.evidence = evidence
#     case.defense_count = 0
#     case.status = "completed"              # 항상 완료로 닫아줌
#     case.completed_at = datetime.now(timezone.utc)
#     db.commit(); db.refresh(case)

#     return {"phishing": phishing, "evidence": evidence, "defense_count": 0}


# app/services/admin_summary.py
from __future__ import annotations

from sqlalchemy.orm import Session
from uuid import UUID
from app.db import models as m
from app.services.llm_providers import admin_chat    # o-시리즈 전용 분기(temperature=1) 적용
from datetime import datetime, timezone
import json, re, ast
from typing import Any


# =========================
# LLM 프롬프트 (피해자 발화만 제공)
# =========================
PROMPT_LLM_ONLY = """
당신은 연구용 보이스피싱 분석가입니다.
아래 대화 로그를 읽고, 보이스피싱 피해 발생 여부와 그 근거를 **JSON으로만** 출력하세요.

[중요 전제]
- 대화가 아직 종료되지 않았을 수 있음. **현재까지의 로그만** 근거로 판정하고, 미래 상황은 가정하지 말 것.
- **아래 로그에는 '피해자'의 발화만 제공된다. 오직 피해자의 실제 행동/확인 발화(송금·인출·앱 설치·링크/QR 접속·민감정보 제공 등)만으로 판정할 것.**
- 애매하면 보수적으로 보되, 아래의 **완료/고위험 행위**가 하나라도 확인되면 `phishing=true`.

[판정 기준] (하나라도 충족 시 phishing=true)
A) **금전 이동 완료/직접 시도**
   - “송금/이체/입금/출금/인출/ATM에서 찾음/락커(보관함)에 넣음/현금 전달/자동이체/강제출금/안전계좌” 등 **실제 금전 이동**이 완료 또는 즉시 실행 단계
   - 신규·대환·카드론 등 **대출 실행** 후 금액을 범인 측에 전달
B) **민감한 금융·인증 정보 제공**
   - 주민등록번호, 계좌번호, **통장 비밀번호**, 보안카드 번호, **OTP/인증번호**, 카드 CVC/유효기간 등 제공
C) **디지털 접근 허용(피싱 경유)**
   - **QR코드 접속**, **피싱 링크 클릭**, **악성앱 설치/실행**, **원격제어 앱(예: AnyDesk/TeamViewer 등) 설치·승인**
D) **지인/기관 사칭에 따른 실행**
   - 가족·지인·수사기관·금융기관 사칭에 속아 **송금/인출/계좌·비밀번호 제공/앱 설치**가 발생

[phishing=false 판단] (모든 항목 충족 시에만)
1. 위 A~D 이벤트가 **전혀 발생하지 않았음**
2. 현재까지 **피해자의 발화 기준**으로 금전 이동·민감정보 제공·앱/링크 실행이 **발생하지 않음**
3. 피해자가 대표번호 재확인/지점 방문/신고/거절/통화 종료 등으로 **명확히 방어**하고 이후 실행이 없음

[출력 형식] (매우 엄격)
- 오직 JSON 객체 1개만 출력(코드블록, 설명, 주석 금지)
- 키는 정확히 2개: "phishing", "evidence"
- 위 두 키 외의 어떤 키도 출력하지 말 것.
- 키 순서는 ["phishing", "evidence"]
- "phishing": true 또는 false
- "evidence": 한 단락(2~4문장) 요약 + **핵심 발화 2~5개**를 turn_index와 함께 인용 (모두 피해자 발화)
  - 인용 예: turn 7 "700만원 송금했어요", turn 10 "락커 24번에 넣었습니다", turn 5 "OTP 6자리 불러드릴게요"
- 인용에서의 turn_index 표기는 항상 정수(1,2,3...)로 쓰고, 앞에 0을 붙이지 말 것(01, 03 금지).

[참고 시나리오]
시나리오: {scenario}

[대화 로그]
{dialog}

[출력 예시]
{{"phishing": true, "evidence": "피해자 발화 기준, turn 7에서 '700만원 송금했어요', turn 10에서 '락커 24번에 넣었습니다' 등 금전 이동 완료가 확인됨. 또한 turn 5에서 OTP 제공 발화가 나타남."}}
""".strip()


# =========================
# 대화 포맷터 (피해자 발화만)
# =========================
def _format_dialog_victim_only(db: Session, case_id: UUID) -> str:
    """
    DB의 대화 로그에서 '피해자' 발화만 판정용 평문으로 변환.
    형식: 2 [피해자] ...내용...
    """
    logs = (
        db.query(m.ConversationLog)
        .filter(m.ConversationLog.case_id == case_id)
        .order_by(m.ConversationLog.turn_index.asc())
        .all()
    )
    lines: list[str] = []
    for lg in logs:
        if lg.role != "victim":
            continue
        lines.append(f"{lg.turn_index:02d} [피해자] {lg.content}")
    return "\n".join(lines)


# =========================
# JSON 파서 (느슨)
# =========================
def _json_loads_lenient(s: str) -> dict[str, Any]:
    """모델이 앞뒤에 텍스트를 붙였을 경우에도 JSON 블록만 안전하게 파싱."""
    mobj = re.search(r"\{[\s\S]*\}", s)
    raw = mobj.group(0) if mobj else s
    
    # 예비 보정: "turn": 03 → "turn": 3 (혹시 등장할 경우 대비용)
    # 다른 숫자 필드에도 안전하게 동작 (키 이름 제한하지 않음)
    fixed = re.sub(r'(:\s*)0+(\d+)(\s*[,\}])', r': \2\3', raw)
    
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 마지막 안전장치
        return ast.literal_eval(raw)


# =========================
# 메인: 케이스 요약/판정 (LLM-only)
# =========================
def summarize_case(db: Session, case_id: UUID):
    """
    현재까지의 로그 중 **피해자 발화만** LLM에 전달하여 판정.
    규칙 기반(정규식) 매칭 제거 → LLM 결과만 저장.
    ADMIN_MODEL은 .env(예: o4-mini)로 제어.
    """
    case = db.get(m.AdminCase, case_id)
    if case is None:
        raise ValueError(f"AdminCase {case_id} not found")

    # 시나리오 정규화
    scenario_obj = case.scenario
    scenario_str = json.dumps(scenario_obj, ensure_ascii=False) if isinstance(scenario_obj, (dict, list)) else str(scenario_obj or "")

    # 피해자 발화만 사용
    dialog = _format_dialog_victim_only(db, case_id)

    # 피해자 발화가 전혀 없는 경우: 보수적 false로 마감
    if not dialog.strip():
        case.phishing = False
        case.evidence = "피해자 발화가 없어 피해 발생을 확인할 수 없음."
        case.defense_count = 0
        case.status = "completed"
        case.completed_at = datetime.now(timezone.utc)
        db.commit(); db.refresh(case)
        return {"phishing": False, "evidence": case.evidence, "defense_count": 0}

    # LLM 호출 (피해자 발화만 전달)
    llm = admin_chat()  # 내부에서 ADMIN_MODEL 사용
    resp = llm.invoke(PROMPT_LLM_ONLY.format(scenario=scenario_str, dialog=dialog)).content

    data = _json_loads_lenient(resp)
    if "phishing" not in data or "evidence" not in data:
        raise RuntimeError("LLM 응답에 'phishing' 또는 'evidence' 키가 없습니다.")

    # LLM 결과 그대로 저장
    phishing = bool(data["phishing"])
    evidence = str(data["evidence"] or "")

    case.phishing = phishing
    case.evidence = evidence
    case.defense_count = 0
    case.status = "completed"
    case.completed_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(case)

    return {"phishing": phishing, "evidence": evidence, "defense_count": 0}
