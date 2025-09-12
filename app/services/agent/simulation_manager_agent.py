# app/services/agent/simulation_manager_agent.py (수정 버전)
"""
시뮬레이션 관리자 React Agent - 필요시에만 MCP 호출
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from uuid import UUID
import json
import asyncio
import subprocess
import threading
import time
import ast
from datetime import datetime

from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import Tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.llm_providers import agent_chat
from app.services.conversations_read import fetch_logs_by_case
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _coerce_jsonlike(s: str | dict) -> dict:
    if isinstance(s, dict):
        return s
    try:
        return json.loads(s)
    except Exception:
        try:
            return ast.literal_eval(s)  # '...' 단따옴표 dict 보정
        except Exception:
            raise ValueError("Invalid JSON-like input")


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


class OnDemandMCPManager:
    """필요할 때만 MCP 서버를 시작/종료하는 관리자"""

    def __init__(self):
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.server = None
        self.is_running = False
        self.url = "ws://127.0.0.1:8001/mcp"
        self._ready = threading.Event()

    async def start_mcp_server_if_needed(self) -> str:
        """MCP 서버가 필요하면 시작"""
        if self.is_running:
            return self.url

        try:
            self._ready.clear()
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            # 서버 준비될 때까지 대기
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
        import websockets
        from websockets.server import serve

        async def mcp_handler(websocket, path):
            try:
                async for message in websocket:
                    msg = json.loads(message)
                    response = await self._handle_mcp_message(msg)
                    if response:
                        await websocket.send(json.dumps(response))
            except Exception as e:
                logger.error(f"MCP 핸들러 오류: {e}")

        self.server = await serve(
            mcp_handler,
            "127.0.0.1",
            8001,
            ping_interval=30,  # 기본 20 → 30초
            ping_timeout=120,  # 기본 20 → 120초
            close_timeout=10,  # 종료 여유
            max_queue=None,  # backpressure 완화
        )
        logger.info("MCP 서버가 ws://127.0.0.1:8001 에서 시작됨")

    async def _handle_mcp_message(
            self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """MCP 메시지 처리"""
        msg_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "serverInfo": {
                        "name": "on-demand-mcp",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": {
                            "listChanged": True
                        }
                    }
                }
            }
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [{
                        "name": "simulator.run",
                        "description": "Run simulation",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "offender_id": {
                                    "type": "integer"
                                },
                                "victim_id": {
                                    "type": "integer"
                                },
                                "scenario": {
                                    "type": "object"
                                }
                            }
                        }
                    }]
                }
            }
        elif method == "tools/call":
            args = params.get("arguments", {})
            # 시뮬레이션 실행
            try:
                result = await asyncio.to_thread(
                    self._run_simulation_directly_blocking, args)
            except Exception as e:
                logger.exception("[MCP] simulator.run 실행 오류")
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32000,
                        "message": str(e)
                    }
                }

            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": result
                }
            }

        return None

    def _run_loop(self):
        """전용 이벤트 루프를 백그라운드 스레드에서 실행"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            # 서버 생성 후 run_forever
            async def _start():
                await self._start_embedded_mcp_server()
                self._ready.set()

            self.loop.run_until_complete(_start())
            self.loop.run_forever()
        except Exception as e:
            logger.error(f"MCP 루프 실행 오류: {e}")
        finally:
            # 루프 종료시 정리
            pending = asyncio.all_tasks(loop=self.loop)
            for t in pending:
                t.cancel()
            try:
                self.loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            self.loop.close()

    def _run_simulation_directly_blocking(
            self, args: Dict[str, Any]) -> Dict[str, Any]:
        """(블로킹) 시뮬레이션 직접 실행 - 스레드에서 돌아갑니다."""
        from app.db.session import SessionLocal
        from app.services.simulation import run_two_bot_simulation
        from types import SimpleNamespace

        db = SessionLocal()
        try:
            sim_request = SimpleNamespace(
                offender_id=args.get("offender_id", 1),
                victim_id=args.get("victim_id", 1),
                max_rounds=args.get("max_rounds", 20),
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
        """서버와 루프를 안전하게 종료"""
        if not self.is_running or not self.loop:
            return
        try:

            async def _shutdown():
                if self.server is not None:
                    self.server.close()
                    await self.server.wait_closed()

            fut = asyncio.run_coroutine_threadsafe(_shutdown(), self.loop)
            try:
                fut.result(timeout=2)
            except Exception as e:
                logger.warning(f"MCP 서버 종료 대기 중 예외: {e}")

            # 루프 정지
            self.loop.call_soon_threadsafe(self.loop.stop)

            # 스레드 합류
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=2)
            self.is_running = False
            logger.info("MCP 서버 종료됨")
        except Exception as e:
            logger.error(f"MCP 서버 종료 실패: {e}")


