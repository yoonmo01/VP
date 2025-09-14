from __future__ import annotations

from sqlalchemy.orm import Session
from uuid import UUID
from app.db import models as m
from app.services.llm_providers import admin_chat  # ADMIN_MODEL 사용
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json, re

# =========================
# LLM 프롬프트 (전체 대화: 공격자+피해자)
# =========================
PROMPT_FULL_DIALOG = """
당신은 연구용 보이스피싱 분석가입니다.
아래 **전체 대화 로그(공격자+피해자)** 를 읽고, 피해 발생 여부와 위험도, 취약성, 다음 라운드 진행 권고를 **JSON으로만** 출력하세요.

[중요 전제]
- 대화가 아직 종료되지 않았을 수 있음. **현재까지의 로그만** 근거로 판정하고, 미래 상황은 가정하지 말 것.
- '공격자' 발화는 맥락 제공용이며, **판정은 결국 피해자의 실제 실행/확약/전달 발화가 핵심 증거**가 되어야 함.
- 아래 [판정 기준]과 [위험도 가이드]를 준수.

[판정 기준] (하나라도 충족 시 phishing=true)
A) **금전 이동 완료/직접 시도**
   - “송금/이체/입금/출금/인출/ATM/보관함(락커) 넣음/현금 전달/안전계좌” 등 **실제 금전 이동** 완료 또는 즉시 실행 단계
   - 신규·대환·카드론 등 **대출 실행** 후 금액을 범인 측에 전달
B) **민감 금융·인증 정보 제공**
   - 주민등록번호, 계좌번호, **통장 비밀번호**, 보안카드 번호, **OTP/인증번호**, 카드 CVC/유효기간, 공동/공동인증서 비밀번호 등 제공
C) **디지털 접근 허용(피싱 경유)**
   - **QR코드 접속**, **의심 링크 클릭**, **악성앱 설치/실행**, **원격제어 앱(AnyDesk/TeamViewer 등) 설치·승인**
D) **사칭에 따른 실행**
   - 가족·지인·수사기관·금융기관 사칭에 속아 **송금/인출/계좌·비밀번호 제공/앱 설치**가 발생

[phishing=false 판단] (모두 충족 시에만)
1. 위 A~D 이벤트가 **전혀 발생하지 않음**
2. 현재까지 **피해자 발화 기준**으로 금전 이동·민감정보 제공·앱/링크 실행이 **발생하지 않음**
3. 피해자가 대표번호 재확인/지점 방문/신고/거절/통화 종료 등으로 **명확히 방어**하고 이후 실행이 없음

[위험도 가이드] (risk.score ∈ [0,100], risk.level ∈ {{low, medium, high, critical}})
- critical(75~100): 금전 이동 완료/직접 시도, OTP·비번 등 핵심정보 제공, 원격제어 허용 등 **피해 실현/임박**
- high(50~74): 링크 클릭/QR·앱 설치 등 실행 전 단계가 복수 확인, 다수 설득 징후, 금전 이전 직전
- medium(25~49): 일부 흔들림(의심 링크 열람 시도 등)이나 설득 진행 중, 아직 핵심 실행 없음
- low(0~24): 일관된 방어/검증, 의심 시그널 탐지, 실행 징후 없음

[취약성(victim_vulnerabilities) 예시]
- “권위/긴급 호소에 취약”, “검증 없이 링크/QR 응답”, “금융 지식 부족”, “원격제어/앱 설치 거부 약함”, “개인정보 요구에 관대” 등
- 최대 3~6개, 간결한 문장형

[다음 라운드 진행 권고(continue)]
- {{\"recommendation\":\"continue\"|\"stop\",\"reason\":\"...\"}}
- 예: 위험도 높음/판정 true → \"stop\" 또는 \"continue\" (교육/추가 검증 목적에 따라), 판단 근거를 명확히 서술
- 본 시스템은 훈련 시뮬레이션이므로, 피드백/보호 조치를 위해 **합리적 권고**를 제시

[출력 형식] (아주 엄격)
- 오직 JSON 객체 1개만 출력(코드블록/설명/주석 금지)
- 최상위 키(정확히 5개): \"phishing\", \"evidence\", \"risk\", \"victim_vulnerabilities\", \"continue\"
- \"phishing\": true | false
- \"evidence\": 한 단락(2~4문장) 요약 + **핵심 발화 2~6개**를 turn_index와 역할을 함께 인용
  - 인용 예: turn 7 [피해자] \"700만원 송금했어요\", turn 10 [피해자] \"락커 24번에 넣었습니다\"
  - 큰따옴표는 반드시 \\\" 로 이스케이프할 것
- \"risk\": {{\"score\": 정수 0~100, \"level\": \"low\"|\"medium\"|\"high\"|\"critical\", \"rationale\": \"한 단락\"}}
- \"victim_vulnerabilities\": [문자열, ...] (3~6개)
- \"continue\": {{\"recommendation\":\"continue\"|\"stop\",\"reason\":\"한 단락\"}}
- **문자열 내부에서 \" 는 반드시 \\\" 로 이스케이프.** (어렵다면 『 』 사용 가능)

[참고 시나리오]
{scenario}

[대화 로그]
{dialog}
""".strip()

