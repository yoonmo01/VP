# # app/services/admin_summary.py
# from __future__ import annotations

# from sqlalchemy.orm import Session
# from uuid import UUID
# from app.db import models as m
# from app.services.llm_providers import admin_chat    # o-시리즈 전용 분기(temperature=1) 적용
# from datetime import datetime, timezone
# import json, re, ast
# from typing import Any

# # =========================
# # LLM 프롬프트 (피해자 발화만 제공)
# # =========================
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
# 1. 위 A~D 이벤트가 **전혀 발생하지 않았음**
# 2. 현재까지 **피해자의 발화 기준**으로 금전 이동·민감정보 제공·앱/링크 실행이 **발생하지 않음**
# 3. 피해자가 대표번호 재확인/지점 방문/신고/거절/통화 종료 등으로 **명확히 방어**하고 이후 실행이 없음

# [출력 형식] (매우 엄격)
# - 오직 JSON 객체 1개만 출력(코드블록, 설명, 주석 금지)
# - 키는 정확히 2개: "phishing", "evidence"
# - 위 두 키 외의 어떤 키도 출력하지 말 것.
# - 키 순서는 ["phishing", "evidence"]
# - "phishing": true 또는 false
# - "evidence": 한 단락(2~4문장) 요약 + **핵심 발화 2~5개**를 turn_index와 함께 인용 (모두 피해자 발화)
#   - 인용 예: turn 7 "700만원 송금했어요", turn 10 "락커 24번에 넣었습니다", turn 5 "OTP 6자리 불러드릴게요"
# - 인용에서의 turn_index 표기는 항상 정수(1,2,3...)로 쓰고, 앞에 0을 붙이지 말 것(01, 03 금지).

# [참고 시나리오]
# 시나리오: {scenario}

# [대화 로그]
# {dialog}

# [출력 예시]
# {{"phishing": true, "evidence": "피해자 발화 기준, turn 7에서 '700만원 송금했어요', turn 10에서 '락커 24번에 넣었습니다' 등 금전 이동 완료가 확인됨. 또한 turn 5에서 OTP 제공 발화가 나타남."}}
# """.strip()

# # =========================
# # 대화 포맷터 (피해자 발화만)
# # =========================
# def _format_dialog_victim_only(db: Session, case_id: UUID) -> str:
#     """
#     DB의 대화 로그에서 '피해자' 발화만 판정용 평문으로 변환.
#     형식: 2 [피해자] ...내용...
#     """
#     logs = (
#         db.query(m.ConversationLog)
#         .filter(m.ConversationLog.case_id == case_id)
#         .order_by(m.ConversationLog.turn_index.asc())
#         .all()
#     )
#     lines: list[str] = []
#     for lg in logs:
#         if lg.role != "victim":
#             continue
#         lines.append(f"{lg.turn_index} [피해자] {lg.content}")  # 0패딩 제거 유지
#     return "\n".join(lines)

# # ====== 추가: JSON 블록 추출 + 괄호 자동 닫기 ======
# def _extract_json_with_balancing(s: str) -> str:
#     """
#     문자열 s에서 첫 '{'부터 시작하는 JSON 객체 블록을 탐색하면서
#     따옴표/이스케이프를 고려해 {}, [] 균형을 맞춰 끝까지 캡처.
#     끝까지 읽었는데도 스택이 남아있으면 필요한 닫는 괄호를 자동으로 붙여서 반환.
#     """
#     start = s.find("{")
#     if start == -1:
#         return s.strip()

#     stack = []
#     in_str = False
#     esc = False
#     end = None

#     for i in range(start, len(s)):
#         ch = s[i]
#         if in_str:
#             if esc:
#                 esc = False
#             elif ch == "\\":
#                 esc = True
#             elif ch == '"':
#                 in_str = False
#         else:
#             if ch == '"':
#                 in_str = True
#             elif ch == "{":
#                 stack.append("}")
#             elif ch == "[":
#                 stack.append("]")
#             elif ch in ("}", "]"):
#                 if stack and stack[-1] == ch:
#                     stack.pop()
#                     if not stack:
#                         end = i
#                         break

