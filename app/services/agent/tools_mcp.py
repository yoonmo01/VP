# app/services/agent/tools_mcp.py
from __future__ import annotations
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
import json
import threading

from pydantic import BaseModel
from langchain_core.tools import tool

# 외부 라이브러리
import websockets
from websockets.server import serve

from app.core.logging import get_logger
logger = get_logger(__name__)


# ----------------------------
# 유틸 (비동기 안전 실행)
# ----------------------------
def run_coro_safely(coro):
    """현재 루프가 없으면 asyncio.run, 있으면 별도 스레드에서 실행."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(lambda: asyncio.run(coro))
            return fut.result()


# ----------------------------
# OnDemand MCP Server Manager
# ----------------------------
class OnDemandMCPManager:
    """필요할 때만 MCP 서버를 시작/종료하는 관리자 (단일 모듈로 분리해 순환 임포트 방지)"""

    def __init__(self):
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.server = None
        self.is_running = False
        self.url = "ws://127.0.0.1:8001/mcp"
        self._ready = threading.Event()

    async def start_mcp_server_if_needed(self) -> str:
        """MCP 서버가 꺼져 있으면 기동하고 URL 반환."""
        if self.is_running:
            return self.url

        try:
            self._ready.clear()
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            # 서버 준비 완료 신호 대기
            for _ in range(20):
                if self._ready.wait(timeout=0.1):
                    break
                await asyncio.sleep(0.05)
            if not self._ready.is_set():
                raise RuntimeError("MCP 서버 준비 신호 수신 실패")
            self.is_running = True
            return self.url
        except Exception as e:
            logger.error(f"MCP 서버 시작 실패: {e}")
            return None

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

        # ws://127.0.0.1:8001/mcp
        self.server = await serve(
            mcp_handler, "127.0.0.1", 8001,
            ping_interval=30, ping_timeout=120, close_timeout=10, max_queue=None
        )
        logger.info("MCP 서버가 ws://127.0.0.1:8001/mcp 에서 시작됨")

    async def _handle_mcp_message(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        msg_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "serverInfo": {"name": "on-demand-mcp", "version": "1.0.0"},
                    "capabilities": {"tools": {"listChanged": True}}
                }
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "tools": [{
                        "name": "simulator.run",
                        "description": "Run simulation",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "offender_id": {"type": "integer"},
                                "victim_id": {"type": "integer"},
                                "scenario": {"type": "object"},
                                "max_turns": {
                                    "type": "integer",
                                    "description": "한 사이클의 최대 턴(공1+피1=1)"
                                }
                            }
                        }
                    }]
                }
            }

        elif method == "tools/call":
            args = params.get("arguments", {})
            try:
                result = await asyncio.to_thread(self._run_simulation_directly_blocking, args)
            except Exception as e:
                logger.exception("[MCP] simulator.run 실행 오류")
                return {
                    "jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32000, "message": str(e)}
                }
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"content": result}}

        # 알 수 없는 메서드
        return None

    def _run_loop(self):
        """임베디드 서버를 별도 이벤트 루프/스레드에서 구동."""
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
            pending = asyncio.all_tasks(loop=self.loop)
            for t in pending:
                t.cancel()
            try:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            self.loop.close()

    def _run_simulation_directly_blocking(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """(블로킹) 실제 시뮬레이션 엔진 호출 - 별도 스레드에서 실행."""
        from app.db.session import SessionLocal
        from app.services.simulation import run_two_bot_simulation
        from types import SimpleNamespace

        db = SessionLocal()
        try:
            sim_request = SimpleNamespace(
                offender_id=args.get("offender_id", 1),
                victim_id=args.get("victim_id", 1),
                max_turns=args.get("max_turns", 15),    # ✅ max_turns 일관
                case_scenario=args.get("scenario", {}),
                include_judgement=True,
                use_agent=True,
            )
            case_id, total_turns = run_two_bot_simulation(db, sim_request)
            return {
                "case_id": str(case_id),
                "total_turns": total_turns,
                "timestamp": datetime.now().isoformat(),
            }
        finally:
            db.close()

    def stop_mcp_server(self):
        """서버/루프 안전 종료."""
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


# ----------------------------
# LangChain Tool 정의
# ----------------------------
class MCPRunInput(BaseModel):
    offender_id: int
    victim_id: int
    scenario: Dict[str, Any] = {}
    max_turns: int = 15


def make_mcp_tools(mcp_manager: Optional[OnDemandMCPManager] = None):
    """
    오케스트레이터/에이전트에 등록할 MCP 호출용 LangChain 툴.
    - 순환 임포트 없도록 이 파일만으로 self-contained
    """
    mgr = mcp_manager or OnDemandMCPManager()

    @tool("mcp.simulator_run", args_schema=MCPRunInput,description="내장 MCP 서버를 on-demand로 띄우고 WS로 simulator.run을 호출해 시뮬레이션을 수행한다.")
    def simulator_run(
        offender_id: int,
        victim_id: int,
        scenario: Dict[str, Any],
        max_turns: int = 15
    ) -> Dict[str, Any]:
        """
        내장 MCP 서버를 on-demand로 띄우고, WS로 simulator.run 호출.
        """
        # 1) 서버 기동
        mcp_url = run_coro_safely(mgr.start_mcp_server_if_needed())
        if not mcp_url:
            return {"error": "MCP start failed"}

        # 2) 클라이언트로 JSON-RPC 호출
        async def _call_ws() -> Dict[str, Any]:
            try:
                async with websockets.connect(
                    mcp_url,
                    open_timeout=15,
                    ping_interval=30,
                    ping_timeout=120,
                    close_timeout=10,
                    max_queue=None,
                ) as websocket:
                    # initialize
                    init_msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
                    await websocket.send(json.dumps(init_msg))
                    await websocket.recv()

                    # tools/call simulator.run
                    sim_msg = {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "simulator.run",
                            "arguments": {
                                "offender_id": offender_id,
                                "victim_id": victim_id,
                                "scenario": scenario,
                                "max_turns": max_turns,  # ✅ max_turns 일관
                            }
                        }
                    }
                    logger.info(
                        "[MCP/ws] tools/call simulator.run "
                        f"(offender_id={offender_id}, victim_id={victim_id}, max_turns={max_turns})"
                    )
                    await websocket.send(json.dumps(sim_msg))
                    response = await websocket.recv()
                    data = json.loads(response)
                    return (data.get("result") or {}).get("content", {}) or {}
            except Exception as e:
                logger.error(f"[MCP/ws] 통신 실패: {e}")
                return {"error": str(e)}

        return run_coro_safely(_call_ws())

    # 툴 리스트와 매니저를 함께 반환(오케스트레이터에서 stop 용이)
    return [simulator_run], mgr
