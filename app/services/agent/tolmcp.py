# app/services/agent/tools_mcp.py
from __future__ import annotations
from typing import Any, Dict, Optional, Literal
import os, json, ast, re
from json import JSONDecoder
import httpx
from pydantic import BaseModel, Field, ValidationError
from langchain_core.tools import tool
from app.core.logging import get_logger
from app.services.prompts import render_attacker_system_string, render_victim_system_string
from app.services.agent.payload_store import load_payload

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────
# MCP 서버 베이스 URL
#   - 권장: MCP_BASE_URL (예: http://127.0.0.1:5177)
#   - 하위호환: MCP_HTTP_URL (예: http://127.0.0.1:5177/mcp) -> 베이스만 추출
# ─────────────────────────────────────────────────────────
_base_from_env = os.getenv("MCP_BASE_URL") or os.getenv("MCP_HTTP_URL", "http://127.0.0.1:5177")
MCP_BASE_URL = _base_from_env.replace("/mcp", "").rstrip("/")
GUIDANCE_KEY = os.getenv("MCP_GUIDANCE_KEY", "type").strip() or "type"
SEND_SYSTEM_PROMPTS = os.getenv("MCP_SEND_SYSTEM_PROMPTS", "0") == "1"

# ───────── 입력 스키마 ─────────
class Templates(BaseModel):
    attacker: str
    victim: str

class Guidance(BaseModel):
    type: Literal["A","P"]
    text: str

class MCPRunInput(BaseModel):
    offender_id: int
    victim_id: int
    scenario: Dict[str, Any]
    victim_profile: Dict[str, Any]

    # templates: dict 혹은 미제공 시 기본값
    templates: Templates = Field(
        default_factory=lambda: Templates(attacker="ATTACKER_PROMPT_V1", victim="VICTIM_PROMPT_V1")
    )

    # 모델: 여러 형태를 허용하고 아래에서 정규화
    models: Optional[Dict[str, str]] = None
    attacker_model: Optional[str] = None  # 호환 키
    victim_model: Optional[str] = None    # 호환 키
    max_turns: int = 15
    guidance: Optional[Guidance] = None
    case_id_override: Optional[str] = None
    round_no: Optional[int] = None
    combined_prompt: Optional[str] = None

class SingleData(BaseModel):
    data: dict = Field(...)

# ───────── 유틸 ─────────
def _unwrap(data: Any) -> Dict[str, Any]:
    """
    Tool Action Input으로 들어온 값을 '평평한(dict)' 형태로 반환.
    - dict면 {"data": {...}} 이면 내부 {...}만 반환, 아니면 그대로
    - str이면 첫 JSON 객체만 raw_decode로 파싱 후, {"data": {...}}면 내부만 반환
    - 코드펜스/접두 텍스트/트레일링 문자 방어 포함
    - JSON 파싱 실패 시 ast.literal_eval 폴백
    """
    if isinstance(data, dict):
        if set(data.keys()) == {"data"} and isinstance(data["data"], dict):
            return data["data"]
        return data

    if data is None:
        raise ValueError("Action Input is None")

    s = str(data).strip()

    # 코드펜스 제거 (```json ... ``` 등)
    if s.startswith("```"):
        m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S | re.I)
        if m:
            s = m.group(1).strip()

    # "Action Input: ..." 같은 접두 텍스트 제거 → 첫 '{'부터
    i = s.find("{")
    if i > 0:
        s = s[i:]

    dec = JSONDecoder()
    try:
        obj, end = dec.raw_decode(s)
    except Exception:
        # 1) 본문 내 가장 바깥의 { ... } 블록을 추출
        m = re.search(r"\{.*\}", s, re.S)
        if m:
            sub = m.group(0)
        else:
            raise ValueError("No JSON object found in action input")

        # 2) json.loads 시도
        try:
            obj = json.loads(sub)
        except Exception:
            # 3) ast.literal_eval (파이썬 dict 리터럴 허용)
            try:
                pyobj = ast.literal_eval(sub)
                if isinstance(pyobj, dict):
                    obj = pyobj
                else:
                    raise ValueError("Parsed object is not a dict")
            except Exception as e:
                raise ValueError(f"Unable to parse Action Input as JSON or Python literal: {e}")

    # payload_key 복원: {"payload_key": "..."} 형태
    if isinstance(obj, dict) and "payload_key" in obj:
        try:
            loaded = load_payload(obj["payload_key"])
            if loaded is None:
                raise ValueError(f"payload_key not found or expired: {obj['payload_key']}")
            obj = loaded
        except Exception as e:
            raise ValueError(f"failed to load payload from payload_key: {e}")

    # 'data' 래퍼가 있는 경우 벗겨서 반환
    if isinstance(obj, dict) and set(obj.keys()) == {"data"} and isinstance(obj["data"], dict):
        return obj["data"]

    if not isinstance(obj, dict):
        raise ValueError("Action Input did not resolve to a dict")

    return obj

