from sqlalchemy.orm import Session
from uuid import UUID
from typing import Tuple
from app.db import models as m
from app.services.llm_providers import openai_chat  # (지금은 관리자도 GPT)
from datetime import datetime, timezone
import os
import re
import json
import ast

# -------------------- LLM 프롬프트 (수정) --------------------
PROMPT = """
당신은 연구용 보이스피싱 분석가입니다.
[출력 규칙] (엄격)
- 한국어로 작성.
- 오직 JSON만 출력. JSON 앞뒤에 불필요한 텍스트/해설/코드블록/주석 금지.
- 반드시 두 개의 키만 포함: phishing, evidence
- 키 순서는 ["phishing", "evidence"]
- evidence는 한 단락(2~4문장)으로 요약, 핵심 발화는 turn_index와 함께 2~5개 인용.

[판정 기준] (매우 중요)
- phishing=true : 아래 중 하나 이상이 [대화의 후반부/최종]에 실제로 발생했을 때만 true
  1) 금전 송금/이체 완료, 현금 인출 및 보관함 투입
  2) 대출 실행(신규·대환) 완료
  3) 자동이체/강제출금 등으로 실제 금전 이동이 발생했음이 명시적으로 확인
- 단독으로 true가 되지 않음(보조 증거만):
  - 주민번호/이름/전화번호 등 PII 제공
  - OTP/인증번호 전달·입력
  - ‘검사/긴급/전용계좌/가상계좌/안전관리’ 등 위협·유도 표현
- 최종상태 우선:
  - 마지막 구간에서 ‘대표번호 재확인/지점 방문/신고/거절/통화 종료’ 등 방어가 명확하고,
    그 이후 금전행위가 없다면 phishing=false.

[시나리오]
{scenario}

[대화 로그]
{dialog}

[출력 예시]
{{"phishing": true, "evidence": "피해자가 200만원 송금을 완료했고, turn_index 05, 08, 09, 10에서 금전 전달 발화가 명확히 나타남"}}
""".strip()


def _format_dialog(db: Session, case_id: UUID) -> str:
    logs = (
        db.query(m.ConversationLog)
        .filter(m.ConversationLog.case_id == case_id)
        .order_by(m.ConversationLog.turn_index.asc())
        .all()
    )
    lines = []
    for lg in logs:
        who = "[피싱범]" if lg.role == "offender" else "[피해자]"
        lines.append(f"{lg.turn_index:02d} {who} {lg.content}")
    return "\n".join(lines)


# -------------------- 강한 ‘완료’/‘방어’ 신호 정의 (수정) --------------------
COMPLETE_STRONG_PATTERNS = [
    r"(송금|이체|입금)\s*(완료|했[어요]?|했습니다|처리했)",
    r"(현금|돈)\s*(전부|다)?\s*인출(했[어요]?|했습니다)",
    r"(보관함|락커)\s*(에|에다)\s*(넣었|두었|보관했)",
    r"\b\d[\d,\.]*\s*(원|만원|억)\b.*(송금|이체|입금|인출)"
]
COMPLETE_RXS = [re.compile(p, re.IGNORECASE) for p in COMPLETE_STRONG_PATTERNS]

DEFENSE_STRONG_PATTERNS = [
    r"(대표번호|공식\s*번호|콜\s*백|다시\s*전화|번호\s*확인|지점\s*방문)",
    r"(신고|경찰|사이버수사대|금융감독원|금감원)",
    r"(송금|이체|인출|계좌)\s*(안|못)\s*하겠|거절|불가|의심",
    r"(끊겠|끊을게|통화\s*그만|종료|마무리하겠습니다)"
]
DEFENSE_RXS = [re.compile(p, re.IGNORECASE) for p in DEFENSE_STRONG_PATTERNS]

LINE_RX = re.compile(r"^(\d+)\s\[(피싱범|피해자)\]\s(.+)$", re.M)


def _scan_dialog(dialog: str):
    """
    대화에서 피해자 발화만 스캔하여 강한 완료/방어 신호 turn_index 목록과
    근거로 쓸 샘플 텍스트 일부를 반환.
    """
    completes, defenses = [], []
    complete_samples, defense_samples = [], []
    for m in LINE_RX.finditer(dialog):
        idx = int(m.group(1))
        role = m.group(2)
        text = m.group(3)
        if role != "피해자":
            continue
        if any(rx.search(text) for rx in COMPLETE_RXS):
            completes.append(idx)
            if len(complete_samples) < 5:
                complete_samples.append((idx, text))
        if any(rx.search(text) for rx in DEFENSE_RXS):
            defenses.append(idx)
            if len(defense_samples) < 5:
                defense_samples.append((idx, text))
    return completes, defenses, complete_samples, defense_samples


