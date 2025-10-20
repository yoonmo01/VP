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
# ─────────────────────────────────────────────────────────
_base_from_env = os.getenv("MCP_BASE_URL") or os.getenv("MCP_HTTP_URL", "http://127.0.0.1:5177")
MCP_BASE_URL = _base_from_env.replace("/mcp", "").rstrip("/")
MCP_USE_HTTP = os.getenv("MCP_USE_HTTP", "1") == "1"  # ← 필요시 0으로 꺼도 됨

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
    templates: Templates = Field(
        default_factory=lambda: Templates(attacker="ATTACKER_PROMPT_V1", victim="VICTIM_PROMPT_V1")
    )
    models: Optional[Dict[str, str]] = None
    attacker_model: Optional[str] = None
    victim_model: Optional[str] = None
    max_turns: int = 15
    guidance: Optional[Guidance] = None
    case_id_override: Optional[str] = None
    round_no: Optional[int] = None
    combined_prompt: Optional[str] = None

class SingleData(BaseModel):
    data: dict = Field(...)

# ───────── 유틸 ─────────
def _unwrap(data: Any) -> Dict[str, Any]:
    if isinstance(data, dict):
        if set(data.keys()) == {"data"} and isinstance(data["data"], dict):
            return data["data"]
        return data
    if data is None:
        raise ValueError("Action Input is None")

    s = str(data).strip()
    if s.startswith("```"):
        m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S | re.I)
        if m:
            s = m.group(1).strip()

    i = s.find("{")
    if i > 0:
        s = s[i:]

    dec = JSONDecoder()
    try:
        obj, _ = dec.raw_decode(s)
    except Exception:
        m = re.search(r"\{.*\}", s, re.S)
        if not m:
            raise ValueError("No JSON object found in action input")
        sub = m.group(0)
        try:
            obj = json.loads(sub)
        except Exception:
            try:
                pyobj = ast.literal_eval(sub)
                if not isinstance(pyobj, dict):
                    raise ValueError("Parsed object is not a dict")
                obj = pyobj
            except Exception as e:
                raise ValueError(f"Unable to parse Action Input: {e}")

    if isinstance(obj, dict) and "payload_key" in obj:
        loaded = load_payload(obj["payload_key"])
        if loaded is None:
            raise ValueError(f"payload_key not found or expired: {obj['payload_key']}")
        obj = loaded

    if isinstance(obj, dict) and set(obj.keys()) == {"data"} and isinstance(obj["data"], dict):
        return obj["data"]

    if not isinstance(obj, dict):
        raise ValueError("Action Input did not resolve to a dict")

    return obj

def _post_api_simulate(arguments: Dict[str, Any]) -> Dict[str, Any]:
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

    if isinstance(data, dict) and "ok" in data:
        return data
    return {"ok": True, "result": data}

