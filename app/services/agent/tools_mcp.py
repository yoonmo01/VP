# app/services/agent/tools_mcp.py
from __future__ import annotations
from typing import Any, Dict, Optional, Literal
import os, json, asyncio
from pydantic import BaseModel, Field, ValidationError
from langchain_core.tools import tool
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from app.core.logging import get_logger

logger = get_logger(__name__)
MCP_HTTP_URL = os.getenv("MCP_HTTP_URL", "http://127.0.0.1:5177/mcp")  # FastMCP HTTP 엔드포인트

# ───────── 입력 스키마 (App → MCP) ─────────
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
    # (선택) models/temperature를 넘기고 싶으면 여기에 필드 추가

# {"data": {...}} 또는 {...} 허용
def _unwrap(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, bytes):
        obj = obj.decode()
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

async def _mcp_call_http(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    # FastMCP Streamable HTTP로 접속
    async with streamablehttp_client(MCP_HTTP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            tools = await session.list_tools()
            if tool_name not in [t.name for t in tools.tools]:
                raise RuntimeError(f"MCP tool not found: {tool_name}")

            res = await session.call_tool(tool_name, arguments=arguments)
            # FastMCP는 보통 content[0].text에 JSON 문자열을 넣음
            if res.content and getattr(res.content[0], "text", None):
                try:
                    return json.loads(res.content[0].text)
                except Exception:
                    return {"raw": res.content[0].text}
            # 혹은 서버가 dict 자체를 content로 줄 수도 있음
            return {"result": [c.model_dump() for c in (res.content or [])]}

def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        return loop.run_until_complete(coro)

def make_mcp_tools():
    @tool(
        "mcp.simulator_run",
        description="외부 MCP 서버의 sim.simulate_dialogue 툴을 호출하여 두-봇 시뮬레이션을 실행합니다."
    )
    def simulator_run(data: Any) -> Dict[str, Any]:
        payload = _unwrap(data)

        # 1라운드 가드: guidance는 round_no<=1 & case_id 없음이면 제거
        round_no = payload.get("round_no")
        case_id = payload.get("case_id") or payload.get("case_id_override")
        if payload.get("guidance") and (not case_id) and (round_no is None or int(round_no) <= 1):
            logger.info("[mcp.simulator_run] guidance before first run → ignored")
            payload.pop("guidance", None)

        try:
            model = MCPRunInput.model_validate(payload)
        except ValidationError as ve:
            return {
                "ok": False,
                "error": "Invalid Action Input for mcp.simulator_run",
                "pydantic_errors": json.loads(ve.json()),
            }

        # App에서 조립해 넘긴 재료(시나리오/프로필/템플릿ID 등)를 그대로 MCP로 전달
        args = {
            "offender_id": model.offender_id,
            "victim_id": model.victim_id,
            "scenario": model.scenario,
            "victim_profile": model.victim_profile,
            "templates": {"attacker": model.templates.attacker, "victim": model.templates.victim},
            "max_turns": model.max_turns,
        }
        if model.guidance:
            args["guidance"] = {"type": model.guidance.type, "text": model.guidance.text}
        if model.case_id_override:
            args["case_id_override"] = model.case_id_override
        if model.round_no:
            args["round_no"] = model.round_no

        logger.info(f"[MCP] call sim.simulate_dialogue args={list(args.keys())}")
        res = _run(_mcp_call_http("sim.simulate_dialogue", args))
        logger.info(f"[MCP] result sample={str(res)[:300]}")

        # 서버 표준 응답: {"result": {...}} 형태 기대
        result = res.get("result") or res
        # conversation_id → app 표준 case_id로 매핑
        cid = result.get("conversation_id") or result.get("case_id")
        if not cid:
            return {"ok": False, "error": "MCP 응답에 conversation_id/case_id 없음", "raw": res}

        total_turns = (result.get("stats") or {}).get("turns")
        return {
            "ok": True,
            "case_id": cid,
            "total_turns": total_turns,
            "result": result,
        }

    # 선택지 B이므로 여기서는 툴 리스트만 반환
    return [simulator_run]
