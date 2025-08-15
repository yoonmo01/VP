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

PROMPT = """
너는 연구용 보이스피싱 분석가다. 아래 대화 로그를 읽고,
1) phishing: true/false (피해가 실제로 발생했거나 발생 직전·명백한 시도면 true)
2) evidence: 한 단락(2~4문장)으로 왜 그렇게 판단했는지 근거
만 JSON으로만 출력하라. 키는 phishing, evidence만 포함.

[시나리오]
{scenario}

[대화 로그]
{dialog}
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

def _rule_based(dialog: str) -> Tuple[bool | None, str]:
    # 매우 단순한 휴리스틱: 현금 인출/전용계좌/보관함/영장/수거 등 키워드
    red_flags = [
        "현금 인출", "현금을", "전용계좌", "안전관리", "보관함", "락커", "수거책",
        "검사", "수사관", "영장", "긴급", "즉시 송금", "원격", "앱 설치", "원격제어"
    ]
    hits = [k for k in red_flags if k in dialog]
    phishing = True if hits else None  # 확신 없으면 None
    evidence = "정형 룰 기반 추정: 위험 징후 키워드 감지 → " + (", ".join(hits) if hits else "징후 부족")
    return phishing, evidence

# -------------------- 방어 횟수 계산(피해자 대사만) --------------------
DEFENSE_PATTERNS = [
    r"(공식|은행|경찰|검찰)\s*(대표번호|콜센터|번호|방문)",     # 공식 경로 확인 의사
    r"(검색|조회|확인)\s*(해볼게|해보겠습니다|먼저)",            # 먼저 확인/검색
    r"(링크|앱)\s*(안|못)\s*열|설치\s*(안|못)하",               # 링크/앱 거부
    r"(계좌|현금|송금)\s*(안|못)\s*하겠|거절|불가|의심",          # 송금/인출 거절/의심
    r"(콜백|다시 전화|번호 확인)",                              # 콜백/번호 확인
]
DEFENSE_REGEXES = [re.compile(p) for p in DEFENSE_PATTERNS]

def _count_defenses(dialog_text: str) -> int:
    """
    대화 로그 문자열에서 [피해자] 줄만 뽑아 방어 패턴 매칭 수를 합산.
    한 줄에 여러 패턴이 맞아도 1로 치고 싶으면 any(.)로 바꾸면 됨.
    """
    cnt = 0
    for line in dialog_text.splitlines():
        if "[피해자]" in line:
            text = line.split("] ", 1)[-1] if "] " in line else line
            # 패턴별 매칭을 모두 합산(보수적으로 카운트)
            cnt += sum(1 for rx in DEFENSE_REGEXES if rx.search(text))
    return cnt
# ----------------------------------------------------------------------

def summarize_case(db: Session, case_id: UUID):
    case = db.get(m.AdminCase, case_id)
    if case is None:
        raise ValueError(f"AdminCase {case_id} not found")

    dialog = _format_dialog(db, case_id)

    phishing: bool | None = None
    evidence: str = ""

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
        else:
            phishing, evidence = _rule_based(dialog)
    else:
        phishing, evidence = _rule_based(dialog)

    # ✅ 방어 횟수 계산
    defense_count = _count_defenses(dialog)

    # DB 업데이트
    case.phishing = phishing
    case.evidence = evidence
    # 아래 컬럼이 모델에 있어야 합니다: defense_count INTEGER
    case.defense_count = defense_count
    case.status = "completed"                     # 완료 처리
    case.completed_at = datetime.now(timezone.utc)         # 완료 시각
    db.commit(); db.refresh(case)

    return {"phishing": phishing, "evidence": evidence, "defense_count": defense_count}