#     if end is not None:
#         return s[start:end + 1]

#     balanced = s[start:]
#     while stack:
#         balanced += stack.pop()
#     return balanced

# # =========================
# # JSON 파서 (느슨) — 교체 버전
# # =========================
# def _json_loads_lenient(s: str) -> dict[str, Any]:
#     """모델이 앞뒤에 텍스트를 붙였거나 일부 닫힘 괄호가 빠진 JSON도 최대한 복구해서 파싱."""
#     raw = _extract_json_with_balancing(s)

#     # 가벼운 전처리 및 보정
#     fixed = (raw
#              .replace("“", "\"").replace("”", "\"")
#              .replace("’", "'").replace("‘", "'"))
#     # "turn": 03 → 3 등 숫자 앞 0 제거
#     fixed = re.sub(r'(:\s*)0+(\d+)(\s*[,\}])', r': \2\3', fixed)
#     # 트레일링 콤마 제거: ,} 또는 ,] → } / ]
#     fixed = re.sub(r",(\s*[}\]])", r"\1", fixed)

#     # 1차: 표준 JSON
#     try:
#         return json.loads(fixed)
#     except json.JSONDecodeError:
#         pass

#     # 2차: 파이썬 리터럴로 백업 (true/false/null 보정)
#     py_like = re.sub(r'\btrue\b', 'True', fixed)
#     py_like = re.sub(r'\bfalse\b', 'False', py_like)
#     py_like = re.sub(r'\bnull\b', 'None', py_like)
#     try:
#         return ast.literal_eval(py_like)
#     except Exception as e:
#         raise ValueError(f"LLM JSON 파싱 실패: {e}\nRAW:\n{raw}\nFIXED:\n{fixed}") from e

# # =========================
# # 메인: 케이스 요약/판정 (LLM-only)
# # =========================
# def summarize_case(db: Session, case_id: UUID):
#     """
#     현재까지의 로그 중 **피해자 발화만** LLM에 전달하여 판정.
#     규칙 기반(정규식) 매칭 제거 → LLM 결과만 저장.
#     ADMIN_MODEL은 .env(예: o4-mini)로 제어.
#     """
#     case = db.get(m.AdminCase, case_id)
#     if case is None:
#         raise ValueError(f"AdminCase {case_id} not found")

#     # 시나리오 정규화
#     scenario_obj = case.scenario
#     scenario_str = json.dumps(scenario_obj, ensure_ascii=False) if isinstance(scenario_obj, (dict, list)) else str(scenario_obj or "")

#     # 피해자 발화만 사용
#     dialog = _format_dialog_victim_only(db, case_id)

#     # 피해자 발화가 전혀 없는 경우: 보수적 false로 마감
#     if not dialog.strip():
#         case.phishing = False
#         case.evidence = "피해자 발화가 없어 피해 발생을 확인할 수 없음."
#         case.defense_count = 0
#         case.status = "completed"
#         case.completed_at = datetime.now(timezone.utc)
#         db.commit(); db.refresh(case)
#         return {"phishing": False, "evidence": case.evidence, "defense_count": 0}

#     # LLM 호출 (피해자 발화만 전달)
#     llm = admin_chat()  # 내부에서 ADMIN_MODEL 사용
#     resp = llm.invoke(PROMPT_LLM_ONLY.format(scenario=scenario_str, dialog=dialog)).content

#     data = _json_loads_lenient(resp)
#     if "phishing" not in data or "evidence" not in data:
#         raise RuntimeError("LLM 응답에 'phishing' 또는 'evidence' 키가 없습니다.")

#     # LLM 결과 그대로 저장 (evidence는 문자열로 유지)
#     phishing = bool(data["phishing"])
#     evidence = str(data["evidence"] or "")

#     case.phishing = phishing
#     case.evidence = evidence
#     case.defense_count = 0
#     case.status = "completed"
#     case.completed_at = datetime.now(timezone.utc)
#     db.commit(); db.refresh(case)

