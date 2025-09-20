from __future__ import annotations
from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from fastapi import HTTPException
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.db import models as m
import json, ast, re

from app.services.prompts import (
    ATTACKER_PROMPT,
    VICTIM_PROMPT,
    render_victim_from_profile,
)

# ---------- 문자열 전처리 유틸(코드펜스/따옴표/첫 JSON 블록만 추출) ----------
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
    stack, in_str, esc, end = [], False, False, None
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
        else:
            if ch == '"': in_str = True
            elif ch == "{": stack.append("}")
            elif ch == "[": stack.append("]")
            elif ch in ("}", "]"):
                if stack and stack[-1] == ch:
                    stack.pop()
                    if not stack:
                        end = i; break
    if end is not None:
        return s[start:end+1]
    balanced = s[start:]
    while stack:
        balanced += stack.pop()
    return balanced

# ---------- 공통 유틸 ----------
def _to_dict(obj: Any) -> Dict[str, Any]:
    # pydantic BaseModel → dict
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()

    # bytes → str
    if isinstance(obj, (bytes, bytearray)):
        obj = obj.decode()

    if isinstance(obj, dict):
        return obj

    if isinstance(obj, str):
        # 1) 코드펜스/스마트따옴표 제거
        s = _normalize_quotes(_strip_code_fences(obj)).strip()

        # 2) 따옴표 바깥의 주석/노트 제거(예: "# 예시", "(Note: ...)" 등은 JSON 앞뒤에 붙는 경우가 많음)
        #    → JSON 블록만 남기면 자연스레 제거됨
        core = _extract_json_with_balancing(s)

        # 3) JSON 우선 → 실패 시 literal_eval
        try:
            return json.loads(core)
        except Exception:
            try:
                return ast.literal_eval(core)
            except Exception:
                raise HTTPException(status_code=422, detail="Action Input 'data'는 주석/설명 없이 올바른 JSON 객체여야 합니다.")

    raise HTTPException(status_code=422, detail="Action Input 'data'는 JSON 객체여야 합니다.")

def _unwrap_data(obj: Any) -> Dict[str, Any]:
    """{"data": {...}} 또는 {...} 둘 다 허용"""
    d = _to_dict(obj)
    inner = d.get("data")
    if inner is not None:
        return _to_dict(inner)
    return d

def _assert_role_turn(turn_index: int, role: str):
    """짝수턴=offender, 홀수턴=victim 규칙 확인(로그 저장용)."""
    expected = "offender" if turn_index % 2 == 0 else "victim"
    if role not in ("offender", "victim"):
        raise HTTPException(status_code=422, detail="role must be 'offender' or 'victim'")
    if role != expected:
        raise HTTPException(status_code=422, detail=f"Turn {turn_index} must be {expected}, got {role}")

# ---------- 단일 인자 스키마 ----------
class SingleData(BaseModel):
    """모든 툴의 Action Input은 {"data": {...}} 한 개만 받도록 통일"""
    data: Any = Field(..., description="툴별 요구 JSON 페이로드를 이 안에 담아주세요")

