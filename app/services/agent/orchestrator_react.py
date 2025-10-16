# app/services/agent/orchestrator_react.py (수정된 버전)

from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
import json
import re
from datetime import datetime
import contextlib
import asyncio
import uuid  # ✅ 추가
import sys
import io
import threading
from queue import Queue as ThreadQueue
import logging

# adf
# sdf
# sdf
# sdf
# dsf

from sqlalchemy.orm import Session
from fastapi import HTTPException

from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.callbacks.base import BaseCallbackHandler

from app.services.llm_providers import agent_chat
from app.services.agent.tools_sim import make_sim_tools
from app.services.agent.tools_admin import make_admin_tools
from app.services.agent.tools_mcp import make_mcp_tools
from app.services.agent.tools_tavily import make_tavily_tools
from app.services.agent.graph import should_continue_rounds
from app.services.agent.guideline_repo_db import GuidelineRepoDB
from app.services.agent.guidance_generator import make_guidance_generation_tool  # 새로 추가
from app.core.logging import get_logger
from app.services.agent.tools_mcp import parse_conversation_logs

# ✅ 올바른 방식 - 클래스와 함수들을 import
from app.services.agent.mcp_controller import (
    MCPController,           # 클래스
    wrap_mcp_tool,          # 함수
    wrap_admin_make_prevention  # 함수
)

# 새 추가
from app.schemas.simulation_request import SimulationStartRequest
from app.services.prompt_integrator_db import build_prompt_package_from_payload
from app.services.agent.stopping_callback import RoundLimitStoppingCallback

logger = get_logger(__name__)

_active_chains = {}  # key -> asyncio.Lock

def _make_chain_key(offender_id: int, victim_id: int):
    return f"{offender_id}:{victim_id}"

# ─────────────────────────────────────────────────────────
# 헬퍼들
# ─────────────────────────────────────────────────────────
def _extract_case_id(from_obj: Any) -> Optional[str]:
    """
    MCP 출력에서 case_id 추출 (검증용)
    
    Note: 이 함수는 더 이상 필수가 아니며, 디버깅/검증 목적으로만 사용
    """
    s = str(from_obj)
    m = re.search(
        r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
        s,
        flags=re.I
    )
    result = m.group(1) if m else None
    
    if not result:
        logger.debug("[Extract] case_id 추출 실패 (정상 - 사전 생성 방식 사용 중)")
    
    return result

def debug_mcp_output(output: Any):
    """MCP 출력 구조 분석"""
    logger.info("=" * 80)
    logger.info("[DEBUG] MCP 출력 분석")
    logger.info(f"타입: {type(output)}")
    
    if isinstance(output, dict):
        logger.info(f"키: {list(output.keys())}")
        for key in ['output', 'result', 'logs', 'conversation_logs']:
            if key in output:
                value = output[key]
                logger.info(f"  {key}: {type(value)} - {str(value)[:200]}...")
    
    output_str = str(output)
    logger.info(f"문자열 길이: {len(output_str)}")
    logger.info(f"샘플:\n{output_str[:1000]}")
    
    # 패턴 검색
    if '[Conversation]' in output_str:
        count = output_str.count('[Conversation]')
        logger.info(f"✅ [Conversation] 발견: {count}개")
    else:
        logger.warning("⚠️ [Conversation] 패턴 없음")
    
    logger.info("=" * 80)


def _extract_phishing(agent_result: Any) -> bool:
    s = str(agent_result).lower()
    return '"phishing": true' in s or "phishing': true" in s or "phishing = true" in s


def _extract_reason(agent_result: Any) -> str:
    m = re.search(r"'reason':\s*'([^']*)'|\"reason\":\s*\"([^\"]*)\"",
                  str(agent_result))
    return (m.group(1) or m.group(2)) if m else ""


def _extract_guidance_text(agent_result: Any) -> str:
    try:
        s = str(agent_result)
        m = re.search(r"\{.*\"type\".*\"text\".*\}", s, re.S)
        if m:
            obj = json.loads(m.group(0))
            return obj.get("text", "").strip()
    except Exception:
        pass
    m2 = re.search(r"text['\"]\s*:\s*['\"]([^'\"]+)['\"]", str(agent_result))
    return m2.group(1).strip() if m2 else ""


def _extract_guidance_info(agent_result: Any) -> Dict[str, Any]:
    """동적 생성된 지침 정보를 추출합니다."""
    try:
        s = str(agent_result)
        # JSON 객체 찾기
        import re
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, s)

        for match in matches:
            try:
                data = json.loads(match)
                if 'text' in data and any(
                        key in data for key in
                    ['reasoning', 'categories', 'expected_effect']):
                    return {
                        "text":
                        data.get("text", ""),
                        "categories":
                        data.get("categories", []),
                        "reasoning":
                        data.get("reasoning", ""),
                        "expected_effect":
                        data.get("expected_effect", ""),
                        "generation_method":
                        data.get("generation_method", "dynamic_analysis")
                    }
            except json.JSONDecodeError:
                continue

        # 폴백: text 필드만 추출
        text_match = re.search(r'"text":\s*"([^"]*)"', s)
        return {
            "text": text_match.group(1) if text_match else "",
            "categories": [],
            "reasoning": "추출 실패",
            "expected_effect": "미확인",
            "generation_method": "fallback_extraction"
        }
    except Exception:
        return {
            "text": "",
            "categories": [],
            "reasoning": "파싱 오류",
            "expected_effect": "미확인",
            "generation_method": "error_fallback"
        }


def _truncate(obj: Any, max_len: int = 800) -> Any:
    """긴 문자열을 로그용으로 안전하게 자르기"""
    try:
        if isinstance(obj, str):
            return (obj[:max_len] + "…") if len(obj) > max_len else obj
        if isinstance(obj, list):
            return [_truncate(x, max_len) for x in obj]
        if isinstance(obj, dict):
            return {k: _truncate(v, max_len) for k, v in obj.items()}
    except Exception:
        pass
    return obj


def _log_prompt_snapshot(round_no: int, sim_payload: Dict[str, Any]) -> None:
    """실제 시뮬레이터에 들어가는 입력 스냅샷을 로그로 남김"""
    snapshot = {
        "round_no": round_no,
        "offender_id": sim_payload.get("offender_id"),
        "victim_id": sim_payload.get("victim_id"),
        "case_id_override": sim_payload.get("case_id_override"),
        "round_no_field": sim_payload.get("round_no"),
        "guidance": sim_payload.get("guidance"),
        "scenario": sim_payload.get("scenario"),
        "victim_profile": sim_payload.get("victim_profile"),
        "templates": {
            "attacker": sim_payload.get("templates", {}).get("attacker", ""),
            "victim": sim_payload.get("templates", {}).get("victim", ""),
        },
        "max_turns": sim_payload.get("max_turns"),
    }
    logger.info("[PromptSnapshot] %s",
                json.dumps(_truncate(snapshot), ensure_ascii=False))


