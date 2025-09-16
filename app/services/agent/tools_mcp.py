# app/services/agent/tools_mcp.py
from __future__ import annotations
from typing import Any, Dict, Optional, Literal
import os, json, asyncio
from pydantic import BaseModel, ValidationError
from langchain_core.tools import tool
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession
from app.core.logging import get_logger

logger = get_logger(__name__)
# 서버는 정확히 /mcp (트레일링 슬래시 없음)
MCP_HTTP_URL = os.getenv("MCP_HTTP_URL", "http://127.0.0.1:5177/mcp").rstrip("/")

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
    templates: Templates
    max_turns: int = 15
    guidance: Optional[Guidance] = None
    case_id_override: Optional[str] = None
    round_no: Optional[int] = None

def _unwrap(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, (bytes, bytearray)):
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

# ───────── MCP 호출기 ─────────
async def _mcp_call_http(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    last_err = None
    for attempt in range(3):
        try:
            async with streamablehttp_client(MCP_HTTP_URL) as conn:
                # 반환 타입 방어적 언패킹
                if isinstance(conn, (tuple, list)):
                    if len(conn) == 2:
                        read, write = conn
                    elif len(conn) == 3:
                        read, write, _ = conn
                    else:
                        raise RuntimeError(f"Unexpected connection tuple size: {len(conn)}")
                else:
                    read = getattr(conn, "read", None) or getattr(conn, "reader", None)
                    write = getattr(conn, "write", None) or getattr(conn, "writer", None)
                    if not (read and write):
                        raise RuntimeError("Unsupported streamablehttp_client return type")

                async with ClientSession(read, write) as session:
                    # 일부 환경에서 list_tools()가 초기화 타이밍 이슈를 냄 → echo로 가볍게 연결 체크
                    try:
                        await session.call_tool("system.echo", arguments={"ping": True})
                    except Exception:
                        # echo 없음/오류는 치명적이지 않음. 실제 툴 호출로 진행
                        pass

                    resp = await session.call_tool(tool_name, arguments=arguments)

                    # 1) FastMCP가 content[0].text로 JSON 문자열을 줄 수 있음
                    if resp.content and getattr(resp.content[0], "text", None):
                        text = resp.content[0].text
                        try:
                            return json.loads(text)
                        except Exception:
                            # 서버가 텍스트만 준 경우
                            return {"result": {"raw": text}}

                    # 2) 또는 result dict 필드를 직접 줄 수도 있음
                    if getattr(resp, "result", None):
                        return {"result": resp.result}

                    # 3) 마지막 fallback: content를 통째로 덤프
                    return {"result": [c.model_dump() for c in (resp.content or [])]}
        except Exception as e:
            last_err = e
            logger.warning(f"[MCP] call attempt={attempt+1} failed: {e}")
            # 절대 time.sleep 사용 금지 (async 컨텍스트): 지수적 백오프
            await asyncio.sleep(0.25 * (attempt + 1))

    raise RuntimeError(f"MCP call failed after retries: {last_err}")

def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        # sync 함수 컨텍스트에서 호출되므로, 현재 루프가 있으면 그냥 run_until_complete
        return loop.run_until_complete(coro)

# ───────── LangChain Tool ─────────
def make_mcp_tools():
    @tool(
        "mcp.simulator_run",
        description="외부 MCP 서버의 sim.simulate_dialogue 툴을 호출해 두-봇 시뮬레이션을 실행합니다."
    )
    def simulator_run(data: Any) -> Dict[str, Any]:
        payload = _unwrap(data)

        # 라운드1 가드: case_id 없이 guidance가 오면 무시
        round_no = payload.get("round_no")
        case_id = payload.get("case_id") or payload.get("case_id_override")
        if payload.get("guidance") and not case_id and (round_no is None or int(round_no) <= 1):
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

        logger.info(f"[MCP] call sim.simulate_dialogue args={list(args.keys())} url={MCP_HTTP_URL}")
        res = _run(_mcp_call_http("sim.simulate_dialogue", args))

        # 서버 표준 응답 정규화
        result = res.get("result") or res
        # 서버가 헬퍼에서 {"ok": True/False, "result": {...}} 형태를 주는 경우 우선 확인
        ok = res.get("ok", True)
        if not ok:
            # 서버에서 validation 실패/예외를 JSON으로 반환하는 경우 여기에 걸림
            return {"ok": False, "error": result.get("error") or "mcp_error", "detail": result}

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

    return [simulator_run]