# ---------- 툴 팩토리 ----------
def make_sim_tools(db: Session):
    @tool(
        "sim.fetch_entities",
        args_schema=SingleData,
        description="DB에서 공격자/피해자/시나리오를 읽어 에이전트 입력 묶음을 만든다(steps는 요청>공격자프로필 순). Action Input은 {'data': {'offender_id':int,'victim_id':int,'scenario':{...}}}"
    )
    def fetch_entities(data: Any) -> Dict[str, Any]:
        payload = _unwrap_data(data)  # ✅ 래핑/주석/예시 모두 허용
        try:
            offender_id = int(payload["offender_id"])
            victim_id   = int(payload["victim_id"])
        except KeyError as e:
            raise HTTPException(status_code=422, detail=f"Missing required field: {e.args[0]}")
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="offender_id, victim_id는 정수여야 합니다.")

        scenario = payload.get("scenario") or {}
        if not isinstance(scenario, dict):
            # 문자열로 온 경우도 dict 추출 시도
            scenario = _to_dict(scenario) if isinstance(scenario, str) else {}
        off = db.get(m.PhishingOffender, offender_id)
        vic = db.get(m.Victim, victim_id)
        if not off:
            raise HTTPException(status_code=404, detail=f"offender {offender_id} not found")
        if not vic:
            raise HTTPException(status_code=404, detail=f"victim {victim_id} not found")

        victim_profile = {
            "meta": getattr(vic, "meta", None) or (getattr(vic, "body", {}) or {}).get("meta", {}),
            "knowledge": getattr(vic, "knowledge", None) or (getattr(vic, "body", {}) or {}).get("knowledge", {}),
            "traits": getattr(vic, "traits", None) or (getattr(vic, "body", {}) or {}).get("traits", {}),
        }

        # steps 우선순위: 요청→공격자 프로필
        req_steps = scenario.get("steps")
        off_steps = (off.profile or {}).get("steps")
        steps = req_steps if isinstance(req_steps, list) else (off_steps if isinstance(off_steps, list) else [])

        merged_scenario = {**(off.profile or {}), **(scenario or {}), "steps": steps}
        return {"scenario": merged_scenario, "victim_profile": victim_profile}

    @tool(
        "sim.compose_prompts",
        args_schema=SingleData,
        description="시나리오/피해자/지침을 바탕으로 공격자/피해자 프롬프트를 생성한다. Action Input은 {'data': {'scenario':{...},'victim_profile':{...},'guidance':{'type':'A|P','text':'...'}}}"
    )
    def compose_prompts(data: Any) -> Dict[str, str]:
        """공격자/피해자 역할 프롬프트를 구성한다(실제 기관/계좌/번호 금지 규칙 포함)."""
        payload = _unwrap_data(data)
        scenario = _unwrap_data(payload.get("scenario") or {})
        victim_profile = _unwrap_data(payload.get("victim_profile") or {})
        guidance = payload.get("guidance")

        # 🔹여기서 guidance 1라운드 가드 처리🔹
        round_no = payload.get("round_no")
        case_id  = payload.get("case_id") or payload.get("case_id_override")
        if guidance and not case_id and (round_no is None or int(round_no) <= 1):
            guidance = None

        safety = (
            "[규칙] 실제 기관/계좌/번호는 금지(가명 사용). "
            "앱 설치/링크 요구는 명시적으로만 표현.\n"
        )
        scen = scenario.get("description") or scenario.get("text") or str(scenario)
        vic = (
            f"메타: {victim_profile.get('meta')}\n"
            f"지식: {victim_profile.get('knowledge')}\n"
            f"성격: {victim_profile.get('traits')}\n"
        )
        g_att = f"\n[지침-공격자]\n{guidance['text']}\n" if guidance and guidance.get("type") == "A" else ""
        g_vic = f"\n[지침-피해자]\n{guidance['text']}\n" if guidance and guidance.get("type") == "P" else ""

        attacker_prompt = f"[보이스피싱 시뮬레이션]\n{safety}[시나리오]\n{scen}\n[역할] 너는 공격자다.{g_att}"
        victim_prompt   = f"[보이스피싱 시뮬레이션]\n{safety}[피해자 프로파일]\n{vic}\n[역할] 너는 피해자다.{g_vic}"

        return {"attacker_prompt": attacker_prompt, "victim_prompt": victim_prompt}

    @tool(
        "sim.persist_turn",
        args_schema=SingleData,
        description="ConversationLog에 한 턴(한 줄)을 저장한다(짝수=공격자, 홀수=피해자). Action Input은 {'data': {'case_id':UUID,'offender_id':int,'victim_id':int,'run_no':int,'turn_index':int,'role':'offender|victim','text':str,'use_agent':bool,'guidance_type':'A|P'|null,'guideline':str|null}}"
    )
    def persist_turn(data: Any) -> str:
        """한 줄(단일 role)의 발화를 저장. 짝수턴=offender, 홀수턴=victim 규칙 검증."""
        payload = _unwrap_data(data)  # ✅ {"data": {...}}도 허용
        try:
            case_id = UUID(str(payload["case_id"]))
            offender_id = int(payload["offender_id"])
            victim_id = int(payload["victim_id"])
            run_no = int(payload.get("run_no", 1))
            turn_index = int(payload["turn_index"])
            role = str(payload["role"])
        except KeyError as e:
            raise HTTPException(status_code=422, detail=f"Missing required field: {e.args[0]}")
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="case_id/offender_id/victim_id/run_no/turn_index/role 형식 오류")

        text = (payload.get("text") or "").strip()
        use_agent = bool(payload.get("use_agent", True))
        guidance_type = payload.get("guidance_type")
        guideline = payload.get("guideline")

        _assert_role_turn(turn_index, role)
        log = m.ConversationLog(
            case_id=case_id,
            offender_id=offender_id,
            victim_id=victim_id,
            turn_index=turn_index,
            role=role,
            content=text,
            label=None,
            use_agent=use_agent,
            run=run_no,
            guidance_type=guidance_type,
            guideline=guideline,
        )
        db.add(log); db.commit()
        return f"ok:{log.id}"

    @tool(
        "sim.should_stop",
        args_schema=SingleData,
        description="현재 사이클 인덱스(공+피 한 쌍)와 종료 키워드로 중단 여부 판단. Action Input은 {'data': {'attacker_text':str,'victim_text':str,'turn_index':int,'max_turns':int}}"
    )
    def should_stop(data: Any) -> bool:
        """
        종료 조건:
        1) turn_index(사이클 번호) >= max_turns  → 한 사이클 최대 턴(공+피 쌍) 초과
        2) 종료 키워드가 포함됨
        """
        payload = _unwrap_data(data)  # ✅ 래핑 허용
        try:
            attacker_text = str(payload.get("attacker_text") or "").lower()
            victim_text = str(payload.get("victim_text") or "").lower()
            turn_index = int(payload.get("turn_index", 0))
            max_turns = int(payload.get("max_turns", 15))
        except Exception:
            raise HTTPException(status_code=422, detail="should_stop 입력 형식 오류")

        if turn_index >= max_turns:
            return True
        blob = f"{attacker_text}\n{victim_text}"
        keys = ["여기서 마무리", "통화 종료", "송금 완료", "앱 설치 종료", "앱 설치 완료", "마무리하겠습니다"]
        return any(k.lower() in blob for k in keys)

    return [fetch_entities, compose_prompts, persist_turn, should_stop]