# ─────────────────────────────────────────────────────────
# LangChain 콜백: Thought/Action/Observation 캡처
# ─────────────────────────────────────────────────────────
@dataclass
class SimulationSession:
    """
    시뮬레이션 세션 관리 클래스
    
    Features:
    - case_id 사전 생성
    - 라운드 추적
    - 상태 관리
    """
    case_id: str
    offender_id: int
    victim_id: int
    round_no: int = 0
    status: str = "initializing"
    started_at: datetime = None
    
    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now()
    
    @classmethod
    def create(cls, offender_id: int, victim_id: int, case_id: Optional[str] = None) -> "SimulationSession":
        """새 세션 생성"""
        return cls(case_id=(case_id or str(uuid.uuid4())), offender_id=offender_id, victim_id=victim_id)
    
    def next_round(self) -> int:
        """라운드 진행"""
        self.round_no += 1
        if self.status == "initializing":
            self.status = "running"
        return self.round_no
    
    def complete(self):
        """세션 완료"""
        self.status = "completed"
    
    def fail(self, error: str = None):
        """세션 실패"""
        self.status = f"failed: {error}" if error else "failed"

# # ===== 1. 터미널 로그 캡처 클래스 추가 =====

# class TerminalLogCapture(io.TextIOBase):
#     """
#     터미널 출력을 실시간으로 캡처하는 스트림
#     - 토큰(글자) 단위로 즉시 큐에 전송
#     - asyncio.Queue와 호환되도록 설계
#     """
#     def __init__(self, original_stream, log_queue: asyncio.Queue):
#         self.original_stream = original_stream
#         self.log_queue = log_queue
#         self.buffer = []
        
#     def write(self, text: str):
#         """write 호출 시 즉시 큐에 전송"""
#         # 원본 스트림에도 출력 (터미널에서도 보이게)
#         self.original_stream.write(text)
#         self.original_stream.flush()
        
#         # 큐에 비동기로 전송 (토큰 단위)
#         if text:
#             try:
#                 # asyncio.Queue에 직접 넣기 (sync → async)
#                 # run_in_executor 없이 처리하려면 threadsafe 메서드 사용
#                 loop = asyncio.get_event_loop()
#                 loop.call_soon_threadsafe(
#                     self.log_queue.put_nowait,
#                     {
#                         "type": "agent_log",
#                         "event": "terminal_output",
#                         "data": {"text": text}
#                     }
#                 )
#             except Exception as e:
#                 # 큐가 닫혔거나 오류 발생 시 무시
#                 pass
    
#     def flush(self):
#         self.original_stream.flush()

