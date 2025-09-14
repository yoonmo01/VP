# app/services/prompt_integrator_db.py (신규)
from __future__ import annotations
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.schemas.simulation_request import SimulationStartRequest
from app.db import models as m

def load_victim_profile(db: Session, req: SimulationStartRequest) -> Dict[str, Any]:
    if req.custom_victim:
        return {
            "meta": req.custom_victim.meta,
            "knowledge": req.custom_victim.knowledge,
            "traits": req.custom_victim.traits,
        }
    assert req.victim_id is not None, "victim_id가 필요합니다(커스텀 피해자 없음)."
    vic = db.get(m.Victim, int(req.victim_id))
    if not vic or not vic.is_active:
        raise ValueError(f"Victim {req.victim_id} not found or inactive")
    return {
        "meta": vic.meta or {},
        "knowledge": vic.knowledge or {},
        "traits": vic.traits or {},
    }

def load_scenario_from_offender(db: Session, offender_id: int) -> Dict[str, Any]:
    off = db.get(m.PhishingOffender, int(offender_id))
    if not off or not off.is_active:
        raise ValueError(f"Offender {offender_id} not found or inactive")
    prof = off.profile or {}
    return {
        "description": prof.get("description") or prof.get("text") or off.type or "일반 시나리오",
        "purpose": prof.get("purpose") or "미상",
        "steps": prof.get("steps") or [],
    }

def build_custom_scenario(seed: Dict[str, Any], tavily_out: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    # tavily 출력 우선, seed 보완
    return {
        "description": (tavily_out or {}).get("description") or seed.get("text") or seed.get("type") or "커스텀 시나리오",
        "purpose":     (tavily_out or {}).get("purpose")     or seed.get("purpose") or "미상",
        "steps":       (tavily_out or {}).get("steps")       or seed.get("objectives") or [],
    }

def save_custom_scenario_to_attack(db: Session, scenario: Dict[str, Any]) -> int:
    """
    커스텀 시나리오를 Attack 카탈로그에 저장.
    body 필드에 통째로 넣고 title은 description 앞부분을 사용.
    """
    title = str(scenario.get("description") or "custom").strip()
    atk = m.Attack(title=title[:150] or "custom", category="custom", body=scenario, is_active=True)
    db.add(atk); db.commit(); db.refresh(atk)
    return int(atk.id)

def build_prompt_package_from_payload(
    db: Session,
    req,  # SimulationStartRequest
    tavily_result: Optional[Dict[str, Any]] = None,
    *,
    is_first_run: bool = False,          # ✅ 최초 1회 커스텀만 저장할지 판단
    skip_catalog_write: bool = True      # ✅ 기본은 저장 금지
) -> Dict[str, Any]:
    """
    - 기존 시나리오(offender_id 기반) 사용: Attack 저장 절대 금지
    - 커스텀 시나리오: is_first_run == True 이고 skip_catalog_write == False 인 경우에만 저장
    """
    victim_profile = load_victim_profile(db, req)

    if getattr(req, "custom_scenario", None):
        seed = req.custom_scenario.model_dump()
        # ❗ tavily_result는 기본 None 유지 (원하면 호출부에서 명시적으로 넘겨주세요)
        scenario = build_custom_scenario(seed, tavily_result)

        # ✅ 오직 "최초 1회 + 저장 허용"일 때만 Attack 저장
        if is_first_run is True and skip_catalog_write is False:
            _attack_id = save_custom_scenario_to_attack(db, scenario)
        # else: 저장하지 않음
    else:
        # ✅ 기존 수법/오펜더 기반
        assert req.offender_id is not None, "offender_id가 필요합니다(커스텀 시나리오 없음)."
        scenario = load_scenario_from_offender(db, req.offender_id)
        # ✅ 기존 시나리오에서는 저장 절대 금지 (아래 라인 없음)
        # _attack_id = save_custom_scenario_to_attack(...)

    # ✅ 템플릿은 고정 ID만 패키징(프롬프트 바디는 별도 compose 단계에서 만듦)
    return {
        "scenario": scenario,
        "victim_profile": victim_profile,
        "templates": {"attacker": "ATTACKER_PROMPT_V1", "victim": "VICTIM_PROMPT_V1"},
    }