# app/services/admin_summary.py
from __future__ import annotations

from sqlalchemy.orm import Session
from uuid import UUID
from app.db import models as m
from app.services.llm_providers import openai_chat  # ADMIN_MODEL은 .env로 지정
from datetime import datetime, timezone
import json
import re
import ast
from typing import Any

PROMPT_LLM_ONLY = """
당신은 연구용 보이스피싱 분석가입니다.
아래 대화 로그를 읽고, 보이스피싱 피해 발생 여부와 그 근거를 JSON으로만 출력하세요.

[출력 형식] (매우 엄격)
- 반드시 JSON 객체 1개만 출력.
- 불필요한 설명, 특수기호, 코드블록(```json) 금지.
- 키는 정확히 2개: "phishing", "evidence"
- 키 순서는 ["phishing", "evidence"]
- evidence: 한 단락(2~4문장) 요약 + 핵심 발화 2~5개를 turn_index와 함께 간단히 인용.
- 인용 형식 예시: turn 05 "…송금했어요"

[판정 기준] (모든 수법 포용)
- phishing = true ⇨ 아래 중 하나라도 대화 상에서 실제로 **완료되었다**고 명시된 경우
  1) 금전 송금, 이체, 입금, 현금 인출, 보관함·락커에 현금 보관
  2) 신규·대환 대출 실행 및 그 금액을 범인 측에 전달
  3) 가족·지인 사칭으로 계좌송금, 비밀번호 제공 후 송금/인출 발생
  4) 자동이체, 강제출금 등으로 실제 금전 이동이 발생
- phishing = false ⇨
  - 마지막 구간에서 대표번호 확인, 지점 방문, 신고, 거절, 통화 종료 등으로 **방어가 명확**하고 이후 금전행위가 없을 때
  - 단순 개인정보 제공, OTP/인증번호 입력, 위협·유도 표현만 있고 실제 금전 이동이 발생하지 않았을 때
- 보수적 판정: 애매하면 false(피해 미확정)

[참고 시나리오]  
시나리오: {scenario}

[대화 로그]  
{dialog}

[출력 예시]  
{"phishing": true, "evidence": "피해자가 500만원을 송금 완료했으며, turn 07, 09, 10에서 금전 전달 발화가 명확히 나타남. 이후 방어행위 언급 없음."}
""".strip()


def _format_dialog(db: Session, case_id: UUID) -> str:
    """DB의 대화 로그를 판정용 평문으로 변환."""
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


def _json_loads_lenient(s: str) -> dict[str, Any]:
    """모델이 앞뒤에 텍스트를 붙였을 경우에도 JSON 블록만 안전하게 파싱."""
    mobj = re.search(r"\{[\s\S]*\}", s)
    raw = mobj.group(0) if mobj else s
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 마지막 안전장치: Python literal eval
        return ast.literal_eval(raw)


def summarize_case(db: Session, case_id: UUID):
    """
    ✳ 무조건 LLM만 사용해 피싱여부/근거를 생성한다.
    - ADMIN_MODEL은 .env의 ADMIN_MODEL=gpt-4o 등으로 지정
    - 규칙/정규식 기반 판정은 일절 사용하지 않음
    """
    case = db.get(m.AdminCase, case_id)
    if case is None:
        raise ValueError(f"AdminCase {case_id} not found")

    # 시나리오는 dict/JSON/str 등 무엇이든 올 수 있음 → 안전 변환
    scenario_obj = case.scenario
    if isinstance(scenario_obj, (dict, list)):
        scenario_str = json.dumps(scenario_obj, ensure_ascii=False)
    else:
        scenario_str = str(scenario_obj or "")

    dialog = _format_dialog(db, case_id)

    # 🔹 LLM 호출 (ADMIN_MODEL은 llm_providers 내부에서 .env를 참고)
    llm = openai_chat()  # 내부에서 ADMIN_MODEL 사용한다고 가정
    resp = llm.invoke(PROMPT_LLM_ONLY.format(
        scenario=scenario_str,
        dialog=dialog
    )).content

    data = _json_loads_lenient(resp)
    if "phishing" not in data or "evidence" not in data:
        raise RuntimeError("LLM 응답에 'phishing' 또는 'evidence' 키가 없습니다.")

    phishing = bool(data["phishing"])
    evidence = str(data["evidence"] or "")

    # 방어 횟수 등 룰기반 메타는 사용하지 않으므로 0으로 저장(스키마 not null 대응)
    defense_count = 0

    # DB 업데이트
    case.phishing = phishing
    case.evidence = evidence
    case.defense_count = defense_count
    case.status = "completed"
    case.completed_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(case)

    return {"phishing": phishing, "evidence": evidence, "defense_count": defense_count}
