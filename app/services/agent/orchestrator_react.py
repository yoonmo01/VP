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

def parse_conversation_logs(text: str, target_round: int = None) -> List[Dict]:
    """
    MCP 출력에서 대화 로그를 파싱
    
    Args:
        text: MCP 도구 출력 텍스트
        target_round: 특정 라운드만 필터링 (None이면 전체)
    
    Returns:
        파싱된 로그 리스트
    """
    logs = []
    
    # 여러 패턴 시도 (MCP 출력 형식 변화 대응)
    patterns = [
        # 표준: [Conversation][case:xxx][run:1][turn:0][offender] 내용
        r'\[Conversation\]\[case:([^\]]+)\]\[run:(\d+)\]\[turn:(\d+)\]\[(offender|victim)\]\s+(.+?)(?=\n\[Conversation\]|$)',
        
        # 개행 포함
        r'\[Conversation\]\[case:([^\]]+)\]\[run:(\d+)\]\[turn:(\d+)\]\[(offender|victim)\]\s*\n\s*(.+?)(?=\n\[Conversation\]|$)',
        
        # 공백 관대
        r'\[\s*Conversation\s*\]\s*\[case:([^\]]+)\]\s*\[run:(\d+)\]\s*\[turn:(\d+)\]\s*\[(offender|victim)\]\s+(.+?)(?=\n\[|$)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL | re.MULTILINE)
        
        for match in matches:
            case_id, run, turn, role, content = match
            run_no = int(run)
            
            if target_round is None or run_no == target_round:
                logs.append({
                    "case_id": case_id.strip(),
                    "run": run_no,
                    "turn_index": int(turn),
                    "role": role.strip(),
                    "content": content.strip(),
                    "created_kst": datetime.now().isoformat(),
                })
        
        if logs:  # 성공하면 중단
            logger.info(f"[Parser] 패턴 {patterns.index(pattern)+1}로 {len(logs)}개 로그 파싱 성공")
            break
    
    if not logs:
        logger.warning(f"[Parser] 로그 파싱 실패. 텍스트 길이: {len(text)}")
        logger.debug(f"[Parser] 텍스트 샘플:\n{text[:500]}")
    
    return logs

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

@dataclass
class ThoughtCapture(BaseCallbackHandler):
    last_tool: Optional[str] = None
    last_tool_input: Optional[Any] = None
    events: list = field(default_factory=list)
    conversation_logs: list = field(default_factory=list)  # ✅ 추가

    def on_agent_action(self, action, **kwargs):
        rec = {
            "type": "action",
            "tool": getattr(action, "tool", "?"),
            "tool_input": getattr(action, "tool_input", None),
        }
        self.last_tool = rec["tool"]
        self.last_tool_input = rec["tool_input"]
        self.events.append(rec)
        logger.info("[AgentThought] Tool=%s | Input=%s", rec["tool"],
                    _truncate(rec["tool_input"]))

    def on_agent_finish(self, finish, **kwargs):
        self.events.append({"type": "finish", "log": finish.log})
        
        # ✅ MCP 로그 파싱
        log_text = str(finish.log)

        # ✅ 디버그: finish.log 내용 확인
        logger.info("="*80)
        logger.info("[DEBUG] finish.log 전체 내용:")
        logger.info(log_text[:2000])  # 처음 2000자만
        logger.info("="*80)
        import re
        
        # 패턴: [Conversation][case:...][run:X][turn:Y][offender/victim] 내용
        pattern = r'\[Conversation\]\[case:[^\]]+\]\[run:(\d+)\]\[turn:(\d+)\]\[(offender|victim)\]\s+(.+?)(?=\n\[|$)'
        matches = re.findall(pattern, log_text, re.DOTALL)
        
        logger.info(f"[ThoughtCapture] finish.log 길이: {len(log_text)}")
        logger.info(f"[ThoughtCapture] 매칭된 로그: {len(matches)}개")

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

        logger.info("[AgentFinish] %s", _truncate(finish.log, 1200))

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
    """SSE 스트리밍 with 안전한 case_id 관리 (턴 단위 실시간 + 라운드 단위 백필)"""
    from starlette.concurrency import run_in_threadpool

    req = SimulationStartRequest(**payload)

    # ── 동일 offender/victim 중복 실행 방지 ──
    key = _make_chain_key(int(req.offender_id or 0), int(req.victim_id or 0))
    lock = _active_chains.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _active_chains[key] = lock

    if lock.locked():
        yield {"type": "error", "message": "이미 진행 중인 시뮬레이션이 있습니다. 완료 후 다시 시도하세요."}
        return

    async with lock:
        mcp_manager = None
        mcp_controller = MCPController(max_rounds=5)

        # ✅ 세션 생성(프론트가 준 case_id가 있으면 사용)
        session = SimulationSession.create(
            offender_id=int(req.offender_id or 0),
            victim_id=int(req.victim_id or 0),
            case_id=payload.get("case_id")
        )

        logger.info(
            "[SSE] 새 세션 생성: case_id=%s, offender=%s, victim=%s",
            session.case_id, session.offender_id, session.victim_id
        )

        # ✅ 즉시 프론트에 case_id 공지
        yield {
            "type": "case_created",
            "case_id": session.case_id,
            "offender_id": session.offender_id,
            "victim_id": session.victim_id,
            "timestamp": session.started_at.isoformat()
        }

        try:
            # ── 에이전트 & MCP 도구 세팅 ──
            log_capture = RealtimeLogCapture()
            stopping_callback = RoundLimitStoppingCallback(max_rounds=5)

            ex, mcp_manager, mcp_controller = build_agent_and_tools(
                db, use_tavily=req.use_tavily, mcp_controller=mcp_controller
            )

            # 🔌 턴 스트림 큐 등록 (실시간 new_message 용)
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

                # ── ✅ 핵심: 에이전트 호출과 턴 스트리밍을 동시에 처리 ──
                agent_task = asyncio.create_task(
                    run_in_threadpool(
                        ex.invoke, llm_call, config={"callbacks": [log_capture, stopping_callback]}
                    )
                )
                used_tools.append("mcp.simulator_run")

                # ── ✅ 동시에 큐에서 턴 이벤트를 즉시 퍼블리시 ──
                get_task = asyncio.create_task(turn_q.get())

                # JSON 버퍼
                victim_json_buffer = {}
                
                # ✅ 중요: 에이전트 실행 중에 턴 이벤트를 실시간으로 전송
                while True:
                    done, _ = await asyncio.wait(
                        {agent_task, get_task}, return_when=asyncio.FIRST_COMPLETED
                    )

                    # 턴 이벤트가 도착하면 즉시 프론트로 전송
                    if get_task in done:
                        ev = get_task.result()

                        role = ev.get("role", "").lower()
                        turn_idx = ev.get("turn_index")
                        content = ev.get("content", "")

                        # ✅ victim이고 JSON 블록인 경우 버퍼링
                        if role == "victim" and (content.strip().startswith("```json") or turn_idx in victim_json_buffer):
                            # 버퍼에 추가
                            if turn_idx not in victim_json_buffer:
                                victim_json_buffer[turn_idx] = ""
                            victim_json_buffer[turn_idx] += content
                            
                            # 완성 체크: ```으로 끝나면 완성
                            if victim_json_buffer[turn_idx].strip().endswith("```"):
                                # 완성된 JSON 전송
                                complete_content = victim_json_buffer.pop(turn_idx)
                                
                                yield {
                                    "type": "new_message",
                                    "case_id": ev.get("case_id") or session.case_id,
                                    "round": ev["round"],
                                    "role": role,
                                    "turn_index": turn_idx,
                                    "content": complete_content,  # ✅ 완전한 JSON
                                    "created_kst": ev["created_kst"],
                                }
                            # 아직 미완성이면 다음 조각 대기
                            else:
                                pass  # 계속 버퍼링

                        # ✅ victim이 아니거나 JSON 블록이 아니면 즉시 전송    
                        else:
                            # ✅ new_message 이벤트로 즉시 전송
                            yield {
                                "type": "new_message",
                                "case_id": ev.get("case_id") or session.case_id,
                                "round": ev["round"],
                                "role": ev["role"],
                                "turn_index": ev["turn_index"],
                                "content": ev["content"],
                                "created_kst": ev["created_kst"],
                            }
                        
                        # 다음 이벤트 대기
                        get_task = asyncio.create_task(turn_q.get())

                    # 에이전트 실행이 완료되면 루프 종료
                    if agent_task in done:
                        # 남은 get_task 정리
                        if not get_task.done():
                            get_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await get_task

                        # ✅ 버퍼에 남은 미완성 JSON 처리
                        for turn_idx, partial in victim_json_buffer.items():
                            logger.warning(f"[SSE] 미완성 victim JSON 발견: turn={turn_idx}")
                            # 그래도 전송 (extractDialogueOrPlainText가 처리)
                            yield {
                                "type": "new_message",
                                "case_id": session.case_id,
                                "round": round_no,
                                "role": "victim",
                                "turn_index": turn_idx,
                                "content": partial,
                                "created_kst": datetime.now().isoformat(),
                            }
                        victim_json_buffer.clear()
                        
                        break

                # ── ✅ 라운드 종료 후: 로그 백필 (누락 방지용 배열) ──
                round_logs = log_capture.get_round_logs(round_no)

                # 콜백이 비었으면 MCP 반환의 conversation_logs(문자열) 파싱
                res_run = agent_task.result() if not agent_task.cancelled() else None
                
                # ✅ 백필: conversation_logs 문자열이 있으면 파싱
                if (not round_logs) and isinstance(res_run, dict):
                    # res_run이 dict인 경우 conversation_logs 확인
                    conv_logs_str = res_run.get("conversation_logs")
                    if isinstance(conv_logs_str, str):
                        parsed = parse_conversation_logs(conv_logs_str, target_round=round_no)
                        if parsed:
                            round_logs = parsed
                            logger.info(f"[SSE] 백필 파싱: {len(parsed)}개 로그 복구")

                # ✅ 라운드1에서 MCP가 생성한 실제 case_id로 갱신
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

                # ✅ conversation_logs 이벤트 (배열로 전송 - 백업/검증용)
                if round_logs:
                    round_logs = sorted(round_logs, key=lambda x: x.get("turn_index", 0))
                    yield {
                        "type": "conversation_logs",
                        "round": round_no,
                        "logs": round_logs,  # ← 배열로 전송 (문자열 아님!)
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
                    config={"callbacks": [log_capture, stopping_callback]},
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

                yield {
                    "type": "judgement",
                    "round": round_no,
                    "case_id": session.case_id,
                    "phishing": phishing,
                    "reason": reason,
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
                        ex.invoke, guidance_input, config={"callbacks": [log_capture, stopping_callback]}
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
                    config={"callbacks": [log_capture, stopping_callback]},
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
                config={"callbacks": [log_capture, stopping_callback]},
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
            with contextlib.suppress(Exception):
                await mcp_controller.unregister_sink(turn_q)
            with contextlib.suppress(Exception):
                if mcp_controller:
                    mcp_controller.shutdown()
            with contextlib.suppress(Exception):
                if mcp_manager and getattr(mcp_manager, "is_running", False):
                    await run_in_threadpool(mcp_manager.stop_mcp_server)

            # 락 맵 정리
            try:
                # 현재 lock 객체와 동일할 때만 제거
                if _active_chains.get(key) is lock:
                    del _active_chains[key]
            except Exception:
                pass

            logger.info("[SSE] 리소스 정리 완료: case_id=%s", session.case_id)