def _rule_based(dialog: str) -> Tuple[bool, str]:
    """
    최종상태 우선 원칙:
      - 마지막 방어 turn 이후에 강한 완료가 없으면 False
      - 강한 완료가 1회 이상이면 True
      - 그 외는 False(보수적으로 피해 미확정)
    """
    completes, defenses, complete_samples, defense_samples = _scan_dialog(dialog)
    last_complete = max(completes) if completes else -1
    last_defense  = max(defenses)  if defenses  else -1

    # 마지막 방어가 더 늦고 이후 금전 행위가 없다면 False
    if last_defense > last_complete:
        ev = f"최종 방어 인식: turn {last_defense} 이후 금전행위 없음"
        if defense_samples:
            quotes = "; ".join([f"{i:02d} \"{t[:60]}\"" for i, t in defense_samples])
            ev += f" | 방어 인용: {quotes}"
        return False, ev

    # 강한 금전 완료 신호가 있으면 True
    if last_complete >= 0:
        ev = f"금전행위 완료 인식: turn {last_complete}"
        if complete_samples:
            quotes = "; ".join([f"{i:02d} \"{t[:60]}\"" for i, t in complete_samples])
            ev += f" | 완료 인용: {quotes}"
        return True, ev

    # 아무 강한 신호도 없으면 False
    return False, "금전행위 완료 신호 없음(보수적 판정)"


# -------------------- 방어 횟수 계산(케이스 메타 저장용, 기존 로직 보강) --------------------
DEFENSE_PATTERNS = [
    r"(공식|은행|경찰|검찰)\s*(대표번호|콜센터|번호|방문)",
    r"(검색|조회|확인)\s*(해볼게|해보겠습니다|먼저)",
    r"(링크|앱)\s*(안|못)\s*열|설치\s*(안|못)하",
    r"(계좌|현금|송금)\s*(안|못)\s*하겠|거절|불가|의심",
    r"(콜백|다시 전화|번호 확인)",
]
DEFENSE_REGEXES = [re.compile(p, re.IGNORECASE) for p in DEFENSE_PATTERNS]

def _count_defenses(dialog_text: str) -> int:
    cnt = 0
    for line in dialog_text.splitlines():
        if "[피해자]" in line:
            text = line.split("] ", 1)[-1] if "] " in line else line
            cnt += sum(1 for rx in DEFENSE_REGEXES if rx.search(text))
    return cnt


# -------------------- 메인 요약 함수 --------------------
def summarize_case(db: Session, case_id: UUID):
    case = db.get(m.AdminCase, case_id)
    if case is None:
        raise ValueError(f"AdminCase {case_id} not found")

    dialog = _format_dialog(db, case_id)

    phishing: bool | None = None
    evidence: str = ""

    # 1) LLM 판정 (있으면)
    if os.getenv("OPENAI_API_KEY"):
        llm = openai_chat()  # 지금은 관리자도 GPT 사용
        resp = llm.invoke(PROMPT.format(scenario=case.scenario, dialog=dialog)).content
        # JSON 추출(강건)
        mobj = re.search(r"\{[\s\S]*\}", resp)
        if mobj:
            try:
                data = json.loads(mobj.group(0))
            except json.JSONDecodeError:
                data = ast.literal_eval(mobj.group(0))
            phishing = bool(data.get("phishing")) if "phishing" in data else None
            evidence = str(data.get("evidence") or "")

    # 2) 룰 기반 최종상태 판정 (항상 실행, LLM 과잉양성 방지용 오버라이드)
    rb_phishing, rb_evidence = _rule_based(dialog)

    if phishing is None:
        # LLM이 없거나 실패 → 룰 결과 사용
        phishing = rb_phishing
        evidence = rb_evidence
    else:
        # LLM 결과와 룰 결과 병합 정책:
        # - 룰이 False(최종 방어)면 False로 오버라이드 (과잉양성 방지)
        # - 룰이 True(강한 금전행위)면 True로 승격
        # - 그 외엔 LLM 유지
        if rb_phishing is False and phishing is True:
            phishing = False
            evidence = (evidence + " | rule-override: " + rb_evidence).strip()
        elif rb_phishing is True and phishing is not True:
            phishing = True
            evidence = (rb_evidence + " | llm: " + evidence).strip() if evidence else rb_evidence

    # 3) 방어 횟수 계산(메타)
    defense_count = _count_defenses(dialog)

    # 4) DB 업데이트
    case.phishing = phishing
    case.evidence = evidence
    case.defense_count = defense_count
    case.status = "completed"
    case.completed_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(case)

    return {"phishing": phishing, "evidence": evidence, "defense_count": defense_count}
