# app/services/agent/tools_mcp.py
from __future__ import annotations
from typing import Any, Dict, Optional, Literal
import os, json, asyncio
from pydantic import BaseModel, Field, ValidationError
from langchain_core.tools import tool

# ✅ MCP: Streamable HTTP 클라이언트 사용
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.core.logging import get_logger
logger = get_logger(__name__)

# ✅ HTTP 엔드포인트로 변경 (서버는 /mcp 경로를 노출해야 함)
MCP_HTTP_URL = os.getenv("MCP_HTTP_URL", "http://127.0.0.1:5177/mcp")

# ───────── 입력 스키마 (app → MCP) ─────────
class Templates(BaseModel):
    attacker: str
    victim: str

class Guidance(BaseModel):
    type: Literal["A", "P"]
    text: str

class MCPRunInput(BaseModel):
    offender_id: int
    victim_id: int
    scenario: Dict[str, Any]
    victim_profile: Dict[str, Any]
    templates: Templates
    max_turns: int = 15
    guidance: Optional[Guidance] = None
    case_id_override: Optional[str] = None
    round_no: Optional[int] = None
    # (원하면 추가)
    # models: Dict[str, str] = {"attacker": "gpt-4o-mini", "victim": "gemini-1.5-flash"}
    # temperature: float = 0.6

# {"data": {...}} 또는 {...} 허용
def _unwrap(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, str):
        obj = json.loads(obj)
    if isinstance(obj, dict) and "data" in obj:
        inner = obj["data"]
        if isinstance(inner, str):
            return json.loads(inner)
        return inner
    if not isinstance(obj, dict):
        raise ValueError("Action Input은 JSON 객체여야 합니다.")
    return obj

# ───────── MCP 호출기(HTTP) ─────────
async def _mcp_call_http(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    async with streamablehttp_client(MCP_HTTP_URL) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            # (선택) 툴 목록 확인
            tools = await session.list_tools()
            if tool_name not in [t.name for t in tools.tools]:
                raise RuntimeError(f"MCP tool not found: {tool_name}")

            res = await session.call_tool(tool_name, arguments=arguments)

            # 서버가 content[0].text에 JSON 문자열을 넣어 돌려주는 것이 표준적
            if res.content and res.content[0].text is not None:
                text = res.content[0].text
                try:
                    return json.loads(text)
                except Exception:
                    return {"raw": text}

            # 서버가 객체를 직접 싣는 구현이라면(비표준) content[0].json 같은 처리가 필요할 수 있음
            return {}

def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        return loop.run_until_complete(coro)

# ───────── LangChain Tool: mcp.simulator_run ─────────
def make_mcp_tools():
    @tool(
        "mcp.simulator_run",
        description="외부 MCP 서버의 sim.simulate_dialogue 툴을 호출해 두-봇 시뮬레이션을 실행합니다."
    )
    def simulator_run(data: Any) -> Dict[str, Any]:
        payload = _unwrap(data)

        # 1라운드 가드: case_id/round_no 없는데 guidance가 들어오면 제거
        round_no = payload.get("round_no")
        case_id = payload.get("case_id") or payload.get("case_id_override")
        if payload.get("guidance") and not case_id and (round_no is None or int(round_no) <= 1):
            logger.info("[mcp.simulator_run] guidance provided before first run → ignored")
            payload.pop("guidance", None)

        # 스키마 검증
        try:
            model = MCPRunInput.model_validate(payload)
        except ValidationError as ve:
            return {
                "ok": False,
                "error": "Invalid Action Input for mcp.simulator_run",
                "pydantic_errors": json.loads(ve.json()),
            }

        # MCP 서버에 넘길 인자 (SimulationInput과 1:1 매핑)
        args = {
            "offender_id": model.offender_id,
            "victim_id": model.victim_id,
            "scenario": model.scenario,
            "victim_profile": model.victim_profile,
            "templates": {
                "attacker": model.templates.attacker,
                "victim": model.templates.victim
            },
            "max_turns": model.max_turns,
        }
        if model.guidance:
            args["guidance"] = {"type": model.guidance.type, "text": model.guidance.text}
        if model.case_id_override:
            args["case_id_override"] = model.case_id_override
        if model.round_no:
            args["round_no"] = model.round_no

        logger.info(f"[MCP] call sim.simulate_dialogue args={list(args.keys())}")

        # 외부 MCP 호출 (HTTP)
        res = _run(_mcp_call_http("sim.simulate_dialogue", args))

        # 서버 결과 표준화
        # 기대: {"result": {"conversation_id": "...", "turns":[{role,text}...], ...}}
        result = res.get("result") or res
        cid = result.get("conversation_id")
        if not cid:
            return {"ok": False, "error": "MCP 응답에 conversation_id 없음", "raw": res}

        return {
            "ok": True,
            "case_id": cid,
            "total_turns": (result.get("stats", {}) or {}).get("turns"),
            "result": result,
        }

    return [simulator_run]
