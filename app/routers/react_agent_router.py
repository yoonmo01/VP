# app/routers/react_agent_router.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
import json
from datetime import datetime

from app.db.session import get_db
from app.services.agent.simulation_manager_agent import (
    SimulationManagerAgent, run_managed_simulation, create_simulation_request)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/react-agent", tags=["React Agent"])


# Pydantic 모델들
class VictimInfo(BaseModel):
    age: int = Field(description="피해자 나이")
    tech_literacy: str = Field(default="medium",
                               description="기술 이해도: low/medium/high")
    personality: Dict[str, Any] = Field(default_factory=dict,
                                        description="성격 특성")
    background: Dict[str, Any] = Field(default_factory=dict,
                                       description="배경 정보")


class ScenarioInfo(BaseModel):
    type: str = Field(description="시나리오 타입")
    description: str = Field(description="시나리오 설명")
    steps: List[str] = Field(default_factory=list, description="공격 단계들")
    target: Optional[str] = Field(default=None, description="타겟 정보")


class ModelSettings(BaseModel):
    attacker_model: str = Field(default="gpt-4", description="공격자 LLM 모델")
    victim_model: str = Field(default="claude-3", description="피해자 LLM 모델")
    temperature: Optional[float] = Field(default=0.7, description="모델 온도 설정")


class SimulationRequest(BaseModel):
    victim_info: VictimInfo
    scenario: ScenarioInfo
    models: ModelSettings = Field(default_factory=ModelSettings)
    objectives: List[str] = Field(default=["education"],
                                  description="시뮬레이션 목적")
    max_rounds: int = Field(default=30, description="최대 대화 턴")
    offender_id: int = Field(description="DB상 공격자 ID")
    victim_id: int = Field(description="DB상 피해자 ID")


class AnalysisRequest(BaseModel):
    case_id: UUID
    focus: Optional[str] = Field(default="", description="분석 초점 영역")
    mode: str = Field(default="comprehensive",
                      description="분석 모드: basic/comprehensive/expert")


class QuestionRequest(BaseModel):
    case_id: UUID
    question: str = Field(description="React Agent에게 묻고 싶은 질문")


@router.post("/simulation", summary="React Agent 기반 완전 자동 시뮬레이션")
async def run_intelligent_simulation(request: SimulationRequest,
                                     background_tasks: BackgroundTasks,
                                     db: Session = Depends(get_db)):
    """
    React Agent 기반 완전 자동 시뮬레이션

    React Agent가 스스로:
    1. 피해자 프로필을 분석하고 취약점 평가
    2. 시나리오에 맞는 최적 전략 수립
    3. 각 LLM 모델에 맞는 프롬프트 최적화
    4. MCP Client로 시뮬레이션 서버에 연결하여 실행
    5. 실시간 결과 분석 및 개선점 제시

    사용자는 기본 정보만 제공하면, 나머지는 AI가 창의적으로 처리
    """
    try:
        # React Agent 초기화
        agent = SimulationManagerAgent(db)

        # 요청을 Agent가 이해할 수 있는 형식으로 변환
        agent_request = {
            "victim_info": request.victim_info.dict(),
            "scenario": request.scenario.dict(),
            "attacker_model": request.models.attacker_model,
            "victim_model": request.models.victim_model,
            "objectives": request.objectives,
            "max_rounds": request.max_rounds,
            "offender_id": request.offender_id,
            "victim_id": request.victim_id
        }

        # React Agent가 완전 자동으로 시뮬레이션 관리
        result = agent.run_comprehensive_simulation(agent_request)

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))

        return {
            "success":
            True,
            "simulation_id":
            id(request),
            "agent_analysis":
            result.get("analysis", ""),
            "thought_process":
            result.get("thought_process", []),
            "tools_used": [
                step[0].tool for step in result.get("thought_process", [])
                if hasattr(step[0], 'tool')
            ],
            "timestamp":
            result.get("timestamp"),
            "meta": {
                "agent_type": "simulation_manager_react_agent",
                "mcp_integration": "active",
                "automation_level": "full"
            }
        }

    except Exception as e:
        logger.error(f"React Agent 시뮬레이션 실행 실패: {e}")
        raise HTTPException(status_code=500, detail=f"시뮬레이션 실행 실패: {str(e)}")


