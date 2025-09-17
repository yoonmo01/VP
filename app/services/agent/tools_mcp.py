# app/services/agent/tools_mcp.py
from __future__ import annotations
from typing import Any, Dict, Optional, Literal
import os, json
from json import JSONDecoder
import httpx
from pydantic import BaseModel, Field, ValidationError
from langchain_core.tools import tool
from app.core.logging import get_logger
import re

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────
# MCP 서버 베이스 URL
#   - 권장: MCP_BASE_URL (예: http://127.0.0.1:5177)
#   - 하위호환: MCP_HTTP_URL (예: http://127.0.0.1:5177/mcp) -> 베이스만 추출
# ─────────────────────────────────────────────────────────
_base_from_env = os.getenv("MCP_BASE_URL") or os.getenv("MCP_HTTP_URL", "http://127.0.0.1:5177")
MCP_BASE_URL = _base_from_env.replace("/mcp", "").rstrip("/")

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
    """
    if isinstance(data, dict):
        if set(data.keys()) == {"data"} and isinstance(data["data"], dict):
            return data["data"]               # ✅ 최상위 'data' 벗기기
        return data

    if data is None:
        raise ValueError("Action Input is None")

    s = str(data).strip()

    # 코드펜스 제거
    if s.startswith("```"):
        m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S | re.I)
        if m:
            s = m.group(1).strip()

    # "Action Input: ..." 같은 접두 텍스트 제거 → 첫 '{'부터
    i = s.find("{")
    if i > 0:
        s = s[i:]

    dec = JSONDecoder()
    obj, end = dec.raw_decode(s)  # 첫 JSON만 파싱

    # ✅ 문자열로 들어온 경우도 'data' 래퍼 벗기기
    if isinstance(obj, dict) and set(obj.keys()) == {"data"} and isinstance(obj["data"], dict):
        return obj["data"]

    return obj

# def _unwrap_forgiving(obj: dict) -> dict:
#     """
#     {"data":{...}, "guidance":..., "round_no":..., "case_id_override":...}
#     처럼 섞여 들어와도 data 안으로 병합해서 돌려줌.
#     """
#     if "data" in obj and isinstance(obj["data"], dict):
#         merged = dict(obj["data"])
#         # 루트에 잘못 나온 키들을 흡수
#         for k in ("case_id_override", "round_no", "guidance"):
#             if k in obj and k not in merged:
#                 merged[k] = obj[k]
#         return merged
#     return obj

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
        # ---------- 1) 입력 언랩 + 통짜 프롬프트 자동 구성 ----------
        payload = _unwrap(data)


        # case_id 별칭 지원
        if "case_id" in payload and "case_id_override" not in payload:
            payload["case_id_override"] = payload["case_id"]

        # compose_prompts 결과 자동 합치기(있을 때만)
        ap = payload.get("attacker_prompt")
        vp = payload.get("victim_prompt")
        if ap and vp and "combined_prompt" not in payload:
            payload["combined_prompt"] = f"[ATTACKER]\n{ap}\n[/ATTACKER]\n[VICTIM]\n{vp}\n[/VICTIM]"

        # 라운드1 가드: case_id 없이 guidance가 오면 무시
        round_no = payload.get("round_no")
        case_id = payload.get("case_id_override")
        if payload.get("guidance") and not case_id and (round_no is None or int(round_no) <= 1):
            logger.info("[mcp.simulator_run] guidance before first run → ignored")
            payload.pop("guidance", None)

        # ---------- 2) 1회만 검증 ----------
        try:
            model = MCPRunInput.model_validate(payload)
        except ValidationError as ve:
            return {
                "ok": False,
                "error": "Invalid Action Input for mcp.simulator_run",
                "pydantic_errors": json.loads(ve.json()),
            }

        # ---------- 3) 모델 키 정규화 (attacker_model/victim_model → models.attacker/victim) ----------
        eff_models: Dict[str, str] = {}
        if isinstance(model.models, dict):
            eff_models.update({k: v for k, v in model.models.items() if isinstance(v, str) and v})
        if model.attacker_model:
            eff_models["attacker"] = model.attacker_model
        if model.victim_model:
            eff_models["victim"] = model.victim_model
        if eff_models:
            logger.info(f"[MCP] using explicit models: {eff_models}")

        # ---------- 4) 서버 스키마에 맞게 arguments 구성 ----------
        args: Dict[str, Any] = {
            "offender_id": model.offender_id,
            "victim_id": model.victim_id,
            "scenario": model.scenario,
            "victim_profile": model.victim_profile,
            "templates": {"attacker": model.templates.attacker, "victim": model.templates.victim},
            "max_turns": model.max_turns,
        }
        if model.guidance:
            # 서버가 guidance 키를 'kind'로 요구한다면 아래 한 줄만 바꾸면 됨:
            # args["guidance"] = {"kind": model.guidance.type, "text": model.guidance.text}
            args["guidance"] = {"type": model.guidance.type, "text": model.guidance.text}
        if model.case_id_override:
            args["case_id_override"] = model.case_id_override
        if model.round_no:
            args["round_no"] = model.round_no
        if model.combined_prompt:
            args["combined_prompt"] = model.combined_prompt
        # ★ 개별 프롬프트도 같이 전달(서버가 최우선 사용)
        if ap and vp:
            args["attacker_prompt"] = ap
            args["victim_prompt"] = vp
        # 모델 전달(선택)
        if eff_models:
            args["models"] = eff_models

        logger.info(f"[MCP] POST /api/simulate keys={list(args.keys())} base={MCP_BASE_URL}")

        # ---------- 5) 호출 ----------
        res = _post_api_simulate(args)

        # 서버가 실패 형식으로 주는 경우 그대로 반환
        if isinstance(res, dict) and res.get("ok") is False:
            return res

        # ---------- 6) 응답 평탄화(핵심) ----------
        # 서버 응답은 대개 {"result": {...}} 또는 {"raw": {"result": {...}}} 형태일 수 있다.
        result = None
        if isinstance(res, dict):
            if isinstance(res.get("result"), dict):
                result = res["result"]
            elif isinstance(res.get("raw"), dict) and isinstance(res["raw"].get("result"), dict):
                result = res["raw"]["result"]

        if not isinstance(result, dict):
            return {"ok": False, "error": "bad_simulator_payload", "raw": res}

        # 여러 경로에서 conversation_id를 튼튼하게 추출
        cid = (
            result.get("conversation_id")
            or result.get("case_id")
            or (result.get("meta") or {}).get("conversation_id")
        )

        if not cid:
            # 과거 코드에서는 이 지점에서 ok: False를 반환했기 때문에 항상 실패처럼 보였을 수 있음
            return {"ok": False, "error": "missing_conversation_id", "raw": result}

        turns = result.get("turns") or []
        stats = result.get("stats") or {}
        ended_by = result.get("ended_by")
        meta = result.get("meta") or {}

        # ---------- 7) 표준화된 성공 응답 ----------
        return {
            "ok": True,
            "case_id": cid,
            "turns": turns,
            "stats": stats,
            "ended_by": ended_by,
            "meta": meta,
            "log": result,        # ★ admin 판단에 그대로 넘길 전체 로그
            "total_turns": stats.get("turns"),
        }

    return [simulator_run]