# =========================
# 포맷터 (라운드별 전체 대화)
# =========================
def _format_dialog_full_run(db: Session, case_id: UUID, run_no: int) -> str:
    rows = (
        db.query(m.ConversationLog)
        .filter(
            m.ConversationLog.case_id == case_id,
            m.ConversationLog.run == run_no,
        )
        .order_by(m.ConversationLog.turn_index.asc())
        .all()
    )
    if not rows:
        return ""
    out: List[str] = []
    for r in rows:
        role_ko = "공격자" if r.role == "offender" else "피해자"
        out.append(f"{r.turn_index} [{role_ko}] {r.content or ''}")
    return "\n".join(out)

def _scenario_string(db: Session, case_id: UUID) -> str:
    case = db.get(m.AdminCase, case_id)
    if not case:
        return ""
    scen = getattr(case, "scenario", None)
    if isinstance(scen, (dict, list)):
        return json.dumps(scen, ensure_ascii=False)
    return str(scen or "")

# ====== 공통 노이즈 제거/JSON 추출 ======
def _strip_code_fences(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()

def _normalize_quotes(s: str) -> str:
    return (
        s.replace("\u201c", '"').replace("\u201d", '"')
         .replace("\u2018", "'").replace("\u2019", "'")
    )

def _extract_json_with_balancing(s: str) -> str:
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
    pat = re.compile(rf'("{re.escape(key)}"\s*:\s*")(?P<val>.*)(")\s*(?=[,}}])', re.S)
    def _fix(m: re.Match) -> str:
        val = m.group("val")
        val_fixed = re.sub(r'(?<!\\)"', r'\\"', val)
        return m.group(1) + val_fixed + m.group(3)
    return pat.sub(_fix, text)

# =========================
# JSON 파서 (느슨, 새 스키마 대응)
# =========================
def _json_loads_lenient_full(s: str) -> Dict[str, Any]:
    s0 = _normalize_quotes(_strip_code_fences(s))
    raw = _extract_json_with_balancing(s0)

    def _sanitize(d: Dict[str, Any]) -> Dict[str, Any]:
        # 스키마 표준화
        phishing = bool(d.get("phishing", False))
        evidence = str(d.get("evidence", ""))

        risk = d.get("risk") or {}
        score = int(risk.get("score", 0))
        if score < 0: score = 0
        if score > 100: score = 100
        level = str(risk.get("level") or "")
        if level not in {"low", "medium", "high", "critical"}:
            # 레벨 자동 보정
            level = (
                "critical" if score >= 75 else
                "high"     if score >= 50 else
                "medium"   if score >= 25 else
                "low"
            )
        rationale = str(risk.get("rationale", ""))

        vul = d.get("victim_vulnerabilities") or d.get("vulnerabilities") or []
        if not isinstance(vul, list):
            vul = [str(vul)]
        vul = [str(x) for x in vul][:6]

        cont = d.get("continue") or {}
        rec  = cont.get("recommendation")
        if rec not in {"continue", "stop"}:
            # 기본값: 위험도 높으면 stop, 아니면 continue
            rec = "stop" if score >= 75 or phishing else "continue"
        reason = str(cont.get("reason", ""))

        return {
            "phishing": phishing,
            "evidence": evidence,
            "risk": {"score": score, "level": level, "rationale": rationale},
            "victim_vulnerabilities": vul,
            "continue": {"recommendation": rec, "reason": reason},
        }

    # 1차 그대로
    try:
        return _sanitize(json.loads(raw))
    except Exception:
        pass

    # 2차 최소 보정
    fixed_min = re.sub(r'(:\s*)0+(\d+)(\s*[,\}])', r': \2\3', raw)
    fixed_min = re.sub(r",(\s*[}\]])", r"\1", fixed_min)
    try:
        return _sanitize(json.loads(fixed_min))
    except Exception:
        pass

    # 3차 evidence 따옴표 보정
    fixed_esc = _escape_inner_quotes_for_value_of("evidence", fixed_min)
    try:
        return _sanitize(json.loads(fixed_esc))
    except Exception as e:
        raise ValueError(f"LLM JSON 파싱 실패: {e}\nRAW:\n{raw}\nFIXED:\n{fixed_esc}") from e

# =========================
# 메인: 라운드별 전체대화 판정 (LLM-only)
# =========================
def summarize_run_full(db: Session, case_id: UUID, run_no: int) -> Dict[str, Any]:
    scenario_str = _scenario_string(db, case_id)
    dialog = _format_dialog_full_run(db, case_id, run_no)

    if not dialog.strip():
        return {
            "phishing": False,
            "evidence": "해당 라운드에 대화가 없어 피해 여부를 판정할 수 없습니다.",
            "risk": {"score": 0, "level": "low", "rationale": "대화 없음"},
            "victim_vulnerabilities": [],
            "continue": {"recommendation": "continue", "reason": "분석할 대화가 없어 추가 수집 필요"},
        }

    llm = admin_chat()
    resp = llm.invoke(PROMPT_FULL_DIALOG.format(scenario=scenario_str, dialog=dialog)).content
    return _json_loads_lenient_full(resp)

# =========================
# (레거시) 케이스 단위 판정 - 전체 대화 사용
#   - simulation.py 등에서 기존 summarize_case(db, case_id)를 호출하므로
#     하위 호환 위해 케이스 전체(모든 run) 로그로 판정해 저장
# =========================
def summarize_case(db: Session, case_id: UUID):
    case = db.get(m.AdminCase, case_id)
    if case is None:
        raise ValueError(f"AdminCase {case_id} not found")

    # 케이스의 모든 run을 하나로 합쳐 전체 로그로 판단
    rows = (
        db.query(m.ConversationLog)
        .filter(m.ConversationLog.case_id == case_id)
        .order_by(m.ConversationLog.run.asc(), m.ConversationLog.turn_index.asc())
        .all()
    )
    if not rows:
        case.phishing = False
        case.evidence = "대화가 없어 피해 여부를 판정할 수 없음."
        case.defense_count = 0
        case.status = "completed"
        case.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(case)
        return {"phishing": False, "evidence": case.evidence, "defense_count": 0}

    # run 별 포맷과 동일한 문자열로 합치되, run 표시만 추가
    lines: List[str] = []
    for r in rows:
        role_ko = "공격자" if r.role == "offender" else "피해자"
        lines.append(f"run {r.run} :: {r.turn_index} [{role_ko}] {r.content or ''}")
    dialog = "\n".join(lines)
    scenario_str = _scenario_string(db, case_id)

    llm = admin_chat()
    resp = llm.invoke(PROMPT_FULL_DIALOG.format(scenario=scenario_str, dialog=dialog)).content
    parsed = _json_loads_lenient_full(resp)

    # LLM 결과 저장(케이스 단위)
    case.phishing = bool(parsed.get("phishing", False))
    case.evidence = str(parsed.get("evidence", ""))
    case.defense_count = 0
    case.status = "completed"
    case.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(case)

    return {"phishing": case.phishing, "evidence": case.evidence, "defense_count": 0}
