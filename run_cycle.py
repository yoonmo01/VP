# run_cycle.py
from __future__ import annotations
import json
from typing import Any, Dict, List, Tuple

from app.db.session import SessionLocal
from app.db import models as m
from app.services.simulation import run_two_bot_simulation
from app.services.admin_summary import summarize_case
from app.schemas.conversation import ConversationRunRequest
from app.core.config import settings
from app.services.prompts import (
    render_attacker_from_offender,
    render_victim_from_profile,
)

def _case_scenario_from_offender(offender: m.PhishingOffender) -> Dict[str, Any]:
    """
    offender.profile 안에 들어있는 시나리오 스냅샷에서 purpose/steps를 추출.
    없으면 최소 포맷으로 대체.
    """
    profile = offender.profile or {}
    purpose = profile.get("purpose") or "시나리오 목적 미지정"
    steps = profile.get("steps") or []
    # (선택) type을 넣어두면 분석시 유용
    typ = profile.get("type")
    scen = {"purpose": purpose, "steps": steps}
    if typ:
        scen["type"] = typ
    return scen


def run_one(db, offender: m.PhishingOffender, victim: m.Victim, max_rounds: int) -> Tuple[str, int]:
    """
    하나의 시뮬레이션 케이스 실행 (공격자 + 피해자 프롬프트 변수 세팅)
    """
    case_scenario = _case_scenario_from_offender(offender)
    # 1) 공격자 프롬프트 변수 생성
    attacker_vars = render_attacker_from_offender({
        "name": offender.name,
        "type": offender.type,
        "profile": offender.profile
    })

    # 2) 피해자 프롬프트 변수 생성
    victim_vars = render_victim_from_profile({
        "meta": victim.meta,
        "knowledge": victim.knowledge,
        "traits": victim.traits
    })

    # 3) 시뮬레이션 요청 객체 생성
    req = ConversationRunRequest(
        offender_id=offender.id,
        victim_id=victim.id,
        case_scenario=case_scenario,
        max_rounds=max_rounds,
        history=[],
        last_victim="",
        last_offender="",
        **attacker_vars,
        **victim_vars
    )

    # 4) 시뮬레이션 실행
    case_id, total_turns = run_two_bot_simulation(db, req)

    # 5) 결과 요약 저장
    summarize_case(db, case_id)

    return str(case_id), total_turns


def main():
    db = SessionLocal()
    try:
        offenders: List[m.PhishingOffender] = (
            db.query(m.PhishingOffender).filter(m.PhishingOffender.is_active.is_(True)).order_by(m.PhishingOffender.id)
        ).all()
        victims: List[m.Victim] = (
            db.query(m.Victim).filter(m.Victim.is_active.is_(True)).order_by(m.Victim.id)
        ).all()

        if not offenders or not victims:
            raise RuntimeError("오프너/피해자 데이터가 부족합니다. seed를 먼저 넣어주세요.")

        CYCLES = 5  # ← 사이클 횟수

        total = 0
        results = []

        for cycle in range(1, CYCLES + 1):
            print(f"\n=== Cycle {cycle}/{CYCLES} 시작 ===")
            for off in offenders:
                for vic in victims:
                    case_id, turns = run_one(db, off, vic, max_rounds=15)
                    total += 1
                    results.append({
                        "cycle": cycle,
                        "case_id": case_id,
                        "offender_id": off.id,
                        "victim_id": vic.id,
                        "turns": turns
                    })
                    print(f"[{total}] cycle={cycle} offender={off.id} victim={vic.id} → case={case_id} turns={turns}")

        print("\n=== Batch summary ===")
        print(f"총 케이스 수: {total} (예상 {len(offenders)} x {len(victims)} x {CYCLES} = {len(offenders)*len(victims)*CYCLES})")
        print(json.dumps(results[:5], ensure_ascii=False, indent=2))

    finally:
        db.close()


if __name__ == "__main__":
    main()