@router.post("/analyze", summary="React Agent 자유 분석")
async def analyze_with_react_agent(request: AnalysisRequest,
                                   db: Session = Depends(get_db)):
    """
    React Agent를 통한 자유로운 케이스 분석

    React Agent가:
    - 케이스를 다양한 관점에서 자유롭게 탐색
    - 예상치 못한 패턴이나 통찰 발견
    - 창의적이고 깊이 있는 분석 제공
    - 인간이 놓칠 수 있는 세부사항 포착
    """
    try:
        agent = SimulationManagerAgent(db)

        # Agent에게 분석 요청 (자유 형식)
        analysis_prompt = f"""
케이스 {request.case_id}를 자유롭게 분석해주세요.
{f"특히 {request.focus}에 집중해서 " if request.focus else ""}
분석 깊이: {request.mode}

궁금한 것을 자유롭게 탐구하고, 창의적인 통찰을 제공해주세요.
"""

        result = agent.agent_executor.invoke({"input": analysis_prompt})

        return {
            "success": True,
            "case_id": str(request.case_id),
            "analysis": result.get("output", ""),
            "exploration_steps": result.get("intermediate_steps", []),
            "focus_area": request.focus or "전체 케이스",
            "analysis_mode": request.mode,
            "meta": {
                "agent_type": "free_exploration",
                "thinking_style": "creative_and_intuitive",
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        logger.error(f"React Agent 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=f"분석 실패: {str(e)}")


@router.post("/ask", summary="React Agent에게 자연어 질문")
async def ask_react_agent(request: QuestionRequest,
                          db: Session = Depends(get_db)):
    """
    React Agent에게 자연어로 자유롭게 질문

    예시 질문들:
    - "이 케이스에서 공격자가 가장 영리했던 순간은?"
    - "피해자가 의심하기 시작한 정확한 시점과 이유는?"  
    - "다른 케이스와 비교했을 때 이 케이스의 특이점은?"
    - "만약 내가 이 상황에 있었다면 어떻게 대응했을까?"
    """
    try:
        agent = SimulationManagerAgent(db)

        # 자연어 질문을 Agent에게 전달
        question_prompt = f"""
케이스 {request.case_id}에 대한 질문입니다:

"{request.question}"

이 질문에 대해 자유롭게 탐구하고 통찰력 있는 답변을 해주세요.
필요하면 여러 도구를 사용해서 깊이 있게 분석해보세요.
"""

        result = agent.agent_executor.invoke({"input": question_prompt})

        return {
            "success": True,
            "case_id": str(request.case_id),
            "question": request.question,
            "answer": result.get("output", ""),
            "reasoning_process": result.get("intermediate_steps", []),
            "meta": {
                "agent_type": "question_answering",
                "interaction_style": "conversational",
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        logger.error(f"질문 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"질문 처리 실패: {str(e)}")


@router.get("/debug/prompt")
def debug_prompt(db: Session = Depends(get_db)):
    agent = SimulationManagerAgent(db)
    return {
        "vars": agent.react_prompt.input_variables,
        "last_msg_type": str(type(agent.react_prompt.messages[-1]).__name__),
        "tools": [t.name for t in agent.tools],
    }


# app/routers/react_agent_router.py  (get_react_agent_status)
@router.get("/status", summary="React Agent 시스템 상태")
async def get_react_agent_status(db: Session = Depends(get_db)):
    try:
        agent = SimulationManagerAgent(db)
        mcp_status = "ready" if agent.mcp_manager.is_running else "stopped"

        return {
            "system_status": "healthy",
            "react_agent": {
                "available":
                True,
                "type":
                "simulation_manager_agent",
                "tools_available":
                len(agent.tools),
                "capabilities": [
                    "피해자 프로필 분석", "시뮬레이션 전략 수립", "LLM 모델별 프롬프트 최적화",
                    "MCP 클라이언트 기능", "실시간 결과 분석", "창의적 통찰 제공"
                ]
            },
            "mcp_integration": {
                "client_ready":
                True,
                "server_url":
                agent.mcp_server_url if agent.mcp_manager.is_running else None,
                "connection_status":
                mcp_status,
            },
            "available_tools": [tool.name for tool in agent.tools],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"상태 확인 실패: {e}")
        return {
            "system_status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/examples", summary="사용 예시 및 가이드")
async def get_usage_examples():
    """React Agent API 사용 예시와 가이드"""
    return {
        "overview": {
            "description":
            "React Agent는 사용자 입력을 받아 스스로 생각하고 판단하여 최적의 보이스피싱 시뮬레이션을 실행합니다",
            "key_features": [
                "완전 자동화된 시뮬레이션 관리", "창의적이고 예측 불가능한 분석", "사용자별 맞춤 최적화",
                "실시간 MCP 통신", "자연어 상호작용"
            ]
        },
        "endpoints": {
            "full_simulation": {
                "url": "POST /api/react-agent/simulation",
                "description": "React Agent가 처음부터 끝까지 완전 자동으로 시뮬레이션 관리",
                "example": {
                    "victim_info": {
                        "age": 68,
                        "tech_literacy": "low",
                        "personality": {
                            "trusting": True,
                            "cautious": False
                        },
                        "background": {
                            "finance_experience": False
                        }
                    },
                    "scenario": {
                        "type": "urgent_bank_security",
                        "description": "은행 계좌 보안 문제 긴급 알림",
                        "steps": ["신원 확인", "문제 설명", "해결책 제시", "개인정보 요청"]
                    },
                    "models": {
                        "attacker_model": "gpt-4",
                        "victim_model": "claude-3"
                    },
                    "objectives": ["education", "vulnerability_assessment"],
                    "offender_id": 1,
                    "victim_id": 1
                }
            },
            "free_analysis": {
                "url": "POST /api/react-agent/analyze",
                "description": "Agent가 자유롭게 케이스를 탐구하고 분석",
                "example": {
                    "case_id": "uuid-here",
                    "focus": "피해자의 심리적 변화와 방어 메커니즘",
                    "mode": "comprehensive"
                }
            },
            "natural_qa": {
                "url": "POST /api/react-agent/ask",
                "description": "자연어로 Agent에게 궁금한 것을 질문",
                "example": {
                    "case_id": "uuid-here",
                    "question": "이 공격자가 사용한 가장 교묘한 심리 기법은 무엇이고, 왜 효과적이었나요?"
                }
            }
        },
        "workflow": {
            "1": "사용자가 기본 정보 입력 (피해자, 시나리오, 목표)",
            "2": "React Agent가 상황을 자유롭게 분석하고 판단",
            "3": "Agent가 최적 전략을 창의적으로 수립",
            "4": "MCP Client로 시뮬레이션 서버에 연결",
            "5": "실시간 LLM vs LLM 대화 실행",
            "6": "결과를 분석하고 인사이트 제공"
        },
        "agent_advantages": [
            "인간이 놓치는 미묘한 패턴 발견", "예상치 못한 창의적 해결책 제시", "실시간 적응과 최적화",
            "일관성 있는 고품질 분석", "자연스러운 대화형 상호작용"
        ]
    }


# 개발/테스트용 엔드포인트
@router.post("/test", summary="React Agent 테스트 실행")
async def test_react_agent_system(test_mode: str = "basic",
                                  db: Session = Depends(get_db)):
    """
    개발용 React Agent 테스트

    test_mode:
    - basic: 간단한 분석 테스트
    - comprehensive: 전체 시뮬레이션 테스트  
    - interactive: 질의응답 테스트
    """
    try:
        agent = SimulationManagerAgent(db)

        if test_mode == "basic":
            # 기본 분석 테스트
            result = agent.agent_executor.invoke(
                {"input": "React Agent 시스템이 정상 작동하는지 간단히 테스트해주세요"})

        elif test_mode == "comprehensive":
            # 전체 시뮬레이션 테스트
            test_request = create_simulation_request(victim_info={
                "age": 70,
                "tech_literacy": "low"
            },
                                                     scenario={
                                                         "type": "test",
                                                         "description":
                                                         "테스트 시나리오"
                                                     },
                                                     objectives=["test"])
            result = agent.run_comprehensive_simulation(test_request)

        elif test_mode == "interactive":
            # 대화형 테스트
            result = agent.agent_executor.invoke(
                {"input": "안녕하세요, React Agent님! 자기소개를 해주세요."})

        else:
            raise HTTPException(status_code=400, detail="지원하지 않는 테스트 모드입니다")

        return {
            "test_mode": test_mode,
            "status": "success",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"React Agent 테스트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"테스트 실패: {str(e)}")
