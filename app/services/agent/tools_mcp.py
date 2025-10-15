# app/services/agent/tools_mcp.py
from __future__ import annotations
from typing import Any, Dict, Optional, Literal
import os, json, asyncio, threading, re
from json import JSONDecoder
import httpx
from pydantic import BaseModel, Field, ValidationError
from langchain_core.tools import tool
from app.core.logging import get_logger
from datetime import datetime
import re
import websockets
import socket
from langsmith.run_helpers import traceable

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
    data: Any = Field(...)
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

def parse_conversation_logs(text: str, target_round: int | None = None):
    logs = []
    patterns = [
        r'\[Conversation\]\[case:([^\]]+)\]\[run:(\d+)\]\[turn:(\d+)\]\[(offender|victim)\]\s+(.+?)(?=\n\[Conversation\]|$)',
        r'\[Conversation\]\[case:([^\]]+)\]\[run:(\d+)\]\[turn:(\d+)\]\[(offender|victim)\]\s*\n\s*(.+?)(?=\n\[Conversation\]|$)',
    ]
    for pat in patterns:
        for case_id, run, turn, role, content in re.findall(pat, text, re.DOTALL|re.MULTILINE):
            run_no = int(run)
            if target_round is None or target_round == run_no:
                logs.append({
                    "case_id": case_id.strip(),
                    "run": run_no,
                    "turn_index": int(turn),
                    "role": role.strip(),
                    "content": content.strip(),
                    "created_kst": datetime.now().isoformat(),
                })
        if logs:
            break
    return logs


# ─────────────────────────────────────────────────────────
# 유틸: 이벤트루프 안전 실행
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

# 포트용
def _pick_free_port(start=5177, limit=20) -> int:
    for p in range(start, start+limit):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", p))
            except OSError:
                continue
            return p
    raise RuntimeError("free port not found")