def _post_api_simulate(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    MCP 서버 REST 엔드포인트 호출:
      POST {MCP_BASE_URL}/api/simulate
      Body: {"arguments": {...}}
      Resp: SimulationResult(dict) 또는 {"ok":True,"result":{...}}
    """
    url = f"{MCP_BASE_URL}/api/simulate"
    payload = {"arguments": arguments}
    with httpx.Client(timeout=120.0) as client:
        try:
            r = client.post(url, json=payload)
            r.raise_for_status()
        except httpx.HTTPStatusError as he:
            return {"ok": False, "error": "http_error", "status": he.response.status_code, "text": he.response.text}
        except Exception as e:
            return {"ok": False, "error": "http_exception", "text": str(e)}

    try:
        data = r.json()
    except Exception:
        return {"ok": False, "error": "invalid_json", "text": r.text}

    # 서버가 {"ok":..., "result": {...}} 또는 곧바로 {...}를 줄 수 있음 → 정규화
    if isinstance(data, dict) and "ok" in data:
        return data
    return {"ok": True, "result": data}

# ───────── LangChain Tool ─────────
def make_mcp_tools():
    @tool(
        "mcp.simulator_run",
        description="MCP 서버의 POST /api/simulate 를 호출해 두-봇 시뮬레이션을 실행합니다."
    )
    def simulator_run(data: Any) -> Dict[str, Any]:
        # ---------- 1) 입력 언랩 ----------
        payload = _unwrap(data)

        if isinstance(payload, dict) and "payload_key" in payload:
            stored = load_payload(payload["payload_key"])
            if not isinstance(stored, dict):
                return {"ok": False, "error": "payload_key_not_found", "hint": "expired or missing"}
            payload = stored

        # case_id 별칭 지원
        if "case_id" in payload and "case_id_override" not in payload:
            payload["case_id_override"] = payload["case_id"]

        # (혼선 방지) combined_prompt 자동 생성/전달 제거
        ap = payload.get("attacker_prompt")
        vp = payload.get("victim_prompt")
        # if ap and vp and "combined_prompt" not in payload:
        #     payload["combined_prompt"] = f"[ATTACKER]\n{ap}\n[/ATTACKER]\n[VICTIM]\n{vp}\n[/VICTIM]"

        # ---------- 2) 1회만 검증 ----------
        try:
            model = MCPRunInput.model_validate(payload)
        except ValidationError as ve:
            return {
                "ok": False,
                "error": "Invalid Action Input for mcp.simulator_run",
                "pydantic_errors": json.loads(ve.json()),
            }

        # ---------- 3) 모델 키 정규화 ----------
        eff_models: Dict[str, str] = {}
        if isinstance(model.models, dict):
            eff_models.update({k: v for k, v in model.models.items() if isinstance(v, str) and v})
        if model.attacker_model:
            eff_models["attacker"] = model.attacker_model
        if model.victim_model:
            eff_models["victim"] = model.victim_model
        if eff_models:
            logger.info(f"[MCP] using explicit models: {eff_models}")

        # ---------- 4) prompts.py 빌더로 system 문자열 생성 ----------
        atk_system = payload.get("attacker_prompt") or None
        vic_system = payload.get("victim_prompt") or None

        if not atk_system:
            try:
                atk_system = render_attacker_system_string(
                    scenario=model.scenario or {},
                    current_step="",
                    guidance=(model.guidance.model_dump() if model.guidance else None),
                )
            except Exception as e:
                logger.warning(f"[MCP] render_attacker_system_string failed: {e}")
                atk_system = None  # 폴백 필요

        if not vic_system:
            try:
                vic_system = render_victim_system_string(
                    victim_profile=model.victim_profile or {},
                    round_no=int(model.round_no or 1),
                    previous_experience="",
                    is_convinced_prev=None,
                )
            except Exception as e:
                logger.warning(f"[MCP] render_victim_system_string failed: {e}")
                vic_system = None  # 폴백 필요

        # 🔐 최종 폴백: 호출자가 준 templates(짧은 기본문구)라도 넣어서 비는 일 방지
        if atk_system is None:
            atk_system = model.templates.attacker
        if vic_system is None:
            vic_system = model.templates.victim

        # 디버깅용: 실제 전송되는 system 머리만 로그
        def _head(s: str, n: int = 140) -> str:
            try:
                return (s[:n] + ("..." if len(s) > n else ""))
            except Exception:
                return "<non-str>"

        logger.info("[MCP] attacker system head: %s", _head(atk_system))
        logger.info("[MCP] victim   system head: %s", _head(vic_system))

        token_templates = {"attacker": model.templates.attacker, "victim": model.templates.victim}

        # ---------- 5) 서버 스키마에 맞게 arguments 구성 ----------
        args: Dict[str, Any] = {
            "offender_id": model.offender_id,
            "victim_id": model.victim_id,
            "scenario": model.scenario,
            "victim_profile": model.victim_profile,
            "templates": token_templates,  # ← 우리가 만든 system 문자열만 전달
            "max_turns": model.max_turns,
        }
        if model.guidance:
            args["guidance"] = {GUIDANCE_KEY: model.guidance.type, "text": model.guidance.text}
        if model.case_id_override:
            args["case_id_override"] = model.case_id_override
        if model.round_no:
            args["round_no"] = model.round_no
        # combined_prompt 전달 금지 (혼선 방지)
        # if model.combined_prompt:
        #     args["combined_prompt"] = model.combined_prompt

        # 개별 attacker_prompt/victim_prompt 전달 금지 (혼선 방지)
        # if ap and vp:
        #     args["attacker_prompt"] = ap
        #     args["victim_prompt"] = vp



        # 확장 시스템 프롬프트는 환경변수로 on/off (기본 off)
        if SEND_SYSTEM_PROMPTS:
            args["attacker_prompt"] = atk_system
            args["victim_prompt"] = vic_system

        # 모델 전달(선택)
        if eff_models:
            args["models"] = eff_models

        logger.info(f"[MCP] POST /api/simulate keys={list(args.keys())} base={MCP_BASE_URL}")

        # ---------- 6) 호출 ----------
        res = _post_api_simulate(args)

        # 서버가 실패 형식으로 주는 경우 그대로 반환
        if isinstance(res, dict) and res.get("ok") is False:
            # HTTP 500이면 '최소 페이로드'로 1회 재시도 (확장 프롬프트 제거, 템플릿 토큰만)
            if res.get("error") == "http_error" and int(res.get("status") or 0) == 500:
                logger.warning("[MCP] 500 발생 → 최소 페이로드로 재시도")
                minimal_args = {
                    "offender_id": model.offender_id,
                    "victim_id": model.victim_id,
                    "scenario": model.scenario,
                    "victim_profile": model.victim_profile,
                    "templates": token_templates,
                    "max_turns": model.max_turns,
                }
                if model.guidance:
                    minimal_args["guidance"] = {GUIDANCE_KEY: model.guidance.type, "text": model.guidance.text}
                if model.case_id_override:
                    minimal_args["case_id_override"] = model.case_id_override
                if model.round_no:
                    minimal_args["round_no"] = model.round_no
                if eff_models:
                    minimal_args["models"] = eff_models

                res2 = _post_api_simulate(minimal_args)
                if isinstance(res2, dict) and res2.get("ok") is False:
                    return res2
                res = res2
            else:
                return res

        # ---------- 7) 응답 평탄화 ----------
        result = None
        if isinstance(res, dict):
            if isinstance(res.get("result"), dict):
                result = res["result"]
            elif isinstance(res.get("raw"), dict) and isinstance(res["raw"].get("result"), dict):
                result = res["raw"]["result"]

        if not isinstance(result, dict):
            return {"ok": False, "error": "bad_simulator_payload", "raw": res}
        
        for _ in range(3):
            if isinstance(result.get("result"), dict):
                result = result["result"]
                continue
            raw = result.get("raw")
            if isinstance(raw, dict) and isinstance(raw.get("result"), dict):
                result = raw["result"]
                continue
            break

        # 여러 경로에서 conversation_id를 튼튼하게 추출
        cid = (
            result.get("conversation_id")
            or result.get("case_id")
            or (result.get("meta") or {}).get("conversation_id")
        )

        if not cid:
            return {"ok": False, "error": "missing_conversation_id", "raw": result}

        turns = result.get("turns") or []
        stats = result.get("stats") or {}
        ended_by = result.get("ended_by")
        meta = result.get("meta") or {}

        # ---------- 8) 표준화된 성공 응답 ----------
        return {
            "ok": True,
            "case_id": cid,
            "turns": turns,
            "stats": stats,
            "ended_by": ended_by,
            "meta": meta,
            "log": result,
            "total_turns": stats.get("turns"),
            "debug_templates": {          # 👈 추가
                "attacker": atk_system,
                "victim":   vic_system,
            },
        }

    return [simulator_run]