# ===== 기존 클래스 교체 =====
class TerminalLogCapture(io.TextIOBase):
    """
    터미널 출력을 캡처하는 스트림
    - 개행(\n) 기준으로 줄 단위 전송 (터미널과 동일)
    """
    def __init__(self, original_stream, log_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self.original_stream = original_stream
        self.log_queue = log_queue
        self._buf = ""
        self.loop = loop

    def write(self, text: str):
        # 원본에도 그대로 출력
        self.original_stream.write(text)
        self.original_stream.flush()

        if text:
            try:
                # ❌ asyncio.get_event_loop() 금지 (스레드에서 실패)
                # ✅ 메인 루프에 스레드-세이프하게 post
                self.loop.call_soon_threadsafe(
                    self.log_queue.put_nowait,
                    {
                        "type": "agent_log",
                        "event": "terminal_output",
                        "data": {"text": text}
                    }
                )
            except Exception as e:
                # 디버깅 위해 최소한 로그 남기기
                logging.getLogger(__name__).error(f"TerminalLogCapture.write error: {e}")

        if not text:
            return
        self._buf += text

        # 개행 단위로만 쪼개서 전송
        while True:
            if "\n" not in self._buf:
                break
            line, self._buf = self._buf.split("\n", 1)
            self._emit_line(line + "\n")  # 개행 포함해서 보내기 (터미널과 동일한 시각적 결과)

    def flush(self):
        self.original_stream.flush()
        # 남은 조각(마지막 줄)이 있으면 그대로 방출
        if self._buf:
            self._emit_line(self._buf)
            self._buf = ""

    def _emit_line(self, line: str):
        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(
                self.log_queue.put_nowait,
                {
                    "type": "agent_log",
                    "event": "terminal_output",
                    "data": {"text": line},   # 가공/이모지 금지
                }
            )
        except Exception:
            pass
# ===== 2. 컨텍스트 매니저로 stdout 리다이렉션 =====

@contextlib.asynccontextmanager
async def capture_terminal_logs(log_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    """
    터미널 출력을 캡처하는 컨텍스트 매니저
    
    Usage:
        async with capture_terminal_logs(queue):
            # 이 블록 안의 모든 print/logger 출력이 queue로 전송됨
            print("test")
    """
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    # 커스텀 스트림으로 교체
    sys.stdout = TerminalLogCapture(original_stdout, log_queue, loop)
    sys.stderr = TerminalLogCapture(original_stderr, log_queue, loop)
    
    try:
        yield
    finally:
        # 원상복구
        sys.stdout = original_stdout
        sys.stderr = original_stderr

@dataclass
class ThoughtCapture(BaseCallbackHandler):
    last_tool: Optional[str] = None
    last_tool_input: Optional[Any] = None
    events: list = field(default_factory=list)
    conversation_logs: list = field(default_factory=list)
    sse_queue: Optional[asyncio.Queue] = None  # ✅ SSE 큐
    case_id: Optional[str] = None  # ✅ case_id
    loop: Optional[asyncio.AbstractEventLoop] = None  # ✅

    def _send_sse(self, text: str):
        """SSE로 로그 전송하는 헬퍼 메서드"""
        if self.sse_queue and self.loop:
            try:
                self.loop.call_soon_threadsafe(        # ✅
                    self.sse_queue.put_nowait,
                    {
                        "type": "agent_log",
                        "data": {"text": text},
                        "case_id": self.case_id,
                        "ts": datetime.now().isoformat()
                    }
                )
            except Exception as e:
                logger.error(f"SSE 전송 실패: {e}")

    # ✅ LLM 시작 (Thought 생성 시작)
    def on_llm_start(self, serialized, prompts, **kwargs):
        """LLM이 생각을 시작할 때"""
        msg = "💭 [LLM Start] AI가 생각을 시작합니다..."
        logger.info(msg)
        self._send_sse(msg)

    # ✅ LLM 종료 (Thought 완료)
    def on_llm_end(self, response, **kwargs):
        """LLM이 생각을 마쳤을 때"""
        try:
            output = str(response.generations[0][0].text)
            # Thought 추출 시도
            import re
            thought_match = re.search(r'Thought:\s*(.+?)(?=\n(?:Action|Final Answer|$))', output, re.DOTALL)
            if thought_match:
                thought_text = thought_match.group(1).strip()
                msg = f"💭 Thought: {thought_text[:500]}"
                logger.info(msg)
                self._send_sse(msg)
            else:
                msg = f"💭 LLM Output: {output[:500]}"
                logger.info(msg)
                self._send_sse(msg)
        except Exception as e:
            logger.error(f"LLM end 처리 실패: {e}")

    # ✅ 에러 발생
    def on_llm_error(self, error, **kwargs):
        """LLM 에러 발생 시"""
        msg = f"❌ [LLM Error] {str(error)[:300]}"
        logger.error(msg)
        self._send_sse(msg)

    # ✅ 도구 실행 (Action)
    def on_agent_action(self, action, **kwargs):
        rec = {
            "type": "action",
            "tool": getattr(action, "tool", "?"),
            "tool_input": getattr(action, "tool_input", None),
        }
        self.last_tool = rec["tool"]
        self.last_tool_input = rec["tool_input"]
        self.events.append(rec)
        
        # 터미널 로그
        log_msg = f"[AgentThought] Tool={rec['tool']} | Input={_truncate(rec['tool_input'])}"
        logger.info(log_msg)
        
        # SSE 전송
        self._send_sse(f"⚡ Action: {rec['tool']}")
        
        # Action Input도 전송 (200자로 제한)
        input_preview = _truncate(str(rec['tool_input']), 200)
        self._send_sse(f"📥 Action Input: {input_preview}")

    # ✅ 도구 시작
    def on_tool_start(self, serialized, input_str, **kwargs):
        """도구 실행 시작"""
        tool_name = serialized.get("name", "unknown")
        msg = f"🔧 [Tool Start] {tool_name}"
        logger.info(msg)
        self._send_sse(msg)

    # ✅ 도구 종료 (Observation)
    def on_tool_end(self, output, **kwargs):
        """도구 실행 완료"""
        output_str = str(output)
        msg = f"🔍 [Tool End] Output length: {len(output_str)} chars"
        logger.info(msg)
        self._send_sse(msg)
        
        # 결과 일부 전송
        preview = _truncate(output_str, 300)
        self._send_sse(f"👁️ Tool Output: {preview}")

    # ✅ 도구 에러
    def on_tool_error(self, error, **kwargs):
        """도구 실행 에러"""
        msg = f"❌ [Tool Error] {str(error)[:300]}"
        logger.error(msg)
        self._send_sse(msg)

    # ✅ 에이전트 종료 (Final Answer 또는 Observation)
    def on_agent_finish(self, finish, **kwargs):
        self.events.append({"type": "finish", "log": finish.log})
        
        log_text = str(finish.log)

        # 디버그 로그
        logger.info("="*80)
        logger.info("[DEBUG] finish.log 전체 내용:")
        logger.info(log_text[:2000])
        logger.info("="*80)
        
        # SSE로 finish.log 전송
        self._send_sse("=" * 50)
        self._send_sse("📋 [Agent Finish] 에이전트 실행 완료")
        self._send_sse("=" * 50)
        
        # Conversation 로그 파싱
        import re
        pattern = r'\[Conversation\]\[case:[^\]]+\]\[run:(\d+)\]\[turn:(\d+)\]\[(offender|victim)\]\s+(.+?)(?=\n\[|$)'
        matches = re.findall(pattern, log_text, re.DOTALL)
        
        logger.info(f"[ThoughtCapture] finish.log 길이: {len(log_text)}")
        logger.info(f"[ThoughtCapture] 매칭된 로그: {len(matches)}개")
        
        self._send_sse(f"💬 Conversation 로그: {len(matches)}개 발견")

        for match in matches:
            run, turn, role, content = match
            self.conversation_logs.append({
                "turn_index": int(turn),
                "role": role.strip(),
                "content": content.strip(),
                "created_kst": datetime.now().isoformat(),
                "run": int(run),
            })
            logger.info(f"[ThoughtCapture] 로그 추가: run={run}, turn={turn}, role={role}")
        
        if matches:
            logger.info(f"[ThoughtCapture] {len(matches)}개 대화 로그 캡처됨")

        # finish.log 전체를 SSE로 전송 (긴 내용이므로 나눠서)
        # 500자씩 나눠서 전송
        self._send_sse(log_text)
        
        logger.info("[AgentFinish] %s", _truncate(finish.log, 1200))

    # ✅ 체인 시작
    def on_chain_start(self, serialized, inputs, **kwargs):
        """체인 실행 시작"""
        chain_name = serialized.get("name", "unknown")
        msg = f"🔗 [Chain Start] {chain_name}"
        logger.info(msg)
        self._send_sse(msg)

    # ✅ 체인 종료
    def on_chain_end(self, outputs, **kwargs):
        """체인 실행 완료"""
        msg = f"✅ [Chain End] 완료"
        logger.info(msg)
        self._send_sse(msg)

    # ✅ 체인 에러
    def on_chain_error(self, error, **kwargs):
        """체인 실행 에러"""
        msg = f"❌ [Chain Error] {str(error)[:300]}"
        logger.error(msg)
        self._send_sse(msg)

    # ✅ 텍스트 출력 (스트리밍)
    def on_text(self, text: str, **kwargs):
        """임의의 텍스트 출력"""
        if text.strip():
            msg = f"📝 [Text] {text[:300]}"
            logger.info(msg)
            self._send_sse(msg)

@dataclass
class RealtimeLogCapture(BaseCallbackHandler):
    """실시간으로 대화 로그를 캡처하는 콜백"""
    current_round: int = 1
    all_logs: List[Dict] = field(default_factory=list)
    round_logs: Dict[int, List[Dict]] = field(default_factory=dict)
    
    def on_tool_end(self, output: str, **kwargs):
        """도구 실행 직후 즉시 호출"""
        try:
            tool_name = kwargs.get('name', '')
            
            if tool_name != 'mcp.simulator_run':
                return
            
            logger.info(f"[Callback] mcp.simulator_run 완료, 로그 파싱 시작 (round={self.current_round})")
            
            # ✅ output 타입 확인 및 변환
            if isinstance(output, dict):
                # dict인 경우 문자열로 변환
                output_str = json.dumps(output, ensure_ascii=False)
                logger.debug(f"[Callback] output을 dict에서 str로 변환: {len(output_str)}자")
            elif isinstance(output, str):
                output_str = output
            else:
                # 기타 타입은 str() 변환
                output_str = str(output)
                logger.debug(f"[Callback] output을 {type(output)}에서 str로 변환")
            
            # 로그 파싱
            parsed = parse_conversation_logs(output_str, target_round=self.current_round)
            
            if parsed:
                existing_turns = {
                    log['turn_index'] 
                    for log in self.all_logs 
                    if log['run'] == self.current_round
                }
                new_logs = [
                    log for log in parsed 
                    if log['turn_index'] not in existing_turns
                ]
                
                self.all_logs.extend(new_logs)
                
                if self.current_round not in self.round_logs:
                    self.round_logs[self.current_round] = []
                self.round_logs[self.current_round].extend(new_logs)
                
                logger.info(
                    f"[Callback] ✅ {len(new_logs)}개 신규 로그 추가 "
                    f"(round={self.current_round}, 총 {len(self.all_logs)}개)"
                )
            else:
                logger.warning(f"[Callback] ⚠️ 로그 파싱 실패 (round={self.current_round})")
                logger.debug(f"[Callback] output 샘플:\n{output_str[:500]}")
        
        except Exception as e:
            logger.error(f"[Callback] on_tool_end 에러: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def get_round_logs(self, round_no: int) -> List[Dict]:
        """특정 라운드 로그 조회"""
        return self.round_logs.get(round_no, [])
    
    def next_round(self):
        """라운드 진행"""
        self.current_round += 1
        logger.info(f"[Callback] 라운드 진행: {self.current_round}")

# ─────────────────────────────────────────────────────────
# ReAct 시스템 프롬프트 (강한 레일가드 / JSON 예시 이스케이프)
# ─────────────────────────────────────────────────────────
REACT_SYS = (
    "당신은 보이스피싱 시뮬레이션 오케스트레이터입니다.\n"
    "오직 제공된 도구만 사용하여 작업하세요. (직접 결과를 쓰거나 요약으로 때우지 말 것)\n"
    "\n"
    "▼ 실행 제한 (반드시 준수)\n"
    "  • 최대 라운드 수: 5라운드까지만 진행\n"
    "  • 각 라운드는 정확히 1회만 실행 (같은 라운드를 반복하지 않음)\n"
    "  • 5라운드 완료 후에는 **절대 추가 도구를 호출하지 않고** Final Answer만 출력\n"
    "  • admin.make_prevention 호출 후 반드시 Final Answer 출력하고 종료\n"
    "  • Final Answer 출력 후에는 **어떤 도구도 호출하지 않음**\n"
    "\n"
    "▼ 전체 사이클 규칙\n"
    "  [라운드1]\n"
    "    1) sim.fetch_entities 로 시나리오/피해자 정보를 확보한다.\n"
    "    2) sim.compose_prompts 를 호출한다. (★ guidance 금지)\n"
    "    3) mcp.simulator_run 을 실행한다. (★ guidance 금지)\n"
    "    4) admin.judge 로 판정하고 phishing/이유를 기록한다.\n"
    "       └ 이때 (case_id, run_no)만 보내지 말고, 반드시 방금 mcp.simulator_run Observation에서 받은\n"
    "          {{\"turns\": [...]}} 또는 {{\"log\": {{...}}}} 를 함께 전달한다.\n"
    "    5) admin.save_prevention 으로 라운드 요약과 권고 스텝을 저장한다.\n"
    "       ─ 저장 스키마는 다음 한 가지로 고정한다 (다른 키 금지):\n"
    "        case_id, round_no, summary ,{{\"steps\": {{\"prevention_steps\": {{[...]}}}}\n"
    "  [라운드2~N]\n"
    "    6) admin.generate_guidance 로 현재 상황을 분석하여 맞춤형 지침을 생성한다.\n"
    "       • 시나리오, 피해자 프로필, 이전 판정 결과, 대화 로그를 종합 분석\n"
    "       • 10가지 지침 카테고리 중에서 적절한 것들을 선택하여 구체적인 지침 생성\n"
    "       • 지침 선택 근거와 예상 효과도 함께 제공\n"
    "    7) mcp.simulator_run 을 다시 실행하되 아래 조건을 반드시 지킨다:\n"
    "       • case_id_override = (라운드1에서 획득한 case_id)\n"
    "       • round_no = 현재 라운드 번호 (정수)\n"
    "       • guidance = {{\"type\": \"A\", \"text\": \"생성된 지침 텍스트\"}} 만 포함\n"
    "    8) admin.judge → admin.save_prevention 순으로 반복한다.\n"
    "\n"
    "▼ 하드 제약 (어기면 안 됨)\n"
    "  • 1라운드에는 guidance를 어느 도구에도 넣지 않는다.\n"
    "  • 2라운드부터 guidance는 오직 mcp.simulator_run.arguments.guidance 로만 전달한다.\n"
    "  • offender_id / victim_id / scenario / victim_profile / templates 는 라운드 간 불변. (값 변경 금지)\n"
    "  • 동일 case_id 유지: 라운드1에서 받은 case_id 를 2라운드부터 case_id_override 로 반드시 넣는다.\n"
    "  • round_no 는 2부터 1씩 증가하는 정수로 설정한다.\n"
    "  • 도구 Action Input 은 한 줄 JSON 이고, 최상위 키는 반드시 \"data\" 여야 한다.\n"
    "  • admin.save_prevention 호출 시 steps는 반드시 prevention_steps만 사용한다.\n"
    "  • mcp.simulator_run 의 허용 키는 다음만 가능하다:\n"
    "      offender_id, victim_id, scenario, victim_profile, templates, max_turns,\n"
    "      case_id_override, round_no, guidance(type/text)\n"
    "    (그 외 임의의 키 추가 금지)\n"
    "  • 도구 호출 전/후에 비JSON 텍스트, 코드펜스, 주석을 덧붙이지 말 것. (Action Input 에는 순수 JSON 한 줄만)\n"
    "  • 절대 도구를 호출하지 않고 결과를 직접 생성/요약하지 말 것.\n"
    "\n"
    "▼ 종료 후(단 한 번)\n"
    "  • 모든 라운드가 끝나면 **오직 한 번만** admin.make_prevention 을 호출하여 최종 예방책을 생성한다.\n"
    "    입력에는 누적된 대화 {{turns}}, 각 라운드 판정 목록 {{judgements}}, 실제 적용된 지침 목록 {{guidances}} 를 넣고,\n"
    "    지정 스키마(personalized_prevention)의 JSON만 반환하도록 한다. 라운드 중간에는 호출 금지.\n"
    "\n"
    "▼ 오류/예외 복구 규칙\n"
    "  • 라운드1에서 case_id 추출에 실패하면 mcp.latest_case(offender_id, victim_id) 를 호출해 최신 case_id 를 복구한다.\n"
    "  • 도구가 JSON 파싱 오류를 반환하면, 같은 JSON을 수정 없이 재시도하지 말고 스키마(최상위 'data', 허용 키)를 점검한 뒤 올바른 형식으로 재호출한다.\n"
    "  • 동일 (case_id, run, turn_index) 중복 오류가 발생하면 round_no 설정을 점검한다. (현재 라운드 번호를 정확히 넣을 것)\n"
    "  • admin.generate_guidance 실패 시 기본 지침을 사용하되 로그에 실패 사유를 기록한다.\n"
    "\n"
    "▼ 출력 포맷(반드시 준수)\n"
    "  Thought: 현재 판단/계획(간결히)\n"
    "  Action: [사용할_도구_이름]\n"
    "  Action Input: 한 줄 JSON (예: {{\"data\": {{...}}}})\n"
    "  Observation: 도구 결과\n"
    "  ... 필요시 반복 ...\n"
    "  Final Answer: 최종 요약(최종 case_id, 총 라운드 수, 각 라운드 판정 요약 포함)\n")


def build_agent_and_tools(db: Session,
                          use_tavily: bool,
                          mcp_controller: Optional[MCPController] = None  # ✅ 추가
                          ) -> Tuple[AgentExecutor, Any, MCPController]:
    llm = agent_chat(temperature=0.2)

    tools: List = []
    # ✅ MCP 컨트롤러 생성 (없으면)
    if mcp_controller is None:
        mcp_controller = MCPController(max_rounds=5)

    # 각 도구를 안전하게 추가
    try:
        sim_tools = make_sim_tools(db)
        if sim_tools:
            tools.extend([t for t in sim_tools if t is not None])
            logger.info(
                f"[Agent] sim_tools 추가됨: {len([t for t in sim_tools if t is not None])}개"
            )
    except Exception as e:
        logger.error(f"[Agent] sim_tools 로딩 실패: {e}")

    try:
        mcp_tools, mcp_manager = make_mcp_tools(mcp_controller=mcp_controller)
        if mcp_tools:
            wrapped_mcp_tools = []
            for t in mcp_tools:
                if t is None: 
                    continue
                wrapped_mcp_tools.append(wrap_mcp_tool(t, mcp_controller))  # ← 래핑된 걸 사용
            tools.extend(wrapped_mcp_tools)
            logger.info(
                f"[Agent] mcp_tools 추가됨: {len([t for t in mcp_tools if t is not None])}개"
            )
    except Exception as e:
        logger.error(f"[Agent] mcp_tools 로딩 실패: {e}")
        mcp_manager = None

    try:
        admin_tools = make_admin_tools(db, GuidelineRepoDB(db))
        if admin_tools:
            # ✅ admin.make_prevention만 래핑
            wrapped_admin_tools = []
            for t in admin_tools:
                if t is None:
                    continue
                if t.name == "admin.make_prevention":
                    wrapped_admin_tools.append(
                        wrap_admin_make_prevention(t, mcp_controller)
                    )
                else:
                    wrapped_admin_tools.append(t)
            
            tools.extend(wrapped_admin_tools)
            logger.info(
                f"[Agent] admin_tools 추가됨: {len(wrapped_admin_tools)}개"
            )
    except Exception as e:
        logger.error(f"[Agent] admin_tools 로딩 실패: {e}")

    # guidance_tool은 이미 admin_tools에 포함되어 있으므로 별도 추가하지 않음
    # 다만 확인용 로그 추가
    logger.info(f"[Agent] 전체 도구 수: {len(tools)}개")

    if use_tavily:
        try:
            tavily_tools = make_tavily_tools()
            if tavily_tools:
                tools.extend([t for t in tavily_tools if t is not None])
                logger.info(
                    f"[Agent] tavily_tools 추가됨: {len([t for t in tavily_tools if t is not None])}개"
                )
        except Exception as e:
            logger.error(f"[Agent] tavily_tools 로딩 실패: {e}")

    # None 값 필터링 및 도구 이름 확인
    tools = [t for t in tools if t is not None and hasattr(t, 'name')]
    tool_names = [t.name for t in tools]

    logger.info("[Agent] TOOLS REGISTERED: %s", tool_names)

    tool_strings = "\n".join([f"{tool.name}: {tool.description}" for tool in tools])
    tool_names_str = ", ".join([tool.name for tool in tools])

    # admin.generate_guidance가 등록되었는지 확인
    if 'admin.generate_guidance' not in tool_names:
        logger.error("[Agent] admin.generate_guidance 도구가 등록되지 않음!")
        logger.info("[Agent] 사용 가능한 admin 도구들: %s",
                    [name for name in tool_names if name.startswith('admin.')])

    prompt = ChatPromptTemplate.from_messages([
        ("system", REACT_SYS),
        ("human", "사용 가능한 도구들:\n{tools}\n\n"
         "도구 이름 목록: {tool_names}\n\n"
         "아래 포맷을 정확히 따르세요. 포맷 외 임의 텍스트/코드펜스/주석 금지.\n"
         "Thought: 한 줄\n"
         "Action: 도구이름  (예: mcp.simulator_run)\n"
         "Action Input: {{\"data\": {{...}}}}  # JSON 한 줄, 최상위 'data'\n"
         "Observation: (도구 출력)\n"
         "... 반복 ...\n"
         "Final Answer: 결론\n\n"
         "입력:\n{input}\n\n"
         "{agent_scratchpad}"),
    ])

    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
    ex = AgentExecutor(agent=agent,
                       tools=tools,
                       verbose=True,
                       handle_parsing_errors=True,
                       max_iterations=25,
                       max_execution_time=600,
                       early_stopping_method="force",
                       return_intermediate_steps=False,)
    
    
    return ex, mcp_manager, mcp_controller

async def run_orchestrated_stream(db: Session, payload: Dict[str, Any]):
    """SSE 스트리밍 with 터미널 로그 실시간 캡처"""
    from starlette.concurrency import run_in_threadpool

    req = SimulationStartRequest(**payload)

    # ── 동일 offender/victim 중복 실행 방지 ──
    key = _make_chain_key(int(req.offender_id or 0), int(req.victim_id or 0))
    lock = _active_chains.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _active_chains[key] = lock

    if lock.locked():
        yield {"type": "error", "message": "이미 진행 중인 시뮬레이션이 있습니다."}
        return

    async with lock:
        main_loop = asyncio.get_running_loop()
        mcp_manager = None
        mcp_controller = MCPController(max_rounds=5)

        # ✅ 세션 생성
        session = SimulationSession.create(
            offender_id=int(req.offender_id or 0),
            victim_id=int(req.victim_id or 0),
            case_id=payload.get("case_id")
        )

        logger.info("[SSE] 새 세션 생성: case_id=%s", session.case_id)

        # ✅ case_id 공지
        yield {
            "type": "case_created",
            "case_id": session.case_id,
            "offender_id": session.offender_id,
            "victim_id": session.victim_id,
            "timestamp": session.started_at.isoformat()
        }

        # ✅ 터미널 로그 큐 생성
        main_loop = asyncio.get_running_loop()
        terminal_log_queue = asyncio.Queue()

        # ✅✅✅ 핵심 추가: Logger 핸들러 등록
        class SSELogHandler(logging.Handler):
            def __init__(self, log_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
                super().__init__()
                self.log_queue = log_queue
                self.loop = loop  # ✅

            """Logger 출력을 SSE 큐로 전송하는 핸들러"""
            def emit(self, record):
                try:
                    msg = self.format(record)
                    if not msg.endswith("\n"):
                        msg += "\n"
                    self.loop.call_soon_threadsafe(           # ✅ 항상 메인 루프 사용
                        self.log_queue.put_nowait,
                        {
                            "type": "agent_log",
                            "event": "logger_output",
                            "data": {"text": msg},
                        }
                    )
                except Exception:
                    logger.error(f"SSELogHandler.emit error: {e}")
        
        sse_handler = SSELogHandler(terminal_log_queue, main_loop)
        sse_handler.setLevel(logging.DEBUG)  # 또는 logging.INFO
        sse_handler.setFormatter(logging.Formatter(
            '[%(levelname)s] %(name)s - %(message)s'
        ))
        
        # 루트 로거에 핸들러 추가
        root_logger = logging.getLogger()
        root_logger.addHandler(sse_handler)

        for name in ["", "uvicorn", "uvicorn.error", "uvicorn.access", "langchain", "httpx", "asyncio"]:
            lg = logging.getLogger(name)
            lg.addHandler(sse_handler)
            lg.setLevel(logging.DEBUG)
            lg.propagate = True

        try:
            # ✅ 터미널 캡처 시작
            async with capture_terminal_logs(terminal_log_queue, main_loop):
                
                # ── 에이전트 & MCP 도구 세팅 ──
                log_capture = RealtimeLogCapture()
                thought_capture = ThoughtCapture(
                    sse_queue=terminal_log_queue,  # ✅
                    case_id=session.case_id,  # ✅
                    loop=main_loop
                )
                stopping_callback = RoundLimitStoppingCallback(max_rounds=5)

                # ✅ 테스트: 즉시 로그 전송
                yield {
                    "type": "agent_log",
                    "data": {"text": "🔥 [TEST] thought_capture 생성 완료!"},
                    "case_id": session.case_id,
                    "ts": datetime.now().isoformat()
                }
                
                # ✅ 큐에 직접 넣어보기
                await terminal_log_queue.put({
                    "type": "agent_log",
                    "data": {"text": "🔥 [TEST] 큐 직접 전송 테스트!"},
                    "case_id": session.case_id,
                    "ts": datetime.now().isoformat()
                })

                ex, mcp_manager, mcp_controller = build_agent_and_tools(
                    db, use_tavily=req.use_tavily, mcp_controller=mcp_controller
                )

                # 🔌 턴 스트림 큐 등록
                turn_q: asyncio.Queue = mcp_controller.make_sink_queue()
                await mcp_controller.register_sink(turn_q)

                used_tools: List[str] = []
                guidance_history: List[Dict[str, Any]] = []
                previous_judgments: List[Dict[str, Any]] = []

                # ── 프롬프트 패키지 구성 ──
                pkg = await run_in_threadpool(
                    build_prompt_package_from_payload,
                    db, req,
                    tavily_result=None,
                    is_first_run=True,
                    skip_catalog_write=True,
                    enable_scenario_enhancement=True,
                )
                scenario = pkg["scenario"]
                victim_profile = pkg["victim_profile"]
                templates = pkg["templates"]

                max_rounds = max(2, min(req.round_limit or 3, 5))

                if "enhancement_info" in scenario:
                    yield {"type": "enhancement", "data": scenario["enhancement_info"]}

                guidance_info = None
                
                # ✅ 테스트 로그 5개 연속 전송
                for i in range(5):
                    yield {
                        "type": "agent_log",
                        "data": {"text": f"🔥 테스트 로그 {i+1}/5"},
                        "case_id": session.case_id,
                        "ts": datetime.now().isoformat()
                    }
                    await asyncio.sleep(0.1)

                # ============ 라운드 루프 ============
                for _ in range(max_rounds):
                    round_no = session.next_round()

                    try:
                        mcp_controller.start_round()
                    except RuntimeError as e:
                        logger.warning("[SSE] 라운드 시작 불가: %s", e)
                        break

                    log_capture.current_round = round_no

                    yield {
                        "type": "round_start",
                        "round": round_no,
                        "case_id": session.case_id,
                        "message": f"라운드 {round_no} 시작"
                    }

                    # 호출 페이로드
                    sim_payload: Dict[str, Any] = {
                        "offender_id": session.offender_id,
                        "victim_id": session.victim_id,
                        "scenario": scenario,
                        "victim_profile": victim_profile,
                        "templates": templates,
                        "max_turns": req.max_turns,
                        "round_no": round_no,
                    }
                    if round_no > 1:
                        sim_payload["case_id_override"] = session.case_id
                    if guidance_info and guidance_info.get("text"):
                        sim_payload["guidance"] = {"type": "A", "text": guidance_info["text"]}

                    llm_call = {
                        "input": (
                            "다음 JSON 블록을 **수정하지 말고 그대로** mcp.simulator_run의 Action Input으로 사용하라.\n"
                            f"{json.dumps({'data': sim_payload}, ensure_ascii=False)}"
                        )
                    }

                    # 진행상태 공지
                    yield {
                        "type": "simulation_progress",
                        "round": round_no,
                        "case_id": session.case_id,
                        "message": f"라운드 {round_no} 대화 생성 중...",
                        "status": "running",
                    }

                    # ── ✅ 에이전트 호출을 백그라운드 태스크로 시작 ──
                    agent_task = asyncio.create_task(
                        run_in_threadpool(
                            ex.invoke, llm_call, config={"callbacks": [log_capture, stopping_callback]}
                        )
                    )
                    used_tools.append("mcp.simulator_run")

                    # ── ✅ 3개 큐 동시 모니터링: 턴, 터미널 로그, 에이전트 완료 ──
                    get_turn_task = asyncio.create_task(turn_q.get())
                    get_log_task = asyncio.create_task(terminal_log_queue.get())

                    victim_buffers = {}
                    BUFFER_TIMEOUT = 0.5

                    def is_complete_json(text: str) -> bool:
                        text = text.strip()
                        if text.startswith("```json") or text.startswith("```"):
                            return text.count("```") >= 2
                        return True

                    while True:
                        done, _ = await asyncio.wait(
                            {agent_task, get_turn_task, get_log_task},
                            return_when=asyncio.FIRST_COMPLETED
                        )

                        # ✅ 터미널 로그 이벤트 처리 (최우선!)
                        if get_log_task in done:
                            log_ev = get_log_task.result()

                            
                            
                            # 프론트로 즉시 전송 (토큰 단위)
                            yield log_ev
                            
                            # 다음 로그 대기
                            get_log_task = asyncio.create_task(terminal_log_queue.get())

                        # ✅ 턴 이벤트 처리
                        if get_turn_task in done:
                            ev = get_turn_task.result()
                            
                            role = ev.get("role", "").lower()
                            turn_idx = ev.get("turn_index")
                            content = ev.get("content", "")
                            
                            if role == "victim":
                                if turn_idx in victim_buffers:
                                    victim_buffers[turn_idx]["content"] += content
                                else:
                                    victim_buffers[turn_idx] = {
                                        "content": content,
                                        "timestamp": asyncio.get_event_loop().time()
                                    }
                                
                                buffered_content = victim_buffers[turn_idx]["content"]
                                
                                if is_complete_json(buffered_content):
                                    complete_content = victim_buffers.pop(turn_idx)["content"]
                                    
                                    yield {
                                        "type": "new_message",
                                        "case_id": ev.get("case_id") or session.case_id,
                                        "round": ev["round"],
                                        "role": role,
                                        "turn_index": turn_idx,
                                        "content": complete_content,
                                        "created_kst": ev["created_kst"],
                                    }
                                else:
                                    elapsed = asyncio.get_event_loop().time() - victim_buffers[turn_idx]["timestamp"]
                                    if elapsed > BUFFER_TIMEOUT:
                                        partial_content = victim_buffers.pop(turn_idx)["content"]
                                        logger.warning(f"[SSE] victim JSON 타임아웃, 강제 전송: turn={turn_idx}")
                                        
                                        yield {
                                            "type": "new_message",
                                            "case_id": ev.get("case_id") or session.case_id,
                                            "round": ev["round"],
                                            "role": role,
                                            "turn_index": turn_idx,
                                            "content": partial_content,
                                            "created_kst": ev["created_kst"],
                                        }
                            else:
                                yield {
                                    "type": "new_message",
                                    "case_id": ev.get("case_id") or session.case_id,
                                    "round": ev["round"],
                                    "role": role,
                                    "turn_index": turn_idx,
                                    "content": content,
                                    "created_kst": ev["created_kst"],
                                }
                            
                            get_turn_task = asyncio.create_task(turn_q.get())

                        # ✅ 에이전트 실행이 완료되면 루프 종료
                        if agent_task in done:
                            res_run = agent_task.result() if not agent_task.cancelled() else None

                            if res_run:
                                # ✅ output 필드에서 에이전트 로그 추출
                                output_text = str(res_run.get("output", ""))
                                
                                # ✅ 전체 output을 로그로 전송 (500자씩 나눠서)
                                
                                yield {
                                    "type": "agent_log",
                                    "data": {"text": output_text},
                                    "case_id": session.case_id,
                                    "ts": datetime.now().isoformat()
                                }
                                
                                # ✅ 또는 패턴별로 파싱해서 전송
                                import re
                                
                                # Thought 추출
                                thoughts = re.findall(r'Thought:\s*(.+?)(?=\n(?:Action|Observation|Final Answer)|$)', output_text, re.DOTALL)
                                for thought in thoughts:
                                    yield {
                                        "type": "agent_log",
                                        "data": {"text": f"💭 Thought: {thought.strip()[:200]}"},
                                        "case_id": session.case_id,
                                        "ts": datetime.now().isoformat()
                                    }
                                
                                # Action 추출
                                actions = re.findall(r'Action:\s*(.+?)(?=\n)', output_text)
                                for action in actions:
                                    yield {
                                        "type": "agent_log",
                                        "data": {"text": f"⚡ Action: {action.strip()}"},
                                        "case_id": session.case_id,
                                        "ts": datetime.now().isoformat()
                                    }
                                
                                # Action Input 추출
                                action_inputs = re.findall(r'Action Input:\s*(.+?)(?=\nObservation|$)', output_text, re.DOTALL)
                                for action_input in action_inputs:
                                    yield {
                                        "type": "agent_log",
                                        "data": {"text": f"📥 Action Input: {action_input.strip()[:200]}..."},
                                        "case_id": session.case_id,
                                        "ts": datetime.now().isoformat()
                                    }
                                
                                # Observation 추출
                                observations = re.findall(r'Observation:\s*(.+?)(?=\nThought|$)', output_text, re.DOTALL)
                                for observation in observations:
                                    yield {
                                        "type": "agent_log",
                                        "data": {"text": f"👁️ Observation: {observation.strip()[:300]}..."},
                                        "case_id": session.case_id,
                                        "ts": datetime.now().isoformat()
                                    }
                            # 남은 태스크 정리
                            for task in [get_turn_task, get_log_task]:
                                if not task.done():
                                    task.cancel()
                                    with contextlib.suppress(asyncio.CancelledError):
                                        await task
                            
                            # 버퍼에 남은 미완성 victim 턴 강제 전송
                            for turn_idx in list(victim_buffers.keys()):
                                partial = victim_buffers.pop(turn_idx)["content"]
                                logger.warning(f"[SSE] 종료 시 미완성 victim 턴 발견: turn={turn_idx}")
                                
                                yield {
                                    "type": "new_message",
                                    "case_id": session.case_id,
                                    "round": round_no,
                                    "role": "victim",
                                    "turn_index": turn_idx,
                                    "content": partial,
                                    "created_kst": datetime.now().isoformat(),
                                }
                            
                            break

                    # ✅✅✅ 여기서부터 추가! ✅✅✅

                    # 에이전트 결과 파싱
                    res_run = agent_task.result() if not agent_task.cancelled() else None

                    if res_run and isinstance(res_run, dict):
                        # ✅ 구분선
                        yield {
                            "type": "agent_log",
                            "data": {"text": "=" * 60},
                            "case_id": session.case_id,
                            "ts": datetime.now().isoformat()
                        }
                        
                        yield {
                            "type": "agent_log",
                            "data": {"text": f"📋 [에이전트 실행 결과] 라운드 {round_no}"},
                            "case_id": session.case_id,
                            "ts": datetime.now().isoformat()
                        }
                        
                        yield {
                            "type": "agent_log",
                            "data": {"text": "=" * 60},
                            "case_id": session.case_id,
                            "ts": datetime.now().isoformat()
                        }
                        
                        # ✅ intermediate_steps 파싱
                        steps = res_run.get("intermediate_steps", [])
                        
                        if steps:
                            for idx, step in enumerate(steps, 1):
                                try:
                                    action, observation = step
                                    
                                    # Action 전송
                                    yield {
                                        "type": "agent_log",
                                        "data": {"text": f"\n🔹 Step {idx}"},
                                        "case_id": session.case_id,
                                        "ts": datetime.now().isoformat()
                                    }
                                    
                                    yield {
                                        "type": "agent_log",
                                        "data": {"text": f"⚡ Action: {action.tool}"},
                                        "case_id": session.case_id,
                                        "ts": datetime.now().isoformat()
                                    }
                                    
                                    action_input_str = str(action.tool_input)
                                    if len(action_input_str) > 300:
                                        action_input_str = action_input_str[:300] + "..."
                                    
                                    yield {
                                        "type": "agent_log",
                                        "data": {"text": f"📥 Action Input: {action_input_str}"},
                                        "case_id": session.case_id,
                                        "ts": datetime.now().isoformat()
                                    }
                                    
                                    # Observation 전송
                                    observation_str = str(observation)
                                    if len(observation_str) > 500:
                                        observation_str = observation_str[:500] + "..."
                                    
                                    yield {
                                        "type": "agent_log",
                                        "data": {"text": f"👁️ Observation: {observation_str}"},
                                        "case_id": session.case_id,
                                        "ts": datetime.now().isoformat()
                                    }
                                    
                                except Exception as e:
                                    logger.error(f"[SSE] intermediate_steps 파싱 실패: {e}")
                                    yield {
                                        "type": "agent_log",
                                        "data": {"text": f"❌ Step 파싱 실패: {str(e)}"},
                                        "case_id": session.case_id,
                                        "ts": datetime.now().isoformat()
                                    }
                        else:
                            yield {
                                "type": "agent_log",
                                "data": {"text": "⚠️ intermediate_steps가 비어있음"},
                                "case_id": session.case_id,
                                "ts": datetime.now().isoformat()
                            }
                        
                        # ✅ Final Answer (output)
                        if "output" in res_run:
                            yield {
                                "type": "agent_log",
                                "data": {"text": "\n✅ Final Answer:"},
                                "case_id": session.case_id,
                                "ts": datetime.now().isoformat()
                            }
                            
                            output_str = str(res_run["output"])
                            # 500자씩 나눠서 전송
                            
                            yield {
                                "type": "agent_log",
                                "data": {"text": output_text},
                                "case_id": session.case_id,
                                "ts": datetime.now().isoformat()
                            }
                        
                        yield {
                            "type": "agent_log",
                            "data": {"text": "=" * 60 + "\n"},
                            "case_id": session.case_id,
                            "ts": datetime.now().isoformat()
                        }

                    # ✅✅✅ 여기까지 추가! ✅✅✅

                    # ── ✅ 라운드 종료 후: 로그 백필 ──
                    round_logs = log_capture.get_round_logs(round_no)
                    
                    if (not round_logs) and isinstance(res_run, dict):
                        conv_logs_str = res_run.get("conversation_logs")
                        if isinstance(conv_logs_str, str):
                            parsed = parse_conversation_logs(conv_logs_str, target_round=round_no)
                            if parsed:
                                round_logs = parsed
                                logger.info(f"[SSE] 백필 파싱: {len(parsed)}개 로그 복구")

                    if round_no == 1 and round_logs:
                        real_case = next((l.get("case_id") for l in round_logs if l.get("case_id")), None)
                        if real_case and real_case != session.case_id:
                            logger.warning("[SSE] case_id 업데이트: %s → %s", session.case_id, real_case)
                            session.case_id = real_case
                            yield {
                                "type": "case_id_updated",
                                "case_id": session.case_id,
                                "reason": "로그에서 실제 case_id 확인"
                            }

                    if round_logs:
                        round_logs = sorted(round_logs, key=lambda x: x.get("turn_index", 0))
                        yield {
                            "type": "conversation_logs",
                            "round": round_no,
                            "logs": round_logs,
                            "total_turns": len(round_logs),
                            "case_id": session.case_id,
                            "status": "completed",
                        }
                        logger.info("[SSE] ✅ 라운드 %s: %s개 로그 전송 (백필)", round_no, len(round_logs))
                    else:
                        logger.warning("[SSE] ⚠️ 라운드 %s: 로그 없음", round_no)
                        yield {
                            "type": "conversation_logs",
                            "round": round_no,
                            "logs": [],
                            "total_turns": 0,
                            "case_id": session.case_id,
                            "status": "no_logs",
                        }

                    yield {
                        "type": "round_complete",
                        "round": round_no,
                        "case_id": session.case_id,
                        "total_turns": len(round_logs),
                    }

                    # ── 판정 ──
                    res_judge = await run_in_threadpool(
                        ex.invoke,
                        {"input": json.dumps({"data": {"case_id": session.case_id, "run_no": round_no}}, ensure_ascii=False)},
                        config={"callbacks": [log_capture, thought_capture, stopping_callback]},
                    )
                    used_tools.append("admin.judge")

                    phishing = _extract_phishing(res_judge)
                    reason = _extract_reason(res_judge)

                    previous_judgments.append({
                        "round": round_no,
                        "phishing": phishing,
                        "reason": reason,
                        "timestamp": datetime.now().isoformat(),
                    })

                    # ✅ 분석 결과 전송
                    yield {
                        "type": "analysis",
                        "round": round_no,
                        "case_id": session.case_id,
                        "data": {
                            "phishing": phishing,
                            "reason": reason,
                            "timestamp": datetime.now().isoformat(),
                        }
                    }

                    # ── 다음 라운드 지침 생성 ──
                    if round_no < max_rounds:
                        guidance_input = {
                            "input": f"""admin.generate_guidance를 호출:
                            - case_id: {session.case_id}
                            - round_no: {round_no + 1}
                            - scenario: {json.dumps(scenario, ensure_ascii=False)}
                            - victim_profile: {json.dumps(victim_profile, ensure_ascii=False)}
                            - previous_judgments: {json.dumps(previous_judgments, ensure_ascii=False)}"""
                        }
                        res_guidance = await run_in_threadpool(
                            ex.invoke, guidance_input, config={"callbacks": [log_capture, thought_capture, stopping_callback]}
                        )
                        guidance_info = _extract_guidance_info(res_guidance)
                        guidance_history.append({
                            "round": round_no + 1,
                            "guidance": guidance_info,
                            "timestamp": datetime.now().isoformat(),
                        })
                        yield {
                            "type": "guidance_generated",
                            "round": round_no + 1,
                            "case_id": session.case_id,
                            "guidance": guidance_info,
                        }

                    # ── 예방책 저장 ──
                    save_payload = {
                        "case_id": session.case_id,
                        "offender_id": session.offender_id,
                        "victim_id": session.victim_id,
                        "run_no": round_no,
                        "summary": f"Round {round_no} judgement: {'PHISHING' if phishing else 'NOT PHISHING'}. Reason: {reason}",
                        "steps": {
                            "prevention_steps": [
                                "낯선 연락의 긴급 요구는 의심한다.",
                                "공식 채널로 재확인한다(콜백/앱/웹).",
                                "개인·금융정보를 전화/메신저로 제공하지 않는다.",
                                "가족·지인 사칭 시 직접 연락으로 확인한다.",
                                "의심스러우면 즉시 경찰서나 금융감독원에 신고한다.",
                            ]
                        }
                    }
                    if "enhancement_info" in scenario:
                        save_payload["steps"]["scenario_enhancement"] = scenario["enhancement_info"]
                    if guidance_info and guidance_info.get("text"):
                        save_payload["steps"]["guidance_applied"] = guidance_info

                    await run_in_threadpool(
                        ex.invoke,
                        {"input": json.dumps({"data": save_payload}, ensure_ascii=False)},
                        config={"callbacks": [log_capture, thought_capture, stopping_callback]},
                    )

                    log_capture.next_round()

                    # 종료 조건
                    if not should_continue_rounds({"phishing": phishing}, round_no):
                        logger.info("[SSE] 종료 조건 충족: round=%s", round_no)
                        break

                # ── 최종 예방책 생성 ──
                final_payload = {
                    "case_id": session.case_id,
                    "rounds": session.round_no,
                    "turns": log_capture.all_logs,
                    "judgements": previous_judgments,
                    "guidances": guidance_history,
                    "format": "personalized_prevention",
                }
                await run_in_threadpool(
                    ex.invoke,
                    {"input": json.dumps({"data": final_payload}, ensure_ascii=False)},
                    config={"callbacks": [log_capture, thought_capture, stopping_callback]},
                )

                session.complete()
                yield {
                    "type": "complete",
                    "case_id": session.case_id,
                    "rounds": session.round_no,
                    "status": session.status,
                    "used_tools": used_tools,
                    "total_logs": len(log_capture.all_logs),
                    "duration": (datetime.now() - session.started_at).total_seconds(),
                }

            # ✅ capture_terminal_logs 컨텍스트 종료 → stdout 자동 복구

            # 즉시 종료 + 자원 해제
            try:
                await mcp_controller.unregister_sink(turn_q)
            except Exception:
                pass
            if mcp_controller:
                mcp_controller.shutdown()
            if mcp_manager and getattr(mcp_manager, "is_running", False):
                await run_in_threadpool(mcp_manager.stop_mcp_server)

            logger.info("[SSE] 시뮬레이션 완료: case_id=%s, rounds=%s, logs=%s",
                        session.case_id, session.round_no, len(log_capture.all_logs))
            return

        except Exception as e:
            session.fail(str(e))
            logger.exception("SSE 스트리밍 실패")
            yield {"type": "error", "case_id": session.case_id, "message": f"시뮬레이션 오류: {str(e)}"}

        finally:
            # 안전한 정리
            root_logger.removeHandler(sse_handler)
            with contextlib.suppress(Exception):
                await mcp_controller.unregister_sink(turn_q)
            with contextlib.suppress(Exception):
                if mcp_controller:
                    mcp_controller.shutdown()
            with contextlib.suppress(Exception):
                if mcp_manager and getattr(mcp_manager, "is_running", False):
                    await run_in_threadpool(mcp_manager.stop_mcp_server)

            try:
                if _active_chains.get(key) is lock:
                    del _active_chains[key]
            except Exception:
                pass

            logger.info("[SSE] 리소스 정리 완료: case_id=%s", session.case_id)