def make_mcp_tools():
    @tool(
        "mcp.simulator_run",
        description="MCP 서버의 POST /api/simulate 를 호출해 두-봇 시뮬레이션을 실행합니다. (오케스트레이터가 서버 로그의 [conversation_log]를 분해해 턴 단위 SSE로 중계)"
    )
    def simulator_run(data: Any) -> Dict[str, Any]:
        # ---------- 1) 입력 언랩 ----------
        payload = _unwrap(data)
        if isinstance(payload, dict) and "payload_key" in payload:
            stored = load_payload(payload["payload_key"])
            if not isinstance(stored, dict):
                return {"ok": False, "error": "payload_key_not_found", "hint": "expired or missing"}
            payload = stored

        if "case_id" in payload and "case_id_override" not in payload:
            payload["case_id_override"] = payload["case_id"]

        # ---------- 2) 검증 ----------
        try:
            model = MCPRunInput.model_validate(payload)
        except ValidationError as ve:
            return {
                "ok": False,
                "error": "Invalid Action Input for mcp.simulator_run",
                "pydantic_errors": json.loads(ve.json()),
            }

        # ---------- 3) 모델/프롬프트 정규화 ----------
        eff_models: Dict[str, str] = {}
        if isinstance(model.models, dict):
            eff_models.update({k: v for k, v in model.models.items() if isinstance(v, str) and v})
        if model.attacker_model: eff_models["attacker"] = model.attacker_model
        if model.victim_model:   eff_models["victim"]   = model.victim_model
        if eff_models:
            logger.info(f"[MCP] using explicit models: {eff_models}")

        atk_system = payload.get("attacker_prompt") or None
        vic_system = payload.get("victim_prompt") or None

        if not atk_system:
            try:
                atk_system = render_attacker_system_string(
                    scenario=model.scenario or {}, current_step="", guidance=(model.guidance.model_dump() if model.guidance else None),
                )
            except Exception as e:
                logger.warning(f"[MCP] render_attacker_system_string failed: {e}")
                atk_system = None
        if not vic_system:
            try:
                vic_system = render_victim_system_string(
                    victim_profile=model.victim_profile or {}, round_no=int(model.round_no or 1),
                    previous_experience="", is_convinced_prev=None,
                )
            except Exception as e:
                logger.warning(f"[MCP] render_victim_system_string failed: {e}")
                vic_system = None

        if atk_system is None: atk_system = model.templates.attacker
        if vic_system is None: vic_system = model.templates.victim

        token_templates = {"attacker": model.templates.attacker, "victim": model.templates.victim}

        # ---------- 4) 서버 스키마에 맞게 arguments 구성 ----------
        args: Dict[str, Any] = {
            "offender_id": model.offender_id,
            "victim_id": model.victim_id,
            "scenario": model.scenario,
            "victim_profile": model.victim_profile,
            "templates": token_templates,
            "max_turns": model.max_turns,
        }
        if model.guidance:
            args["guidance"] = {GUIDANCE_KEY: model.guidance.type, "text": model.guidance.text}
        if model.case_id_override:
            args["case_id_override"] = model.case_id_override
        if model.round_no:
            args["round_no"] = model.round_no
            
        # ✅ A-방식 핵심: stream_id가 들어왔으면 그대로 전달
        sid = None
        try:
            sid = payload.get("stream_id")
        except Exception:
            sid = None
        if sid:
            args["stream_id"] = sid        

        if SEND_SYSTEM_PROMPTS:
            args["attacker_prompt"] = atk_system
            args["victim_prompt"] = vic_system
        if eff_models:
            args["models"] = eff_models

        logger.info(f"[MCP] POST /api/simulate keys={list(args.keys())} base={MCP_BASE_URL}")

        if not MCP_USE_HTTP:
            # 필요하면 여기서 로컬 엔진으로 직접 붙이는 분기 넣으면 됨.
            return {"ok": False, "error": "http_disabled", "hint": "Set MCP_USE_HTTP=1 or implement local engine"}

        # ---------- 5) HTTP 호출 ----------
        res = _post_api_simulate(args)

        # 실패면 재시도(최소 페이로드)
        if isinstance(res, dict) and res.get("ok") is False:
            return res
        #     if res.get("error") == "http_error" and int(res.get("status") or 0) == 500:
        #         logger.warning("[MCP] 500 → 최소 페이로드 재시도")
        #         minimal_args = {
        #             "offender_id": model.offender_id,
        #             "victim_id": model.victim_id,
        #             "scenario": model.scenario,
        #             "victim_profile": model.victim_profile,
        #             "templates": token_templates,
        #             "max_turns": model.max_turns,
        #         }
        #         if model.guidance:
        #             minimal_args["guidance"] = {GUIDANCE_KEY: model.guidance.type, "text": model.guidance.text}
        #         if model.case_id_override:
        #             minimal_args["case_id_override"] = model.case_id_override
        #         if model.round_no:
        #             minimal_args["round_no"] = model.round_no
        #         if eff_models:
        #             minimal_args["models"] = eff_models

        #         res2 = _post_api_simulate(minimal_args)
        #         if isinstance(res2, dict) and res2.get("ok") is False:
        #             return res2
        #         res = res2
        #     else:
        #         return res

        # ---------- 6) 응답 평탄화 ----------
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
                result = result["result"]; continue
            raw = result.get("raw")
            if isinstance(raw, dict) and isinstance(raw.get("result"), dict):
                result = raw["result"]; continue
            break

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

        return {
            "ok": True,
            "case_id": cid,
            "turns": turns,
            "stats": stats,
            "ended_by": ended_by,
            "meta": meta,
            "log": result,
            "total_turns": stats.get("turns"),
            "debug_templates": {"attacker": atk_system, "victim": vic_system},
        }

    return [simulator_run]