# ─────────────────────────────────────────────────────────
# On-demand MCP 서버 (WS JSON-RPC)
# ─────────────────────────────────────────────────────────
class OnDemandMCPManager:
    def __init__(self, port: int | None = None):
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.server = None
        self.is_running = False
        self.url = "ws://127.0.0.1:5177/mcp"
        self._ready = threading.Event()
        self.port = port or int(os.getenv("ONDEMAND_MCP_PORT", "0") or 0)
        self.url = None  # ← 초기엔 없음

    async def start_mcp_server_if_needed(self) -> str:
        if self.is_running and self.url:
            return self.url
        try:
            self._ready.clear()
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            for _ in range(80):
                if self._ready.wait(timeout=0.1):
                    break
                await asyncio.sleep(0.05)
            if not self._ready.is_set():
                raise RuntimeError("MCP 서버 준비 실패(ready 신호 타임아웃)")
            self.is_running = True
            return self.url
        except Exception as e:
            # ✅ 어떤 예외든 1회만 재시도: 포트 자동 재선택
            winerr = getattr(e, "winerror", None)
            err_no = getattr(e, "errno", None)
            logger.warning(f"[MCP] start 실패({type(e).__name__}: {e}) → 다른 포트로 재시도")
            self.stop_mcp_server()
            self.port = 0  # 다음 시작 때 자동 선택
            # 재시작
            self._ready.clear()
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            for _ in range(80):
                if self._ready.wait(timeout=0.1):
                    break
                await asyncio.sleep(0.05)
            if not self._ready.is_set():
                raise RuntimeError("MCP 서버 준비 실패(재시도도 실패)")
            self.is_running = True
            return self.url  # type: ignore

    async def _start_embedded_mcp_server(self):
        from websockets.server import serve

        async def mcp_handler(websocket, path):
            try:
                async for message in websocket:
                    msg = json.loads(message)
                    response = await self._handle_mcp_message(msg)
                    if response:
                        await websocket.send(json.dumps(response))
            except Exception as e:
                logger.error(f"[MCP] 핸들러 오류: {e}")

        if not self.port:
            self.port = _pick_free_port(8001, 50)

        # ✅ 바인딩 재시도 루프 (경쟁 상황 대비)
        for attempt in range(3):
            try:
                self.server = await serve(
                    mcp_handler, "127.0.0.1", self.port,
                    ping_interval=30, ping_timeout=120, close_timeout=10, max_queue=None
                )
                self.url = f"ws://127.0.0.1:{self.port}/mcp"
                logger.info(f"MCP 서버 시작: {self.url}")  # ✅ 실제 포트로 출력
                return
            except OSError as oe:
                win_conflict = getattr(oe, "winerror", None) == 10048
                nix_conflict = getattr(oe, "errno", None) in (48, 98)
                if win_conflict or nix_conflict:
                    logger.warning(f"[MCP] 포트 {self.port} 점유 → 다른 포트로 재시도")
                    self.port = _pick_free_port(8001, 50)
                    continue
                raise

        raise RuntimeError("MCP 서버 포트 바인딩에 3회 실패")

    async def _handle_mcp_message(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        msg_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params", {}) or {}

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

    @traceable(name="mcp.simulator_run", run_type="tool", tags=["voicephish", "mcp"])
    def _run_simulation_directly_blocking(self, args: Dict[str, Any]) -> Dict[str, Any]:
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
                case_id_override=args.get("case_id_override"),
                round_no=args.get("round_no"),
            )

            from langchain_core.runnables import RunnableConfig
            cfg: RunnableConfig = {
                "run_name": "mcp.simulator_run",
                "tags": ["voicephish","mcp",
                        f"offender:{sim_request.offender_id}",
                        f"victim:{sim_request.victim_id}",
                        f"round:{sim_request.round_no or 1}"],
                "metadata": {
                    "case_id_override": str(sim_request.case_id_override) if sim_request.case_id_override else None,
                    "max_turns": sim_request.max_turns,
                    "has_guidance": bool(sim_request.guidance),
                },
            }
            
            case_id, total_turns = run_two_bot_simulation(db, sim_request).with_config(cfg) if hasattr(run_two_bot_simulation, "with_config") else run_two_bot_simulation(db, sim_request)
            
            # ✅ Agent 프로젝트의 ConversationLog 조회
            from app.db.models import ConversationLog
            
            conversations = db.query(ConversationLog).filter(
                ConversationLog.case_id == case_id,
                ConversationLog.run == (args.get("round_no") or 1)
            ).order_by(ConversationLog.turn_index).all()

            # ✅ 디버그 로그 추가
            logger.info(f"[MCP] DB 조회 결과: {len(conversations)}개 로그")
            offender_count = len([c for c in conversations if c.role == "offender"])
            victim_count = len([c for c in conversations if c.role == "victim"])
            logger.info(f"[MCP] 역할별: offender={offender_count}, victim={victim_count}")
            
            # ✅ 포맷팅
            conversation_logs = []
            for conv in conversations:
                conversation_logs.append(
                    f"[Conversation][case:{case_id}][run:{conv.run}][turn:{conv.turn_index}][{conv.role}] {conv.content}"
                )

            return {
                "case_id": str(case_id),
                "total_turns": total_turns,
                "timestamp": __import__("datetime").datetime.now().isoformat(),
                "conversation_logs": "\n".join(conversation_logs),
                "debug_echo": {
                    "offender_id": sim_request.offender_id,
                    "victim_id": sim_request.victim_id,
                    "round_no": sim_request.round_no,
                    "case_id_override": sim_request.case_id_override,
                    "has_guidance": bool(sim_request.guidance),
                }
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


def make_mcp_tools(mcp_controller=None):
    mgr = OnDemandMCPManager()

    @tool(
        "mcp.simulator_run",
        args_schema=SingleData,
        description="내장 MCP 서버를 on-demand로 기동하고, WS JSON-RPC로 simulator.run을 호출해 템플릿 기반 2-봇 시뮬레이션을 수행합니다.",
    )
    def simulator_run(data: Any) -> Dict[str, Any]:
        payload = _unwrap(data)
        round_no = payload.get("round_no")
        case_id  = payload.get("case_id") or payload.get("case_id_override")
        if payload.get("guidance") and not case_id and (round_no is None or int(round_no) <= 1):
            logger.info("[mcp.simulator_run] guidance provided before first run → ignored")
            payload.pop("guidance", None)

        if "templates" not in payload:
            if "attacker_prompt" in payload or "victim_prompt" in payload:
                payload["templates"] = {}
                if "attacker_prompt" in payload:
                    payload["templates"]["attacker"] = payload.pop("attacker_prompt")
                if "victim_prompt" in payload:
                    payload["templates"]["victim"] = payload.pop("victim_prompt")
        if "templates" in payload and isinstance(payload["templates"], dict):
            t = payload["templates"]
            if "attacker" not in t and "attacker_prompt" in t:
                t["attacker"] = t.pop("attacker_prompt")
            if "victim" not in t and "victim_prompt" in t:
                t["victim"] = t.pop("victim_prompt")

        logger.info(f"[mcp.simulator_run] payload_keys={list(payload.keys())}, templates={payload.get('templates')}")

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

        run_coro_safely(mgr.start_mcp_server_if_needed())

        async def _call_ws(mcp_controller: MCPController | None) -> Dict[str, Any]:
            try:
                async with websockets.connect(
                    mgr.url, open_timeout=15, ping_interval=30, ping_timeout=120, close_timeout=10, max_queue=None
                ) as websocket:
                    # 1) init
                    await websocket.send(json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}))
                    await websocket.recv()

                    # 2) call
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
                    if model.case_id_override:
                        arguments["case_id_override"] = model.case_id_override
                    if model.round_no:
                        arguments["round_no"] = model.round_no

                    logger.info(f"[MCP/ws] simulate args={arguments}")
                    await websocket.send(json.dumps({
                        "jsonrpc":"2.0","id":2,"method":"tools/call",
                        "params":{"name":"simulator.run","arguments": arguments}
                    }))

                    final_result: Dict[str, Any] | None = None
                    collected_text_chunks: list[str] = []

                    # 3) 메시지 수신 루프
                    while True:
                        raw = await websocket.recv()
                        data = json.loads(raw)
                        
                        # (a) MCP가 이벤트(턴)를 푸시하는 케이스
                        if "method" in data and data["method"] in ("tools/event", "notification", "simulator/turn"):
                            params = data.get("params") or {}
                            turn = params.get("turn")
                            if turn and mcp_controller:
                                try:
                                    await mcp_controller.emit_turn(
                                        case_id=turn.get("case_id") or arguments.get("case_id_override"),
                                        round_no=int(turn.get("round") or arguments.get("round_no") or 1),
                                        turn_index=int(turn.get("turn_index") or 0),
                                        role=(turn.get("role") or "").lower(),
                                        content=turn.get("content") or "",
                                        created_kst=datetime.now().isoformat(),
                                    )
                                    logger.info("[MCP/ws] ✅ EMIT TURN run=%s turn=%s role=%s", 
                                            turn.get("round"), turn.get("turn_index"), turn.get("role"))
                                except Exception as e:
                                    logger.warning(f"[MCP/ws] emit_turn failed: {e}")
                            if "text" in params:
                                collected_text_chunks.append(params["text"])

                        # (b) 최종 결과 수신
                        elif data.get("id") == 2 and "result" in data:
                            res = data["result"]
                            content = res.get("content") or {}
                            final_result = content if isinstance(content, dict) else {"content": content}
                            break

                    # 4) ✅ 폴백: 최종 결과에서 conversation_logs 파싱하여 emit
                    if final_result and "conversation_logs" in final_result:
                        log_text = final_result["conversation_logs"]
                        if isinstance(log_text, str) and mcp_controller:
                            parsed_logs = parse_conversation_logs(
                                log_text, 
                                target_round=arguments.get("round_no")
                            )
                            
                            logger.info(f"[MCP/ws] 폴백 파싱: {len(parsed_logs)}개 로그")
                            
                            for log in parsed_logs:
                                await mcp_controller.emit_turn(
                                    case_id=log.get("case_id") or arguments.get("case_id_override"),
                                    round_no=log["run"],
                                    turn_index=log["turn_index"],
                                    role=log["role"],
                                    content=log["content"],
                                    created_kst=log["created_kst"],
                                )
                                logger.debug(
                                    f"[MCP/ws] 폴백 EMIT: turn={log['turn_index']}, role={log['role']}"
                                )

                    # 5) 반환값 정리
                    content = final_result or {}
                    if isinstance(content, dict) and "case_id" in content:
                        content.update({
                            "ok": True,
                            "offender_id": model.offender_id,
                            "victim_id": model.victim_id,
                            "max_turns": model.max_turns,
                            "debug_arguments": arguments,
                        })
                    else:
                        content = {"ok": False, "error": "simulator.run 응답에 case_id 없음"}
                    return content

            except Exception as e:
                logger.error(f"[MCP/ws] 통신 실패: {e}")
                return {"ok": False, "error": str(e)}


        return run_coro_safely(_call_ws(mcp_controller))

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
