"""
MCP 서버 실행 제어 모듈
라운드 제한 및 종료 조건을 강제합니다.
"""
from typing import Optional, Any, Dict
from app.core.logging import get_logger
import asyncio
from datetime import datetime
from langchain_core.tools import Tool

logger = get_logger(__name__)

def _now_iso():
    return datetime.now().isoformat()

class MCPController:
    """
    MCP 서버 호출을 제어하는 컨트롤러
    - 라운드 제한 강제
    - admin.make_prevention 호출 후 MCP 차단
    """
    
    def __init__(self, max_rounds: int = 5):
        self.max_rounds = max_rounds
        self.current_round = 0
        self.is_active = True
        self.make_prevention_called = False
        self._sinks = set()             # asyncio.Queue 집합
        self._sinks_lock = asyncio.Lock()

    # ▼ 추가: SSE에서 읽을 Queue 생성
    def make_sink_queue(self) -> "asyncio.Queue[dict]":
        return asyncio.Queue()

    # ▼ 추가: 등록/해제
    async def register_sink(self, q: "asyncio.Queue[dict]"):
        async with self._sinks_lock:
            self._sinks.add(q)

    async def unregister_sink(self, q: "asyncio.Queue[dict]"):
        async with self._sinks_lock:
            self._sinks.discard(q)

    # ▼ 추가: 턴 이벤트 브로드캐스트
    async def emit_turn(self, *, case_id: str, round_no: int, turn_index: int,
                        role: str, content: str, created_kst: str):
        event = {
            "type": "turn",
            "case_id": case_id,
            "round": round_no,
            "turn_index": turn_index,
            "role": role,
            "content": content,
            "created_kst": created_kst,
        }
        async with self._sinks_lock:
            for q in list(self._sinks):
                try:
                    q.put_nowait(event)
                except Exception:
                    # 꽉 찬 큐 등은 조용히 스킵 (SSE는 최신만 받으면 됨)
                    pass
        
    def can_run_simulation(self) -> tuple[bool, str]:
        """
        시뮬레이션 실행 가능 여부 확인
        
        Returns:
            (가능여부, 거부사유)
        """
        if not self.is_active:
            return False, "MCP 컨트롤러가 비활성화되었습니다"
        
        if self.make_prevention_called:
            return False, "admin.make_prevention 호출 후 종료되었습니다"
        
        if self.current_round >= self.max_rounds:
            return False, f"최대 라운드 수({self.max_rounds}) 도달"
        
        return True, ""
    
    def start_round(self) -> int:
        """
        새 라운드 시작
        
        Returns:
            현재 라운드 번호
            
        Raises:
            RuntimeError: 라운드 시작 불가능한 경우
        """
        can_run, reason = self.can_run_simulation()
        if not can_run:
            logger.error(f"[MCPController] 라운드 시작 불가: {reason}")
            raise RuntimeError(reason)
        
        self.current_round += 1
        logger.info(f"[MCPController] 라운드 {self.current_round}/{self.max_rounds} 시작")
        return self.current_round
    
    def mark_prevention_called(self):
        """admin.make_prevention 호출됨을 기록"""
        logger.info("[MCPController] admin.make_prevention 호출됨 - MCP 비활성화")
        self.make_prevention_called = True
        self.is_active = False
    
    def shutdown(self):
        """컨트롤러 종료"""
        logger.info("[MCPController] 컨트롤러 종료")
        self.is_active = False


def wrap_mcp_tool(original_tool, controller: MCPController) -> Tool:
    """
    mcp.simulator_run이면 on_turn 콜백을 주입해 턴마다 emit_turn.
    그 외 MCP 도구는 기존의 실행 제어만 수행.
    """
    is_simulator = (getattr(original_tool, "name", "") == "mcp.simulator_run")

    async def _emit_turn_safe(ev: dict, case_id_override: str | None, round_no_fallback: int | None):
        try:
            await controller.emit_turn(
                case_id   = ev.get("case_id") or case_id_override or "",
                round_no  = ev.get("round") or ev.get("round_no") or round_no_fallback or 1,
                turn_index= ev.get("turn") or ev.get("turn_index") or 0,
                role      = (ev.get("role") or "offender").lower(),
                content   = ev.get("content") or ev.get("text") or "",
                created_kst = ev.get("created_kst") or _now_iso(),
            )
        except Exception:
            logger.exception("[MCPController] emit_turn 실패")

    def controlled_run(*args, **kwargs):
        can_run, reason = controller.can_run_simulation()
        if not can_run:
            logger.warning(f"[MCPController] {original_tool.name} 호출 차단: {reason}")
            return {"status": "blocked", "reason": reason, "message": "시뮬레이션이 종료되었습니다"}

        # ── 스트리밍 주입: simulator_run만 on_turn 콜백 삽입 ──
        if is_simulator:
            # LangChain Tool.run 은 보통 첫 인자가 dict(json str 등)임
            # 우리 시스템 프롬프트가 {"data": {...}}를 강제하므로 그대로 다룸
            payload = None
            if args and isinstance(args[0], dict):
                payload = args[0]
            elif "tool_input" in kwargs and isinstance(kwargs["tool_input"], dict):
                payload = kwargs["tool_input"]

            if isinstance(payload, dict):
                data = payload.get("data") if "data" in payload else payload
                # 라운드/케이스 추정용
                round_no = int((data or {}).get("round_no") or 1)
                case_id_override = (data or {}).get("case_id_override")

                # 동기 엔진도 안전하게 받을 수 있도록 "동기 의존 X" 콜백 제공
                def on_turn_sync(ev: dict):
                    # 비동기 태스크로 브로드캐스트
                    asyncio.get_event_loop().create_task(
                        _emit_turn_safe(ev or {}, case_id_override, round_no)
                    )

                # 엔진이 기대하는 키 이름에 맞춰 전달 (on_turn / callback / stream_cb 등)
                # 여기선 on_turn 사용. 필요하면 엔진 시그니처에 맞게 이름만 바꾸면 됨.
                try:
                    data["on_turn"] = on_turn_sync
                    # 혹시 다른 이름도 받는다면 중복 세팅해도 무해
                    data["callback"] = data.get("callback") or on_turn_sync
                    data["stream_cb"] = data.get("stream_cb") or on_turn_sync
                except Exception:
                    logger.warning("[MCPController] on_turn 콜백 세팅 실패")

            logger.info(f"[MCPController] {original_tool.name} 실행 허용(스트리밍 모드)")
            return original_tool.run(*args, **kwargs)

        # ── simulator_run 이외 도구는 기존 제어만 ──
        logger.info(f"[MCPController] {original_tool.name} 실행 허용")
        return original_tool.run(*args, **kwargs)

    return Tool(name=original_tool.name, description=original_tool.description, func=controlled_run)


def wrap_admin_make_prevention(original_tool, controller: MCPController):
    """
    admin.make_prevention 도구를 래핑하여 호출 후 MCP 차단
    
    Args:
        original_tool: 원본 admin.make_prevention 도구
        controller: MCP 컨트롤러
    
    Returns:
        래핑된 도구
    """
    from langchain_core.tools import Tool
    
    def controlled_make_prevention(*args, **kwargs):
        logger.info("[MCPController] admin.make_prevention 실행")
        
        # 원본 도구 실행
        result = original_tool.run(*args, **kwargs)
        
        # 실행 후 MCP 차단
        controller.mark_prevention_called()
        
        return result
    
    return Tool(
        name=original_tool.name,
        description=original_tool.description,
        func=controlled_make_prevention
    )