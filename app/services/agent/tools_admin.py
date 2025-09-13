# app/services/agent/tools_admin.py
from __future__ import annotations
from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.db import models as m
from app.services.admin_summary import summarize_case
import json, ast

# ---- 공통: {"data": {...}} 입력 통일 ----
class SingleData(BaseModel):
    data: Any = Field(..., description="이 안에 실제 페이로드를 담는다")

def _to_dict(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        s = obj.strip()
        # JSON 우선
        try:
            return json.loads(s)
        except Exception:
            # JSON 실패 시 literal_eval 보정
            try:
                return ast.literal_eval(s)
            except Exception:
                raise HTTPException(status_code=422, detail="data는 JSON 객체여야 합니다.")
    raise HTTPException(status_code=422, detail="data는 JSON 객체여야 합니다.")

def _unwrap_data(obj: Any) -> Dict[str, Any]:
    """{"data": {...}} 또는 {...} 둘 다 허용"""
    d = _to_dict(obj)
    return _to_dict(d.get("data")) if "data" in d else d

def _normalize_kind(val: Any) -> str:
    """kind가 '{"kind":"A"}' 같은 문자열 JSON이어도 'A'로 복구"""
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("{"):
            try:
                parsed = json.loads(s)
            except Exception:
                try:
                    parsed = ast.literal_eval(s)
                except Exception:
                    raise HTTPException(status_code=422, detail="kind 형식 오류")
            k = parsed.get("kind") or parsed.get("type")
            if isinstance(k, str):
                return k
        return s
    raise HTTPException(status_code=422, detail="kind는 문자열이어야 합니다.")

# ----- 검증용 내부 스키마 (툴 바깥 공개 X) -----
class _JudgeInput(BaseModel):
    case_id: UUID = Field(..., description="대상 케이스 ID")
    run_no: int = Field(1, description="런 번호")

class _GuidanceInput(BaseModel):
    kind: str = Field(..., pattern="^(P|A)$", description="지침 종류: 'P'(피해자) | 'A'(공격자)")

class _SavePreventionInput(BaseModel):
    case_id: UUID
    offender_id: int
    victim_id: int
    run_no: int = 1
    summary: str
    steps: list[str] = Field(default_factory=list, description="예방 단계 리스트")

# ----- 툴 팩토리 -----
def make_admin_tools(db: Session, guideline_repo):
    @tool(
        "admin.judge",
        args_schema=SingleData,
        description="케이스를 요약/판정하여 피싱 여부와 사유를 반환한다. Action Input은 {'data': {'case_id': UUID, 'run_no': int}}"
    )
    def judge(data: Any) -> Dict[str, Any]:
        payload = _unwrap_data(data)
        try:
            ji = _JudgeInput(**payload)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"JudgeInput 검증 실패: {e}")

        res = summarize_case(db, ji.case_id) or {}
        return {
            "phishing": bool(res.get("phishing")),
            "reason": res.get("reason", ""),
            "run_no": ji.run_no,
        }

    @tool(
        "admin.pick_guidance",
        args_schema=SingleData,
        description="상황에 맞는 지침을 선택한다. Action Input은 {'data': {'kind': 'P'|'A'}}"
    )
    def pick_guidance(data: Any) -> Dict[str, str]:
        payload = _unwrap_data(data)
        if "kind" not in payload:
            raise HTTPException(status_code=422, detail="kind 누락")
        kind = _normalize_kind(payload["kind"])
        try:
            gi = _GuidanceInput(kind=kind)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"GuidanceInput 검증 실패: {e}")

        if gi.kind == "P":
            text, title = guideline_repo.pick_preventive()
        else:
            text, title = guideline_repo.pick_attack()
        return {"type": gi.kind, "title": title, "text": text}

    @tool(
        "admin.save_prevention",
        args_schema=SingleData,
        description="개인화된 예방책을 DB에 저장한다. Action Input은 {'data': {'case_id':UUID,'offender_id':int,'victim_id':int,'run_no':int,'summary':str,'steps':[str,...]}}"
    )
    def save_prevention(data: Any) -> str:
        payload = _unwrap_data(data)
        try:
            spi = _SavePreventionInput(**payload)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"SavePreventionInput 검증 실패: {e}")

        obj = m.PersonalizedPrevention(
            case_id=spi.case_id,
            offender_id=spi.offender_id,
            victim_id=spi.victim_id,
            run=spi.run_no,
            content={"summary": spi.summary, "steps": spi.steps},
            note="agent-generated",
            is_active=True,
        )
        db.add(obj)
        db.commit()
        return str(obj.id)

    return [judge, pick_guidance, save_prevention]
