# app/services/agent/mcp_controller.py

from __future__ import annotations
from typing import Dict, Any, Set, Optional
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MCPController:
    """
    MCP 도구 실행을 제어하고 턴별 이벤트를 스트리밍하는 컨트롤러
    
    Features:
    - 라운드 제한 관리
    - 실시간 턴 이벤트 emit
    - 여러 구독자(Queue)에게 브로드캐스트
    """
    max_rounds: int = 5
    current_round: int = 0
    _sinks: Set[asyncio.Queue] = field(default_factory=set)
    _round_started: bool = False
    
    def start_round(self):
        """새 라운드 시작"""
        if self.current_round >= self.max_rounds:
            raise RuntimeError(f"최대 라운드({self.max_rounds}) 도달")
        self.current_round += 1
        self._round_started = True
        logger.info(f"[MCPController] 라운드 {self.current_round} 시작")
    
    def can_run(self) -> bool:
        """실행 가능 여부"""
        return self.current_round < self.max_rounds
    
    def make_sink_queue(self) -> asyncio.Queue:
        """새 이벤트 구독 큐 생성"""
        return asyncio.Queue()
    
    async def register_sink(self, q: asyncio.Queue):
        """이벤트 구독 등록"""
        self._sinks.add(q)
        logger.info(f"[MCPController] 구독자 등록 (총 {len(self._sinks)}개)")
    
    async def unregister_sink(self, q: asyncio.Queue):
        """이벤트 구독 해제"""
        self._sinks.discard(q)
        logger.info(f"[MCPController] 구독자 해제 (남은 {len(self._sinks)}개)")
    
    async def emit_turn(
        self,
        case_id: str,
        round_no: int,
        turn_index: int,
        role: str,
        content: str,
        created_kst: str,
    ):
        """
        턴 이벤트를 모든 구독자에게 브로드캐스트
        
        Args:
            case_id: 케이스 ID
            round_no: 라운드 번호
            turn_index: 턴 인덱스
            role: 역할 (offender/victim)
            content: 대화 내용
            created_kst: 생성 시각 (ISO 형식)
        """
        event = {
            "case_id": case_id,
            "round": round_no,
            "turn_index": turn_index,
            "role": role,
            "content": content,
            "created_kst": created_kst,
        }
        
        # 모든 구독자에게 전송
        dead_sinks = set()
        for q in self._sinks:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"[MCPController] 큐 가득 참음, 이벤트 드롭")
            except Exception as e:
                logger.error(f"[MCPController] emit 실패: {e}")
                dead_sinks.add(q)
        
        # 죽은 구독자 제거
        self._sinks -= dead_sinks
        
        if self._sinks:
            logger.debug(
                f"[MCPController] EMIT: round={round_no}, turn={turn_index}, "
                f"role={role}, subscribers={len(self._sinks)}"
            )
    
    def shutdown(self):
        """컨트롤러 종료"""
        self._sinks.clear()
        logger.info("[MCPController] 종료됨")


def wrap_mcp_tool(tool, controller: MCPController):
    """
    MCP 도구를 래핑하여 라운드 제한 체크
    
    Args:
        tool: 원본 LangChain Tool
        controller: MCP 컨트롤러
    
    Returns:
        래핑된 Tool
    """
    from langchain_core.tools import Tool
    
    original_func = tool.func
    
    def wrapped_func(*args, **kwargs):
        if not controller.can_run():
            logger.warning(f"[MCPController] 최대 라운드 도달, {tool.name} 차단")
            return {
                "ok": False,
                "error": f"최대 라운드({controller.max_rounds}) 도달",
                "blocked": True
            }
        return original_func(*args, **kwargs)
    
    return Tool(
        name=tool.name,
        description=tool.description,
        func=wrapped_func,
        args_schema=tool.args_schema if hasattr(tool, 'args_schema') else None,
    )


def wrap_admin_make_prevention(tool, controller: MCPController):
    """
    admin.make_prevention을 래핑하여 실행 후 즉시 종료
    
    Args:
        tool: admin.make_prevention Tool
        controller: MCP 컨트롤러
    
    Returns:
        래핑된 Tool
    """
    from langchain_core.tools import Tool
    
    original_func = tool.func
    
    def wrapped_func(*args, **kwargs):
        result = original_func(*args, **kwargs)
        # 실행 완료 후 컨트롤러 종료
        controller.shutdown()
        logger.info("[MCPController] make_prevention 완료, 컨트롤러 종료")
        return result
    
    return Tool(
        name=tool.name,
        description=tool.description,
        func=wrapped_func,
        args_schema=tool.args_schema if hasattr(tool, 'args_schema') else None,
    )