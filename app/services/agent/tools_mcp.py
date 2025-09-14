# app/services/agent/tools_mcp.py
from __future__ import annotations
from typing import Dict, Any, Optional, Literal
from datetime import datetime
import asyncio, json, threading

from pydantic import BaseModel, Field
from langchain_core.tools import tool
import websockets
from websockets.server import serve
from app.core.logging import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────
# 유틸: 루프 유무에 안전하게 코루틴 실행
# ─────────────────────────────────────────────────────────
def run_coro_safely(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(lambda: asyncio.run(coro))
            return fut.result()

# ─────────────────────────────────────────────────────────
# 입력 스키마
# ─────────────────────────────────────────────────────────
class Templates(BaseModel):
    attacker: str = Field(..., description="공격자 프롬프트 템플릿 ID")
    victim: str = Field(..., description="피해자 프롬프트 템플릿 ID")

class Guidance(BaseModel):
    type: Literal["A","P"]
    text: str

class MCPRunInput(BaseModel):
    offender_id: int
    victim_id: int
    scenario: Dict[str, Any]
    victim_profile: Dict[str, Any]
    templates: Templates
    guidance: Optional[Guidance] = None
    max_turns: int = 15

# {"data": {...}} 또는 {...} 모두 허용
class SingleData(BaseModel):
    data: Any

def _unwrap(obj: Any) -> Dict[str, Any]:
    """LangChain Action Input 견고 언래핑."""
    from pydantic import BaseModel as _PydBase

    if isinstance(obj, _PydBase):
        obj = obj.model_dump()

    if isinstance(obj, (bytes, bytearray)):
        obj = obj.decode()

    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            raise ValueError("Action Input은 JSON 문자열이거나 객체여야 합니다.")

    for _ in range(3):
        if isinstance(obj, dict) and "data" in obj:
            inner = obj["data"]
            if isinstance(inner, (bytes, bytearray)):
                inner = inner.decode()
            if isinstance(inner, str):
                try:
                    obj = json.loads(inner)
                    continue
                except Exception:
                    obj = {"data": inner}
                    break
            else:
                obj = inner
                continue
        break

    if not isinstance(obj, dict):
        raise ValueError("Action Input은 JSON 객체여야 합니다.")
    return obj

# ─────────────────────────────────────────────────────────
# On-demand MCP 서버
# ─────────────────────────────────────────────────────────
class OnDemandMCPManager:
    def __init__(self):
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.server = None
        self.is_running = False
        self.url = "ws://127.0.0.1:8001/mcp"
        self._ready = threading.Event()

    async def start_mcp_server_if_needed(self) -> str:
        if self.is_running:
            return self.url
        try:
            self._ready.clear()
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            # 서버 준비 신호 대기
            for _ in range(40):
                if self._ready.wait(timeout=0.1):
                    break
                await asyncio.sleep(0.05)
            if not self._ready.is_set():
                raise RuntimeError("MCP 서버 준비 실패(ready 신호 타임아웃)")
            self.is_running = True
            return self.url
        except Exception as e:
            logger.error(f"MCP 서버 시작 실패: {e}")
            raise

    async def _start_embedded_mcp_server(self):
        async def mcp_handler(websocket, path):
            try:
                async for message in websocket:
                    msg = json.loads(message)
                    response = await self._handle_mcp_message(msg)
                    if response:
                        await websocket.send(json.dumps(response))
            except Exception as e:
                logger.error(f"[MCP] 핸들러 오류: {e}")

        self.server = await serve(
            mcp_handler, "127.0.0.1", 8001,
            ping_interval=30, ping_timeout=120, close_timeout=10, max_queue=None
        )
        logger.info("MCP 서버 시작: ws://127.0.0.1:8001/mcp")

    async def _handle_mcp_message(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        msg_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params", {}) or {}

        # initialize 응답
        if method == "initialize":
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "serverInfo": {"name": "on-demand-mcp", "version": "1.0.0"},
                    "capabilities": {"tools": {"listChanged": True}}
                }
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "tools": [{
                        "name": "simulator.run",
                        "description": "Run a two-bot phishing simulation with templated prompts.",
                        "inputSchema": MCPRunInput.model_json_schema()
                    }]
                }
            }

        if method == "tools/call":
            name = params.get("name")
            if name != "simulator.run":
                return {"jsonrpc": "2.0", "id": msg_id,
                        "error": {"code": -32601, "message": f"Unknown tool: {name}"}}
            arguments = params.get("arguments", {}) or {}
            try:
                result = await asyncio.to_thread(self._run_simulation_directly_blocking, arguments)
                return {"jsonrpc": "2.0", "id": msg_id, "result": {"content": result}}
            except Exception as e:
                logger.exception("[MCP] simulator.run 실행 오류")
                return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32000, "message": str(e)}}

        return None

    def _run_loop(self):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            async def _start():
                await self._start_embedded_mcp_server()
                self._ready.set()

            self.loop.run_until_complete(_start())
            self.loop.run_forever()
        except Exception as e:
            logger.error(f"MCP 루프 실행 오류: {e}")
        finally:
            if self.loop:
                pending = asyncio.all_tasks(loop=self.loop)
                for t in pending:
                    t.cancel()
                try:
                    self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
                self.loop.close()

    def _run_simulation_directly_blocking(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        실제 시뮬레이션 엔진 호출(블로킹). args는 MCPRunInput와 동일한 구조.
        """
        from app.db.session import SessionLocal
        from app.services.simulation import run_two_bot_simulation
        from types import SimpleNamespace

        db = SessionLocal()
        try:
            sim_request = SimpleNamespace(
                offender_id=int(args.get("offender_id")),
                victim_id=int(args.get("victim_id")),
                case_scenario=args.get("scenario") or {},
                victim_profile=args.get("victim_profile") or {},
                templates=args.get("templates") or {},
                guidance=args.get("guidance"),
                max_turns=int(args.get("max_turns", 15)),
                include_judgement=True,
                use_agent=True,
            )
            case_id, total_turns = run_two_bot_simulation(db, sim_request)
            # ✅ 표준화된 구조로 반환 (상위 WS 레이어 없이도 안전)
            return {
                "ok": True,
                "case_id": str(case_id),
                "offender_id": sim_request.offender_id,
                "victim_id": sim_request.victim_id,
                "total_turns": total_turns,
                "timestamp": datetime.now().isoformat()
            }
        finally:
            db.close()

    def stop_mcp_server(self):
        if not self.is_running or not self.loop:
            return

        async def _shutdown():
            if self.server is not None:
                self.server.close()
                await self.server.wait_closed()

        fut = asyncio.run_coroutine_threadsafe(_shutdown(), self.loop)
        try:
            fut.result(timeout=2)
        except Exception:
            pass

        self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

        self.is_running = False
        logger.info("MCP 서버 종료됨")

# ─────────────────────────────────────────────────────────
# LangChain Tool
# ─────────────────────────────────────────────────────────
def make_mcp_tools(mcp_manager: Optional[OnDemandMCPManager] = None):
    mgr = mcp_manager or OnDemandMCPManager()

    @tool(
        "mcp.simulator_run",
        args_schema=SingleData,
        description="내장 MCP 서버를 on-demand로 기동하고, WS JSON-RPC로 simulator.run을 호출해 템플릿 기반 2-봇 시뮬레이션을 수행합니다.",
    )
    def simulator_run(data: Any) -> Dict[str, Any]:
        """템플릿/프로필/지침을 포함해 시뮬레이터를 실행합니다."""
        payload = _unwrap(data)

        # 1라운드 가드: case_id/round_no 없으면 guidance 무시
        round_no = payload.get("round_no")
        case_id  = payload.get("case_id") or payload.get("case_id_override")
        if payload.get("guidance") and not case_id and (round_no is None or int(round_no) <= 1):
            logger.info("[mcp.simulator_run] guidance provided before first run → ignored")
            payload.pop("guidance", None)

        # 레거시 보정: top-level attacker_prompt/victim_prompt → templates로 이식
        if "templates" not in payload:
            if "attacker_prompt" in payload or "victim_prompt" in payload:
                payload["templates"] = {}
                if "attacker_prompt" in payload:
                    payload["templates"]["attacker"] = payload.pop("attacker_prompt")
                if "victim_prompt" in payload:
                    payload["templates"]["victim"] = payload.pop("victim_prompt")

        # 템플릿 키 호환
        if "templates" in payload and isinstance(payload["templates"], dict):
            t = payload["templates"]
            if "attacker" not in t and "attacker_prompt" in t:
                t["attacker"] = t.pop("attacker_prompt")
            if "victim" not in t and "victim_prompt" in t:
                t["victim"] = t.pop("victim_prompt")

        logger.info(f"[mcp.simulator_run] payload_keys={list(payload.keys())}, templates={payload.get('templates')}")

        # 스키마 검증
        from pydantic import ValidationError
        try:
            model = MCPRunInput.model_validate(payload)
        except ValidationError as ve:
            example = {
                "data": {
                    "offender_id": 1,
                    "victim_id": 1,
                    "scenario": {"description": "...", "steps": ["..."]},
                    "victim_profile": {"meta": {}, "knowledge": {}, "traits": {}},
                    "templates": {"attacker": "ATTACKER_PROMPT_V1", "victim": "VICTIM_PROMPT_V1"},
                    "max_turns": 15
                }
            }
            logger.error(f"[mcp.simulator_run] bad payload: {payload}")
            return {
                "ok": False,
                "error": "Invalid Action Input for mcp.simulator_run",
                "hint": "mcp.simulator_run은 offender_id, victim_id, scenario, victim_profile, templates가 필요합니다.",
                "expected_shape": example,
                "pydantic_errors": json.loads(ve.json())
            }

        # 서버 기동
        run_coro_safely(mgr.start_mcp_server_if_needed())

        async def _call_ws() -> Dict[str, Any]:
            try:
                async with websockets.connect(
                    mgr.url,
                    open_timeout=15,
                    ping_interval=30,
                    ping_timeout=120,
                    close_timeout=10,
                    max_queue=None,
                ) as websocket:
                    # initialize
                    await websocket.send(json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}))
                    await websocket.recv()

                    arguments = {
                        "offender_id": model.offender_id,
                        "victim_id": model.victim_id,
                        "scenario": model.scenario,
                        "victim_profile": model.victim_profile,
                        "templates": {"attacker": model.templates.attacker, "victim": model.templates.victim},
                        "max_turns": model.max_turns,
                    }
                    if model.guidance:
                        arguments["guidance"] = {"type": model.guidance.type, "text": model.guidance.text}

                    logger.info(f"[MCP/ws] simulate args(offender_id={model.offender_id}, victim_id={model.victim_id}, max_turns={model.max_turns}, has_guidance={bool(model.guidance)})")

                    await websocket.send(json.dumps({
                        "jsonrpc":"2.0","id":2,"method":"tools/call",
                        "params":{"name":"simulator.run","arguments": arguments}
                    }))
                    resp = await websocket.recv()
                    data = json.loads(resp)
                    content = (data.get("result") or {}).get("content", {}) or {}

                    # content 예: {"ok": True, "case_id": "...", "total_turns": N, "timestamp": "..."}
                    if isinstance(content, dict) and "case_id" in content:
                        content.update({
                            "ok": True,
                            "offender_id": model.offender_id,
                            "victim_id": model.victim_id,
                            "max_turns": model.max_turns,
                        })
                    else:
                        content = {
                            "ok": False,
                            "error": "simulator.run 응답에 case_id 없음",
                        }
                    return content
            except Exception as e:
                logger.error(f"[MCP/ws] 통신 실패: {e}")
                return {"ok": False, "error": str(e)}

        return run_coro_safely(_call_ws())

    # ▼▼▼ 새 툴: 최근 케이스 조회 (ConversationLog → AdminCase 경유) ▼▼▼
    @tool(
        "mcp.latest_case",
        args_schema=SingleData,
        description="offender_id, victim_id로 가장 최근 시뮬레이션 케이스(case_id)를 조회합니다. LLM이 case_id를 잃었을 때 복구용."
    )
    def latest_case(data: Any) -> Dict[str, Any]:
        payload = _unwrap(data)
        offender_id = int(payload.get("offender_id", 0))
        victim_id = int(payload.get("victim_id", 0))
        if not offender_id or not victim_id:
            return {"ok": False, "error": "offender_id와 victim_id가 필요합니다."}

        from app.db.session import SessionLocal
        from app.db.models import ConversationLog, AdminCase

        db = SessionLocal()
        try:
            # offender_id, victim_id에 대한 최신 대화 로그 → case_id 획득
            row = (
                db.query(ConversationLog)
                  .filter(
                      ConversationLog.offender_id == offender_id,
                      ConversationLog.victim_id == victim_id
                  )
                  .order_by(ConversationLog.created_at.desc())
                  .first()
            )
            if not row:
                return {"ok": False, "error": "해당 offender_id/victim_id의 최근 케이스가 없습니다."}

            case = db.query(AdminCase).filter(AdminCase.id == row.case_id).first()
            status = getattr(case, "status", None) if case else None
            created_at = getattr(case, "created_at", None) if case else None

            return {
                "ok": True,
                "case_id": str(row.case_id),
                "offender_id": offender_id,
                "victim_id": victim_id,
                "status": status,
                "created_at": created_at.isoformat() if created_at else None,
            }
        except Exception as e:
            logger.exception("[mcp.latest_case] 조회 실패")
            return {"ok": False, "error": str(e)}
        finally:
            db.close()

    return [simulator_run, latest_case], mgr