class SimulationManagerAgent:
    """
    시뮬레이션 관리자 React Agent - 필요시에만 MCP 호출
    """

    def __init__(self, db: Session):
        self.db = db
        self.llm = agent_chat()
        self.mcp_manager = OnDemandMCPManager()

        # React 프롬프트
        JSON_FORMAT_GUIDE = (
            'analyze_victim_profile 입력: {"victim_info": {...}}\n'
            'execute_simulation_with_mcp 입력: {"offender_id": 1, "victim_id": 1, "scenario": {...}, "max_rounds": 20}\n'
            'analyze_simulation_results 입력: {"case_id": "UUID", "run_no": 1}')

        self.react_prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 보이스피싱 시뮬레이션 전문 관리자입니다."
             "사용자가 제공한 정보를 바탕으로 최적의 시뮬레이션을 기획하고 실행합니다."
             "당신의 핵심 역할은 피해자 프로필과 시나리오 분석, 적절한 LLM 모델 선택 및 프롬프트 최적화, 시뮬레이션 실행 (필요시 MCP 서버 호출), 결과 분석 및 개선 방안 제시입니다."
             ),
            ("human", "사용 가능한 도구들:\n{tools}\n\n"
             "도구 이름 목록: {tool_names}\n\n"
             "아래 형식을 엄수하세요:\n"
             "Thought: 문제에 대한 당신의 생각\n"
             "Action: [{tool_names} 중 하나의 정확한 이름]\n"
             "Action Input: JSON 한 줄 (줄바꿈 없이)\n"
             "Observation: 도구 실행 결과\n"
             "... 필요하면 Thought/Action 반복 ...\n"
             "Final Answer: 최종 요약/권고\n\n"
             "Question: {input}"
             "{agent_scratchpad}"),
        ])

        # 도구들 생성
        self.tools = self._create_simulation_tools()

        # Agent 생성
        self.agent = create_react_agent(llm=self.llm,
                                        tools=self.tools,
                                        prompt=self.react_prompt)

        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            max_iterations=15,
            handle_parsing_errors=True,
        )
        # return_intermediate_steps=True)

        logger.info(f"[react_prompt.vars] {self.react_prompt.input_variables}")
        logger.info(
            f"[prompt.last] {type(self.react_prompt.messages[-1]).__name__}")
        try:
            from langchain_core.messages import BaseMessage
            # agent_scratchpad placeholder 확인 (마지막 메시지가 MessagesPlaceholder인지 검사)
            last = self.react_prompt.messages[-1]
            logger.info(f"[react_prompt.last] {type(last)}")
        except Exception as e:
            logger.warning(f"[react_prompt.inspect_error] {e}")

    def _create_simulation_tools(self) -> List[Tool]:
        """시뮬레이션 관리 도구들"""

        def analyze_victim_profile(input_text: str) -> str:
            """피해자 프로필 분석 **바꿔야 할 부분 """
            try:
                data = _coerce_jsonlike(input_text)
                # 사용자가 victim_info만 바로 넣어도 보정
                if "victim_info" not in data and all(
                        k in data for k in ("age", "tech_literacy")):
                    data = {"victim_info": data}
                victim_info = data.get("victim_info", {})

                analysis = {
                    "risk_factors": [],
                    "protective_factors": [],
                    "vulnerability_score": 0.5,
                    "recommended_approach": ""
                }

                # 간단한 분석 로직
                age = victim_info.get("age", 0)
                tech_literacy = victim_info.get("tech_literacy", "medium")
                personality = victim_info.get("personality", {})

                if age > 65:
                    analysis["risk_factors"].append("고령층")
                    analysis["vulnerability_score"] += 0.2

                if tech_literacy == "low":
                    analysis["risk_factors"].append("낮은 기술 이해도")
                    analysis["vulnerability_score"] += 0.3

                if personality.get("trusting", False):
                    analysis["risk_factors"].append("신뢰적 성격")
                    analysis["vulnerability_score"] += 0.2

                # 접근 방식 결정
                if analysis["vulnerability_score"] > 0.7:
                    analysis["recommended_approach"] = "강력한 예방 교육 필요"
                elif analysis["vulnerability_score"] > 0.4:
                    analysis["recommended_approach"] = "균형잡힌 접근"
                else:
                    analysis["recommended_approach"] = "고급 시나리오 훈련"

                return json.dumps(analysis, ensure_ascii=False)

            except Exception as e:
                return f"프로필 분석 실패: {str(e)}"

        def execute_simulation_with_mcp(input_text: str) -> str:
            """MCP를 통한 시뮬레이션 실행 - 여기서 MCP 서버 시작"""
            try:
                data = _coerce_jsonlike(input_text)

                if "simulation_settings" in data and isinstance(
                        data["simulation_settings"], dict):
                    data = data["simulation_settings"]

                # 필수 키 보정/기본값
                data.setdefault("offender_id", 1)
                data.setdefault("victim_id", 1)
                data.setdefault("max_rounds", 3)
                data.setdefault("scenario", {})

                logger.info(
                    f"[MCP] calling simulator.run with offender_id={data['offender_id']} victim_id={data['victim_id']} max_rounds={data['max_rounds']}"
                )

                # MCP 서버 on-demand 시작 (이벤트 루프 안전)
                mcp_url = run_coro_safely(
                    self.mcp_manager.start_mcp_server_if_needed())
                if not mcp_url:
                    return "MCP 서버 시작 실패"
                self.mcp_url = mcp_url

                # 클라이언트 호출
                result = run_coro_safely(self._call_mcp_simulation(data))
                # # MCP 서버를 필요시에만 시작
                # mcp_url = asyncio.run(
                #     self.mcp_manager.start_mcp_server_if_needed())
                # if not mcp_url:
                #     return "MCP 서버 시작 실패"

                # # MCP 클라이언트로 시뮬레이션 요청
                # result = asyncio.run(self._call_mcp_simulation(data))

                return json.dumps(result, ensure_ascii=False)

            except Exception as e:
                logger.error(f"MCP 시뮬레이션 실행 실패: {e}")
                return f"시뮬레이션 실행 실패: {str(e)}"

        def analyze_simulation_results(input_text: str) -> str:
            """시뮬레이션 결과 분석 후 예방책 생성"""
            try:
                data = _coerce_jsonlike(input_text)
                case_id = UUID(str(data.get("case_id")))
                run_no = int(data.get("run_no", 1))

                # 대화 로그 분석
                logs = self._get_logs_for_run(case_id, run_no)

                # 간단한 분석
                victim_logs = [
                    log for log in logs if log.get("role") == "victim"
                ]
                defensive_responses = 0

                for log in victim_logs:
                    content = log.get("content", "").lower()
                    if any(word in content
                           for word in ["의심", "확인", "신고", "사기"]):
                        defensive_responses += 1

                # 예방책 생성
                prevention_strategy = {
                    "summary":
                    f"총 {len(logs)}턴 대화, 방어 반응 {defensive_responses}회",
                    "analysis": {
                        "defensive_responses":
                        defensive_responses,
                        "conversation_quality":
                        len(logs) / 20.0,
                        "outcome":
                        "success"
                        if defensive_responses >= 2 else "needs_improvement"
                    },
                    "steps":
                    ["의심스러운 전화는 즉시 끊기", "개인정보 절대 제공 금지", "112 또는 1332로 신고"],
                    "personalized_tips": []
                }

                if defensive_responses < 2:
                    prevention_strategy["personalized_tips"].append(
                        "방어 반응을 더 빨리 보이도록 훈련 필요")

                return json.dumps(prevention_strategy, ensure_ascii=False)

            except Exception as e:
                return f"결과 분석 실패: {str(e)}"

        return [
            Tool(name="analyze_victim_profile",
                 description="피해자 프로필을 분석합니다. 입력: {'victim_info': {...}}",
                 func=analyze_victim_profile),
            Tool(name="execute_simulation_with_mcp",
                 description="MCP 서버를 호출하여 시뮬레이션을 실행합니다. 입력: 시뮬레이션 설정",
                 func=execute_simulation_with_mcp),
            Tool(
                name="analyze_simulation_results",
                description=
                "시뮬레이션 결과를 분석하고 예방책을 생성합니다. 입력: {'case_id': UUID, 'run_no': int}",
                func=analyze_simulation_results)
        ]

    async def _call_mcp_simulation(self, config: Dict[str,
                                                      Any]) -> Dict[str, Any]:
        """MCP 클라이언트로 시뮬레이션 요청"""
        import websockets

        try:
            url = getattr(self, "mcp_url", None) or "ws://127.0.0.1:8001/mcp"
            async with websockets.connect(
                    url,
                    open_timeout=15,  # 기본 10 → 15초
                    ping_interval=30,
                    ping_timeout=120,
                    close_timeout=10,
                    max_queue=None,
            ) as websocket:
                # 초기화
                init_msg = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {}
                }
                await websocket.send(json.dumps(init_msg))
                await websocket.recv()

                # 시뮬레이션 실행
                sim_msg = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "simulator.run",
                        "arguments": {
                            "offender_id": config.get("offender_id", 1),
                            "victim_id": config.get("victim_id", 1),
                            "scenario": config.get("scenario", {}),
                            "max_rounds": config.get("max_rounds", 20)
                        }
                    }
                }

                logger.info(
                    "[MCP/ws] send tools/call simulator.run "
                    f"(offender_id={sim_msg['params']['arguments']['offender_id']}, "
                    f"victim_id={sim_msg['params']['arguments']['victim_id']}, "
                    f"max_rounds={sim_msg['params']['arguments']['max_rounds']})"
                )

                await websocket.send(json.dumps(sim_msg))
                response = await websocket.recv()
                logger.info(f"[MCP/ws] recv len={len(response)}")
                result = json.loads(response)

                return result.get("result", {}).get("content", {})

        except Exception as e:
            logger.error(f"MCP 통신 실패: {e}")
            return {"error": str(e)}

    def _get_logs_for_run(self, case_id: UUID,
                          run_no: int) -> List[Dict[str, Any]]:
        """특정 run의 로그 조회"""
        rows = (self.db.query(m.ConversationLog).filter(
            m.ConversationLog.case_id == case_id,
            m.ConversationLog.run == run_no).order_by(
                m.ConversationLog.turn_index.asc()).all())

        return [{
            "turn": r.turn_index,
            "role": r.role,
            "content": r.content,
            "run": r.run
        } for r in rows]

    def _debug_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        # agent_scratchpad가 어딘가서 섞여 들어오는지 확인
        suspicious = {
            k: type(v).__name__
            for k, v in payload.items() if k == "agent_scratchpad"
        }
        logger.info(
            f"[invoke.keys] {list(payload.keys())} suspicious={suspicious}")

    def run_comprehensive_simulation(
            self, user_request: Dict[str, Any]) -> Dict[str, Any]:
        """사용자 요청을 받아 전체 시뮬레이션 프로세스 실행"""

        try:
            # React Agent가 자동으로 모든 과정을 처리
            input_prompt = f"""
사용자가 보이스피싱 시뮬레이션을 요청했습니다:

피해자 정보: {json.dumps(user_request.get('victim_info', {}), ensure_ascii=False)}
시나리오: {json.dumps(user_request.get('scenario', {}), ensure_ascii=False)}
목표: {user_request.get('objectives', ['education'])}

다음 순서로 처리해주세요:
1. 먼저 피해자 프로필을 분석하고
2. MCP 서버를 호출하여 시뮬레이션을 실행한 후  
3. 결과를 분석하여 맞춤형 예방책을 생성해주세요

단계별로 신중하게 처리해주세요.
"""
            # ✅ 여기 ‘메서드 내부’에서 payload 생성/사용
            payload = {"input": input_prompt}
            result = self.agent_executor.invoke(payload)

            return {
                "status": "success",
                "analysis": result.get("output", ""),
                "thought_process": result.get("intermediate_steps", []),
                "timestamp": datetime.now().isoformat(),
                "mcp_used": self.mcp_manager.is_running
            }

        except Exception as e:
            logger.error(f"종합 시뮬레이션 실패: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        finally:
            # 작업 완료 후 MCP 서버 정리
            self.mcp_manager.stop_mcp_server()


# 편의 함수들
def create_simulation_request(victim_info: Dict[str, Any],
                              scenario: Dict[str, Any],
                              attacker_model: str = "gpt-o4-mini",
                              victim_model: str = "gpt-o4-mini",
                              objectives: List[str] = None) -> Dict[str, Any]:
    """시뮬레이션 요청 생성"""
    return {
        "victim_info": victim_info,
        "scenario": scenario,
        "attacker_model": attacker_model,
        "victim_model": victim_model,
        "objectives": objectives or ["education"]
    }


def run_managed_simulation(db: Session,
                           user_request: Dict[str, Any]) -> Dict[str, Any]:
    """관리자 Agent를 통한 시뮬레이션 실행"""
    manager = SimulationManagerAgent(db)
    return manager.run_comprehensive_simulation(user_request)