#     return {"phishing": phishing, "evidence": evidence, "defense_count": 0}

# app/services/admin_summary.py
from __future__ import annotations

from sqlalchemy.orm import Session
from uuid import UUID
from app.db import models as m
from app.services.llm_providers import admin_chat  # o-시리즈 전용 분기(temperature=1) 적용
from datetime import datetime, timezone
import json, re
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
- **문자열 내부에서 큰따옴표 " 를 쓰면 반드시 \\" 로 이스케이프할 것.** (이스케이프가 어렵다면 『 』 로 인용)
- 인용에서의 turn_index 표기는 항상 정수(1,2,3...)로 쓰고, 앞에 0을 붙이지 말 것(01, 03 금지).

[참고 시나리오]
시나리오: {scenario}

[대화 로그]
{dialog}

[출력 예시]
{{"phishing": true, "evidence": "피해자 발화 기준, turn 7에서 \\"700만원 송금했어요\\", turn 10에서 \\"락커 24번에 넣었습니다\\" 등 금전 이동 완료가 확인됨. 또한 turn 5에서 OTP 제공 발화가 나타남."}}
""".strip()


# =========================
# 대화 포맷터 (피해자 발화만)
# =========================
def _format_dialog_victim_only(db: Session, case_id: UUID) -> str:
    """
    DB의 대화 로그에서 '피해자' 발화만 판정용 평문으로 변환.
    형식: 2 [피해자] ...내용...
    """
    logs = (db.query(m.ConversationLog).filter(
        m.ConversationLog.case_id == case_id).order_by(
            m.ConversationLog.turn_index.asc()).all())
    lines: list[str] = []
    for lg in logs:
        if lg.role != "victim":
            continue
        lines.append(f"{lg.turn_index} [피해자] {lg.content}")  # 0패딩 제거 유지
    return "\n".join(lines)


# ====== 유틸: 코드펜스/따옴표 정리, JSON 블록 추출, 필드 이스케이프 ======
def _strip_code_fences(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _normalize_quotes(s: str) -> str:
    # 스마트 따옴표 → ASCII
    return (s.replace("\u201c",
                      '"').replace("\u201d",
                                   '"').replace("\u2018",
                                                "'").replace("\u2019", "'"))


def _extract_json_with_balancing(s: str) -> str:
    """
    문자열 s에서 첫 '{'부터 시작하는 JSON 객체 블록을 탐색하면서
    따옴표/이스케이프를 고려해 {}, [] 균형을 맞춰 끝까지 캡처.
    끝까지 읽었는데도 스택이 남아있으면 필요한 닫는 괄호를 자동으로 붙여서 반환.
    """
    start = s.find("{")
    if start == -1:
        return s.strip()

    stack = []
    in_str = False
    esc = False
    end = None

    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                stack.append("}")
            elif ch == "[":
                stack.append("]")
            elif ch in ("}", "]"):
                if stack and stack[-1] == ch:
                    stack.pop()
                    if not stack:
                        end = i
                        break

    if end is not None:
        return s[start:end + 1]

    balanced = s[start:]
    while stack:
        balanced += stack.pop()
    return balanced


def _escape_inner_quotes_for_value_of(key: str, text: str) -> str:
    """
    text 안에서 "key": "...." 값을 찾아, 내부의 미-이스케이프된 " 를 \" 로 바꿔줌.
    이미 \\" 는 그대로 둔다.
    """
    pat = re.compile(
        rf'("{re.escape(key)}"\s*:\s*")(?P<val>.*)(")\s*(?=[,}}])', re.S)

    def _fix(m: re.Match) -> str:
        val = m.group("val")
        # 이미 이스케이프된 \" 는 유지하고 나머지 " 만 이스케이프
        val_fixed = re.sub(r'(?<!\\)"', r'\\"', val)
        return m.group(1) + val_fixed + m.group(3)

    return pat.sub(_fix, text)


# =========================
# JSON 파서 (느슨) — 강화 버전
# =========================
# === 교체: JSON 파서 (느슨) — 안전 우선/최소 보정 ===
def _json_loads_lenient(s: str) -> dict[str, Any]:
    """
    1) 코드펜스/스마트따옴표 정리 후, 객체 블록만 추출
    2) 먼저 '있는 그대로' json.loads 시도
       - 성공하면 스키마 화이트리스트로 불필요 키 제거 (citations 등 무시)
    3) 실패 시에만 최소 보정(숫자 0패딩/트레일링 콤마) → 재시도
    4) 그래도 실패하면 evidence 내부의 미-이스케이프 따옴표를 이스케이프 → 최종 시도
    """
    # 0) 주변 노이즈 제거 & 따옴표 정규화
    s0 = _normalize_quotes(_strip_code_fences(s))
    # 1) JSON 블록만 추출(괄호 균형 맞추기 포함)
    raw = _extract_json_with_balancing(s0)

    # --- 1차: 아무 보정 없이 그대로 파싱 시도 ---
    try:
        data = json.loads(raw)
        return {
            "phishing": bool(data.get("phishing", False)),
            "evidence": str(data.get("evidence", "")),
        }
    except Exception:
        pass  # 아래 단계로

    # --- 2차: 최소 보정 후 재시도 (따옴표는 건드리지 않음) ---
    fixed_min = raw
    # 숫자 앞 0 제거 (": 03," → ": 3,")
    fixed_min = re.sub(r'(:\s*)0+(\d+)(\s*[,\}])', r': \2\3', fixed_min)
    # 트레일링 콤마 제거
    fixed_min = re.sub(r",(\s*[}\]])", r"\1", fixed_min)

    try:
        data = json.loads(fixed_min)
        return {
            "phishing": bool(data.get("phishing", False)),
            "evidence": str(data.get("evidence", "")),
        }
    except Exception:
        pass  # 아래 단계로

    # --- 3차(최후): evidence 내부의 미-이스케이프 " 보정 후 재시도 ---
    fixed_esc = _escape_inner_quotes_for_value_of("evidence", fixed_min)
    try:
        data = json.loads(fixed_esc)
        return {
            "phishing": bool(data.get("phishing", False)),
            "evidence": str(data.get("evidence", "")),
        }
    except Exception as e:
        raise ValueError(
            f"LLM JSON 파싱 실패: {e}\nRAW:\n{raw}\nFIXED:\n{fixed_esc}") from e


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
    scenario_str = json.dumps(scenario_obj, ensure_ascii=False) if isinstance(
        scenario_obj, (dict, list)) else str(scenario_obj or "")

    # 피해자 발화만 사용
    dialog = _format_dialog_victim_only(db, case_id)

    # 피해자 발화가 전혀 없는 경우: 보수적 false로 마감
    if not dialog.strip():
        case.phishing = False
        case.evidence = "피해자 발화가 없어 피해 발생을 확인할 수 없음."
        case.defense_count = 0
        case.status = "completed"
        case.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(case)
        return {
            "phishing": False,
            "evidence": case.evidence,
            "defense_count": 0
        }

    # LLM 호출 (피해자 발화만 전달)
    llm = admin_chat()  # 내부에서 ADMIN_MODEL 사용
    resp = llm.invoke(
        PROMPT_LLM_ONLY.format(scenario=scenario_str, dialog=dialog)).content

    data = _json_loads_lenient(resp)
    data = {
        "phishing": bool(data.get("phishing", False)),
        "evidence": str(data.get("evidence", "")),
    }
    if "phishing" not in data or "evidence" not in data:
        raise RuntimeError("LLM 응답에 'phishing' 또는 'evidence' 키가 없습니다.")

    # LLM 결과 그대로 저장 (evidence는 문자열로 유지)
    phishing = bool(data["phishing"])
    evidence = str(data["evidence"] or "")

    case.phishing = phishing
    case.evidence = evidence
    case.defense_count = 0
    case.status = "completed"
    case.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(case)

    return {"phishing": phishing, "evidence": evidence, "defense_count": 0}
